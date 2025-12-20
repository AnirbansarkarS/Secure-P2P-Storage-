import asyncio
import aiohttp
import logging
import hashlib
from typing import Optional, Dict
import time

logger = logging.getLogger(__name__)


class TransferService:
    """Handles peer-to-peer shard transfers"""
    
    def __init__(self, max_retries: int = 3, timeout: int = 30):
        """
        Initialize transfer service
        
        Args:
            max_retries: Maximum number of retry attempts
            timeout: Timeout for transfers in seconds
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.transfer_stats = {
            'uploads': 0,
            'downloads': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'failures': 0
        }
        
        logger.info("Transfer service initialized")
    
    async def upload_shard(self, session: aiohttp.ClientSession,
                          peer_url: str,
                          file_hash: str,
                          shard_index: int,
                          shard_data: bytes,
                          shard_hash: str) -> bool:
        """
        Upload a shard to a peer
        
        Args:
            session: aiohttp session
            peer_url: URL of the target peer
            file_hash: Hash of the original file
            shard_index: Index of this shard
            shard_data: Shard bytes
            shard_hash: Hash of the shard
            
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                # Prepare multipart form data
                data = aiohttp.FormData()
                data.add_field('file_hash', file_hash)
                data.add_field('shard_index', str(shard_index))
                data.add_field('shard_hash', shard_hash)
                data.add_field('shard_data', shard_data, 
                             filename=f"{file_hash}_{shard_index}.shard")
                
                # Upload with timeout
                async with session.post(
                    f"{peer_url}/shard/upload",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Verify upload
                        if result.get('shard_hash') == shard_hash:
                            self.transfer_stats['uploads'] += 1
                            self.transfer_stats['bytes_sent'] += len(shard_data)
                            
                            logger.info(f"Uploaded shard {shard_index} to {peer_url} "
                                      f"({len(shard_data)} bytes)")
                            return True
                        else:
                            logger.error(f"Shard hash mismatch after upload")
                    else:
                        logger.warning(f"Upload failed with status {response.status}")
                
            except asyncio.TimeoutError:
                logger.warning(f"Upload timeout (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.error(f"Upload error (attempt {attempt + 1}/{self.max_retries}): {e}")
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        self.transfer_stats['failures'] += 1
        logger.error(f"Failed to upload shard {shard_index} after {self.max_retries} attempts")
        return False
    
    async def download_shard(self, session: aiohttp.ClientSession,
                           peer_url: str,
                           file_hash: str,
                           shard_index: int,
                           expected_hash: str = None) -> Optional[bytes]:
        """
        Download a shard from a peer
        
        Args:
            session: aiohttp session
            peer_url: URL of the source peer
            file_hash: Hash of the original file
            shard_index: Index of the shard
            expected_hash: Optional expected hash for verification
            
        Returns:
            Shard bytes or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                async with session.get(
                    f"{peer_url}/shard/download",
                    params={
                        'file_hash': file_hash,
                        'shard_index': shard_index
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        shard_data = await response.read()
                        
                        # Verify hash if provided
                        if expected_hash:
                            computed_hash = hashlib.sha256(shard_data).hexdigest()
                            if computed_hash != expected_hash:
                                logger.error(f"Shard hash mismatch: expected {expected_hash}, "
                                           f"got {computed_hash}")
                                continue
                        
                        self.transfer_stats['downloads'] += 1
                        self.transfer_stats['bytes_received'] += len(shard_data)
                        
                        logger.info(f"Downloaded shard {shard_index} from {peer_url} "
                                  f"({len(shard_data)} bytes)")
                        return shard_data
                    else:
                        logger.warning(f"Download failed with status {response.status}")
                
            except asyncio.TimeoutError:
                logger.warning(f"Download timeout (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.error(f"Download error (attempt {attempt + 1}/{self.max_retries}): {e}")
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        self.transfer_stats['failures'] += 1
        logger.error(f"Failed to download shard {shard_index} after {self.max_retries} attempts")
        return None
    
    async def batch_upload_shards(self, session: aiohttp.ClientSession,
                                 shard_distribution: Dict[str, list],
                                 file_hash: str,
                                 shards: list,
                                 shard_hashes: list) -> Dict[int, list]:
        """
        Upload multiple shards to multiple peers in parallel
        
        Args:
            session: aiohttp session
            shard_distribution: Dict mapping peer_url to list of shard indices
            file_hash: Hash of the original file
            shards: List of shard bytes
            shard_hashes: List of shard hashes
            
        Returns:
            Dict mapping shard_index to list of successful peer URLs
        """
        tasks = []
        shard_peer_map = {}
        
        # Create upload tasks
        for peer_url, shard_indices in shard_distribution.items():
            for shard_idx in shard_indices:
                task = self.upload_shard(
                    session, peer_url, file_hash, shard_idx,
                    shards[shard_idx], shard_hashes[shard_idx]
                )
                tasks.append((task, shard_idx, peer_url))
        
        # Execute uploads in parallel
        results = await asyncio.gather(
            *[task for task, _, _ in tasks],
            return_exceptions=True
        )
        
        # Process results
        successful_uploads = {}
        for (_, shard_idx, peer_url), result in zip(tasks, results):
            if result is True:
                if shard_idx not in successful_uploads:
                    successful_uploads[shard_idx] = []
                successful_uploads[shard_idx].append(peer_url)
        
        logger.info(f"Batch upload complete: {len(successful_uploads)} shards uploaded")
        return successful_uploads
    
    async def batch_download_shards(self, session: aiohttp.ClientSession,
                                   shard_locations: Dict[int, list],
                                   file_hash: str,
                                   shard_hashes: list,
                                   required_shards: int) -> Dict[int, bytes]:
        """
        Download multiple shards from multiple peers in parallel
        
        Args:
            session: aiohttp session
            shard_locations: Dict mapping shard_index to list of peer URLs
            file_hash: Hash of the original file
            shard_hashes: List of expected shard hashes
            required_shards: Minimum number of shards needed
            
        Returns:
            Dict mapping shard_index to shard bytes
        """
        downloaded_shards = {}
        tasks = []
        
        # Create download tasks for each shard
        for shard_idx, peer_urls in shard_locations.items():
            if not peer_urls:
                continue
            
            # Try first peer for each shard
            peer_url = peer_urls[0]
            expected_hash = shard_hashes[shard_idx] if shard_idx < len(shard_hashes) else None
            
            task = self.download_shard(
                session, peer_url, file_hash, shard_idx, expected_hash
            )
            tasks.append((task, shard_idx, peer_urls))
        
        # Execute downloads in parallel
        results = await asyncio.gather(
            *[task for task, _, _ in tasks],
            return_exceptions=True
        )
        
        # Process results and retry failures
        for (_, shard_idx, peer_urls), result in zip(tasks, results):
            if isinstance(result, bytes):
                downloaded_shards[shard_idx] = result
            elif len(peer_urls) > 1:
                # Retry with alternative peers
                for alt_peer_url in peer_urls[1:]:
                    expected_hash = shard_hashes[shard_idx] if shard_idx < len(shard_hashes) else None
                    shard_data = await self.download_shard(
                        session, alt_peer_url, file_hash, shard_idx, expected_hash
                    )
                    if shard_data:
                        downloaded_shards[shard_idx] = shard_data
                        break
        
        logger.info(f"Batch download complete: {len(downloaded_shards)}/{required_shards} shards")
        
        if len(downloaded_shards) < required_shards:
            logger.error(f"Insufficient shards: got {len(downloaded_shards)}, "
                        f"need {required_shards}")
        
        return downloaded_shards
    
    async def verify_shard_integrity(self, shard_data: bytes, expected_hash: str) -> bool:
        """
        Verify shard integrity
        
        Args:
            shard_data: Shard bytes
            expected_hash: Expected SHA-256 hash
            
        Returns:
            True if hash matches, False otherwise
        """
        computed_hash = hashlib.sha256(shard_data).hexdigest()
        is_valid = computed_hash == expected_hash
        
        if not is_valid:
            logger.error(f"Integrity check failed: expected {expected_hash}, "
                        f"got {computed_hash}")
        
        return is_valid
    
    def get_transfer_stats(self) -> Dict:
        """Get transfer statistics"""
        return {
            **self.transfer_stats,
            'success_rate': (
                (self.transfer_stats['uploads'] + self.transfer_stats['downloads']) /
                (self.transfer_stats['uploads'] + self.transfer_stats['downloads'] + 
                 self.transfer_stats['failures'])
                if (self.transfer_stats['uploads'] + self.transfer_stats['downloads'] + 
                    self.transfer_stats['failures']) > 0
                else 0
            )
        }
    
    def reset_stats(self):
        """Reset transfer statistics"""
        self.transfer_stats = {
            'uploads': 0,
            'downloads': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'failures': 0
        }
