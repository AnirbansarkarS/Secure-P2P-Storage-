import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, Callable, Dict
import logging
from ..p2p.node import P2PNode

logger = logging.getLogger(__name__)


class P2PClient:
    """High-level client API for P2P storage"""
    
    def __init__(self, coordinator_url: str = "http://localhost:8000",
                 data_dir: str = "./p2p_client"):
        """
        Initialize P2P client
        
        Args:
            coordinator_url: URL of the coordinator server
            data_dir: Directory for client data
        """
        self.coordinator_url = coordinator_url
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.node = None
        self.is_running = False
        
        logger.info(f"P2P Client initialized: {coordinator_url}")
    
    async def start(self, port: int = None):
        """Start the client node"""
        if self.is_running:
            logger.warning("Client already running")
            return
        
        self.node = P2PNode(coordinator_url=self.coordinator_url)
        await self.node.start(port or 9000)
        self.is_running = True
        logger.info("Client started")
    
    async def stop(self):
        """Stop the client node"""
        if self.node and self.is_running:
            # Cleanup logic here
            self.is_running = False
            logger.info("Client stopped")
    
    async def upload_file(self, file_path: str, password: str,
                         progress_callback: Optional[Callable] = None) -> str:
        """
        Upload a file to the P2P network
        
        Args:
            file_path: Path to the file to upload
            password: Encryption password
            progress_callback: Optional callback for progress updates
            
        Returns:
            File hash
        """
        if not self.is_running:
            await self.start()
        
        try:
            if progress_callback:
                progress_callback(0, "Starting upload...")
            
            file_hash = await self.node.store_file(file_path, password)
            
            if progress_callback:
                progress_callback(100, "Upload complete")
            
            logger.info(f"File uploaded: {file_hash}")
            return file_hash
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise
    
    async def download_file(self, file_hash: str, password: str,
                           output_path: str = None,
                           progress_callback: Optional[Callable] = None) -> str:
        """
        Download a file from the P2P network
        
        Args:
            file_hash: Hash of the file to download
            password: Decryption password
            output_path: Optional output path
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to downloaded file
        """
        if not self.is_running:
            await self.start()
        
        try:
            if progress_callback:
                progress_callback(0, "Starting download...")
            
            file_data = await self.node.retrieve_file(file_hash, password)
            
            if not output_path:
                output_path = self.data_dir / f"downloaded_{file_hash[:8]}"
            
            with open(output_path, 'wb') as f:
                f.write(file_data)
            
            if progress_callback:
                progress_callback(100, "Download complete")
            
            logger.info(f"File downloaded to: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise
    
    async def get_file_info(self, file_hash: str) -> Optional[Dict]:
        """Get information about a stored file"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.coordinator_url}/file/{file_hash}/locations"
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return None
    
    async def list_peers(self, min_reputation: float = 0.0) -> list:
        """List available peers"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.coordinator_url}/peers",
                    params={"min_reputation": min_reputation}
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return []
        except Exception as e:
            logger.error(f"Failed to list peers: {e}")
            return []


# Synchronous wrapper
class P2PClientSync:
    """Synchronous wrapper for P2PClient"""
    
    def __init__(self, coordinator_url: str = "http://localhost:8000",
                 data_dir: str = "./p2p_client"):
        self.client = P2PClient(coordinator_url, data_dir)
        self.loop = asyncio.new_event_loop()
    
    def upload_file(self, file_path: str, password: str,
                   progress_callback: Optional[Callable] = None) -> str:
        """Upload a file (synchronous)"""
        return self.loop.run_until_complete(
            self.client.upload_file(file_path, password, progress_callback)
        )
    
    def download_file(self, file_hash: str, password: str,
                     output_path: str = None,
                     progress_callback: Optional[Callable] = None) -> str:
        """Download a file (synchronous)"""
        return self.loop.run_until_complete(
            self.client.download_file(file_hash, password, output_path, progress_callback)
        )
    
    def get_file_info(self, file_hash: str) -> Optional[Dict]:
        """Get file info (synchronous)"""
        return self.loop.run_until_complete(
            self.client.get_file_info(file_hash)
        )
    
    def list_peers(self, min_reputation: float = 0.0) -> list:
        """List peers (synchronous)"""
        return self.loop.run_until_complete(
            self.client.list_peers(min_reputation)
        )
    
    def close(self):
        """Close the client"""
        self.loop.run_until_complete(self.client.stop())
        self.loop.close()
