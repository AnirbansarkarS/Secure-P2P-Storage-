import os
import json
import sqlite3
import hashlib
import shutil
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages local storage for P2P node"""
    
    def __init__(self, data_dir: str, max_storage_gb: int = 10):
        """
        Initialize storage manager
        
        Args:
            data_dir: Directory for storing data
            max_storage_gb: Maximum storage quota in GB
        """
        self.data_dir = Path(data_dir)
        self.max_storage_bytes = max_storage_gb * 1024 * 1024 * 1024
        
        # Create directory structure
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.shards_dir = self.data_dir / "shards"
        self.shards_dir.mkdir(exist_ok=True)
        self.metadata_dir = self.data_dir / "metadata"
        self.metadata_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self.db_path = self.data_dir / "storage.db"
        self._init_database()
        
        logger.info(f"Storage manager initialized: {data_dir} (max: {max_storage_gb}GB)")
    
    def _init_database(self):
        """Initialize SQLite database for metadata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create shards table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shards (
                shard_hash TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                shard_index INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_verified TIMESTAMP,
                peer_id TEXT,
                expires_at TIMESTAMP,
                UNIQUE(file_hash, shard_index)
            )
        """)
        
        # Create files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_hash TEXT PRIMARY KEY,
                original_name TEXT,
                total_size INTEGER,
                shards_total INTEGER,
                shards_required INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)
        
        # Create storage stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS storage_stats (
                id INTEGER PRIMARY KEY,
                total_shards INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0,
                last_gc TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize stats if not exists
        cursor.execute("INSERT OR IGNORE INTO storage_stats (id) VALUES (1)")
        
        conn.commit()
        conn.close()
    
    def store_shard(self, file_hash: str, shard_index: int, shard_data: bytes, 
                    peer_id: str = None, expires_at: datetime = None) -> str:
        """
        Store a shard to disk
        
        Args:
            file_hash: Hash of the original file
            shard_index: Index of this shard
            shard_data: Shard bytes
            peer_id: ID of peer who owns this shard
            expires_at: Expiration timestamp
            
        Returns:
            Shard hash
        """
        try:
            # Check storage quota
            if not self._check_quota(len(shard_data)):
                raise Exception("Storage quota exceeded")
            
            # Compute shard hash
            shard_hash = hashlib.sha256(shard_data).hexdigest()
            
            # Create filename
            filename = f"{file_hash}_{shard_index}_{shard_hash}.shard"
            filepath = self.shards_dir / filename
            
            # Write shard to disk
            with open(filepath, 'wb') as f:
                f.write(shard_data)
            
            # Store metadata in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO shards 
                (shard_hash, file_hash, shard_index, size_bytes, peer_id, expires_at, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (shard_hash, file_hash, shard_index, len(shard_data), peer_id, 
                  expires_at, datetime.now()))
            
            # Update stats
            self._update_stats(conn, len(shard_data))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored shard {shard_index} for file {file_hash[:8]}: {len(shard_data)} bytes")
            
            return shard_hash
            
        except Exception as e:
            logger.error(f"Failed to store shard: {e}")
            raise
    
    def retrieve_shard(self, file_hash: str, shard_index: int) -> Optional[bytes]:
        """
        Retrieve a shard from disk
        
        Args:
            file_hash: Hash of the original file
            shard_index: Index of the shard
            
        Returns:
            Shard bytes or None if not found
        """
        try:
            # Find shard file
            pattern = f"{file_hash}_{shard_index}_"
            for filename in os.listdir(self.shards_dir):
                if filename.startswith(pattern):
                    filepath = self.shards_dir / filename
                    
                    # Read shard
                    with open(filepath, 'rb') as f:
                        shard_data = f.read()
                    
                    # Verify integrity
                    shard_hash = filename.split('_')[2].replace('.shard', '')
                    computed_hash = hashlib.sha256(shard_data).hexdigest()
                    
                    if computed_hash != shard_hash:
                        logger.error(f"Shard integrity check failed: {filename}")
                        return None
                    
                    # Update last verified
                    self._update_verification(shard_hash)
                    
                    logger.info(f"Retrieved shard {shard_index} for file {file_hash[:8]}")
                    return shard_data
            
            logger.warning(f"Shard not found: {file_hash[:8]}_{shard_index}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve shard: {e}")
            return None
    
    def delete_shard(self, file_hash: str, shard_index: int) -> bool:
        """
        Delete a shard from storage
        
        Args:
            file_hash: Hash of the original file
            shard_index: Index of the shard
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            pattern = f"{file_hash}_{shard_index}_"
            for filename in os.listdir(self.shards_dir):
                if filename.startswith(pattern):
                    filepath = self.shards_dir / filename
                    file_size = os.path.getsize(filepath)
                    
                    # Delete file
                    os.remove(filepath)
                    
                    # Update database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    
                    shard_hash = filename.split('_')[2].replace('.shard', '')
                    cursor.execute("DELETE FROM shards WHERE shard_hash = ?", (shard_hash,))
                    
                    # Update stats
                    self._update_stats(conn, -file_size)
                    
                    conn.commit()
                    conn.close()
                    
                    logger.info(f"Deleted shard {shard_index} for file {file_hash[:8]}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete shard: {e}")
            return False
    
    def list_shards(self, file_hash: str = None) -> List[Dict]:
        """
        List stored shards
        
        Args:
            file_hash: Optional filter by file hash
            
        Returns:
            List of shard metadata dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if file_hash:
            cursor.execute("""
                SELECT shard_hash, file_hash, shard_index, size_bytes, stored_at, last_verified
                FROM shards WHERE file_hash = ?
                ORDER BY shard_index
            """, (file_hash,))
        else:
            cursor.execute("""
                SELECT shard_hash, file_hash, shard_index, size_bytes, stored_at, last_verified
                FROM shards
                ORDER BY stored_at DESC
            """)
        
        shards = []
        for row in cursor.fetchall():
            shards.append({
                'shard_hash': row[0],
                'file_hash': row[1],
                'shard_index': row[2],
                'size_bytes': row[3],
                'stored_at': row[4],
                'last_verified': row[5]
            })
        
        conn.close()
        return shards
    
    def get_storage_stats(self) -> Dict:
        """Get current storage statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT total_shards, total_bytes FROM storage_stats WHERE id = 1")
        row = cursor.fetchone()
        
        total_shards = row[0] if row else 0
        total_bytes = row[1] if row else 0
        
        conn.close()
        
        return {
            'total_shards': total_shards,
            'total_bytes': total_bytes,
            'total_gb': round(total_bytes / (1024**3), 2),
            'max_bytes': self.max_storage_bytes,
            'max_gb': round(self.max_storage_bytes / (1024**3), 2),
            'usage_percent': round((total_bytes / self.max_storage_bytes) * 100, 2) if self.max_storage_bytes > 0 else 0,
            'available_bytes': self.max_storage_bytes - total_bytes
        }
    
    def garbage_collect(self) -> int:
        """
        Remove expired shards
        
        Returns:
            Number of shards removed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find expired shards
            cursor.execute("""
                SELECT shard_hash, file_hash, shard_index, size_bytes
                FROM shards
                WHERE expires_at IS NOT NULL AND expires_at < ?
            """, (datetime.now(),))
            
            expired = cursor.fetchall()
            removed_count = 0
            
            for shard_hash, file_hash, shard_index, size_bytes in expired:
                if self.delete_shard(file_hash, shard_index):
                    removed_count += 1
            
            # Update last GC time
            cursor.execute("""
                UPDATE storage_stats SET last_gc = ? WHERE id = 1
            """, (datetime.now(),))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Garbage collection: removed {removed_count} expired shards")
            return removed_count
            
        except Exception as e:
            logger.error(f"Garbage collection failed: {e}")
            return 0
    
    def _check_quota(self, additional_bytes: int) -> bool:
        """Check if adding bytes would exceed quota"""
        stats = self.get_storage_stats()
        return (stats['total_bytes'] + additional_bytes) <= self.max_storage_bytes
    
    def _update_stats(self, conn: sqlite3.Connection, size_delta: int):
        """Update storage statistics"""
        cursor = conn.cursor()
        
        if size_delta > 0:
            cursor.execute("""
                UPDATE storage_stats 
                SET total_shards = total_shards + 1,
                    total_bytes = total_bytes + ?,
                    updated_at = ?
                WHERE id = 1
            """, (size_delta, datetime.now()))
        else:
            cursor.execute("""
                UPDATE storage_stats 
                SET total_shards = total_shards - 1,
                    total_bytes = total_bytes + ?,
                    updated_at = ?
                WHERE id = 1
            """, (size_delta, datetime.now()))
    
    def _update_verification(self, shard_hash: str):
        """Update last verification timestamp"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE shards SET last_verified = ? WHERE shard_hash = ?
            """, (datetime.now(), shard_hash))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update verification: {e}")
