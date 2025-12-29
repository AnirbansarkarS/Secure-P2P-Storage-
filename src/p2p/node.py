import asyncio
import aiohttp
import json
import logging
import os
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import base64
import uuid

from ..shared.schemas import PeerInfo, PeerStatus, FileMetadata
from ..shared.crypto import CryptoUtils
from ..shared.config import config
from .encryption import FileEncryptor
from .erasure import ErasureCoder, ShardManager
from .discovery import DiscoveryService
from .transfer import TransferService
from .audit import AuditService
from .storage import StorageManager

logger = logging.getLogger(__name__)

@dataclass
class NodeState:
    peer_id: str = ""
    public_key: str = ""
    private_key: str = ""
    files: Dict[str, FileMetadata] = field(default_factory=dict)
    connected_peers: Set[str] = field(default_factory=set)
    reputation: float = 1.0
    last_heartbeat: datetime = field(default_factory=datetime.now)

class P2PNode:
    def __init__(self, coordinator_url: str = None):
        # Use localhost instead of 0.0.0.0 for client connections (Windows compatibility)
        coordinator_host = "localhost" if config.coordinator.host == "0.0.0.0" else config.coordinator.host
        self.coordinator_url = coordinator_url or f"http://{coordinator_host}:{config.coordinator.port}"
        self.state = NodeState()
        self.session = None
        
        # Initialize components
        self.encryptor = FileEncryptor()
        self.erasure_coder = ErasureCoder(
            required_shards=config.node.shards_required,
            total_shards=config.node.shards_total
        )
        self.shard_manager = ShardManager(config.node.data_dir)
        self.storage_manager = StorageManager(config.node.data_dir)
        self.discovery = DiscoveryService(self)
        self.transfer = TransferService(self)
        self.audit = AuditService(self)
        
        # Generate identity if not exists
        self._load_or_create_identity()
    
    def _load_or_create_identity(self):
        """Load existing identity or create new one"""
        identity_file = f"{config.node.data_dir}/identity.json"
        
        try:
            with open(identity_file, 'r') as f:
                identity = json.load(f)
                self.state.peer_id = identity['peer_id']
                self.state.public_key = identity['public_key']
                self.state.private_key = identity['private_key']
            logger.info(f"Loaded existing identity: {self.state.peer_id}")
        except FileNotFoundError:
            # Generate new identity
            private_key, public_key = CryptoUtils.generate_key_pair()
            self.state.private_key = private_key.decode()
            self.state.public_key = public_key.decode()
            
            # Generate peer ID from public key
            peer_id_hash = hashlib.sha256(public_key).digest()
            self.state.peer_id = base64.b64encode(peer_id_hash).decode()[:16]
            
            # Save identity
            os.makedirs(config.node.data_dir, exist_ok=True)
            with open(identity_file, 'w') as f:
                json.dump({
                    'peer_id': self.state.peer_id,
                    'public_key': self.state.public_key,
                    'private_key': self.state.private_key
                }, f)
            
            logger.info(f"Generated new identity: {self.state.peer_id}")
    
    async def start(self, port: int = None):
        """Start the P2P node"""
        port = port or config.node.port
        
        # Start HTTP server for peer communication
        await self._start_http_server(port)
        
        # Register with coordinator
        await self._register_with_coordinator(port)
        
        # Start background tasks
        asyncio.create_task(self._heartbeat_task())
        asyncio.create_task(self._discovery_task())
        asyncio.create_task(self._audit_task())
        
        logger.info(f"P2P node started on port {port}")
    
    async def _start_http_server(self, port: int):
        """Start HTTP server for peer-to-peer communication"""
        # This is a simplified version
        # In production, use a proper async web framework
        pass
    
    async def _register_with_coordinator(self, port: int):
        """Register node with coordinator"""
        try:
            async with aiohttp.ClientSession() as session:
                peer_info = PeerInfo(
                    peer_id=self.state.peer_id,
                    ip_address=self._get_local_ip(),
                    port=port,
                    public_key=self.state.public_key,
                    available_storage=self.storage_manager.get_available_space(),
                    reputation=self.state.reputation,
                    status=PeerStatus.ONLINE,
                    last_seen=datetime.now(),
                    capabilities=["storage", "retrieval", "audit"]
                )
                
                # Convert to dict with proper JSON serialization
                peer_data = peer_info.model_dump(mode='json')
                
                response = await session.post(
                    f"{self.coordinator_url}/register",
                    json=peer_data
                )
                
                if response.status == 200:
                    logger.info("Registered with coordinator")
                else:
                    logger.error(f"Failed to register: {await response.text()}")
        except Exception as e:
            logger.error(f"Error registering with coordinator: {e}")
    
    async def store_file(self, file_path: str, password: str = None) -> str:
        """Store a file in the P2P network"""
        try:
            # 1. Read file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # 2. Encrypt
            encryption_key, encrypted_data = self.encryptor.encrypt_file(
                file_data, 
                password
            )
            
            # 3. Apply erasure coding
            shards = self.erasure_coder.encode(encrypted_data)
            
            # 4. Compute hashes
            file_hash = self.erasure_coder.compute_file_hash(encrypted_data)
            shard_hashes = [
                self.erasure_coder.compute_shard_hash(shard)
                for shard in shards
            ]
            
            # 5. Store shards locally
            shard_locations = {}
            for i, shard in enumerate(shards):
                shard_hash = self.shard_manager.save_shard(file_hash, i, shard)
                shard_locations[i] = [self.state.peer_id]
            
            # 6. Distribute to other peers
            await self._distribute_shards(file_hash, shards, shard_hashes, shard_locations)
            
            # 7. Register with coordinator
            metadata = FileMetadata(
                file_hash=file_hash,
                original_name=os.path.basename(file_path),
                total_size=len(file_data),
                encrypted_size=len(encrypted_data),
                shards_total=len(shards),
                shards_required=self.erasure_coder.required_shards,
                shard_hashes=shard_hashes,
                shard_locations=shard_locations,
                encryption_scheme="AES-256-GCM"
            )
            
            await self._register_file_metadata(metadata)
            
            logger.info(f"File stored with hash: {file_hash}")
            return file_hash
            
        except Exception as e:
            logger.error(f"Error storing file: {e}")
            raise
    
    async def retrieve_file(self, file_hash: str, password: str = None) -> bytes:
        """Retrieve a file from the P2P network"""
        try:
            # 1. Get file metadata from coordinator
            metadata = await self._get_file_metadata(file_hash)
            
            # 2. Collect shards from peers
            shards = await self._collect_shards(metadata)
            
            # 3. Decode using erasure coding
            encrypted_data = self.erasure_coder.decode(shards)
            
            # 4. Decrypt
            file_data = self.encryptor.decrypt_file(encrypted_data, password)
            
            logger.info(f"File retrieved: {file_hash}")
            return file_data
            
        except Exception as e:
            logger.error(f"Error retrieving file: {e}")
            raise
    
    async def _distribute_shards(self, file_hash: str, shards: List[bytes], 
                               shard_hashes: List[str], shard_locations: dict):
        """Distribute shards to other peers"""
        # Get available peers from coordinator
        peers = await self.discovery.get_available_peers()
        
        # Distribute each shard to multiple peers for redundancy
        redundancy = config.node.redundancy_factor
        
        for shard_index, shard in enumerate(shards):
            # Select peers for this shard
            selected_peers = peers[:redundancy]
            
            for peer in selected_peers:
                if peer['peer_id'] != self.state.peer_id:
                    try:
                        # Send shard to peer
                        success = await self.transfer.send_shard(
                            peer,
                            file_hash,
                            shard_index,
                            shard,
                            shard_hashes[shard_index]
                        )
                        
                        if success:
                            shard_locations[shard_index].append(peer['peer_id'])
                    except Exception as e:
                        logger.error(f"Failed to send shard to {peer['peer_id']}: {e}")
    
    async def _collect_shards(self, metadata: FileMetadata) -> List[tuple]:
        """Collect shards from various peers"""
        shards = []
        
        # Try to get required number of shards
        for shard_index in range(metadata.shards_total):
            if len(shards) >= metadata.shards_required:
                break
            
            # Try peers in order
            for peer_id in metadata.shard_locations.get(shard_index, []):
                try:
                    shard_data = await self.transfer.request_shard(
                        peer_id,
                        metadata.file_hash,
                        shard_index
                    )
                    
                    # Verify shard hash
                    computed_hash = self.erasure_coder.compute_shard_hash(shard_data)
                    if computed_hash == metadata.shard_hashes[shard_index]:
                        shards.append((shard_index, shard_data))
                        break  # Got this shard, move to next
                except Exception as e:
                    logger.error(f"Failed to get shard {shard_index} from {peer_id}: {e}")
        
        if len(shards) < metadata.shards_required:
            raise ValueError(f"Could not collect enough shards. Need {metadata.shards_required}, got {len(shards)}")
        
        return shards
    
    async def _heartbeat_task(self):
        """Send periodic heartbeats to coordinator"""
        while True:
            await asyncio.sleep(30)  # Every 30 seconds
            try:
                await self._register_with_coordinator(config.node.port)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
    
    async def _discovery_task(self):
        """Periodically discover new peers"""
        while True:
            await asyncio.sleep(config.node.peer_discovery_interval)
            try:
                await self.discovery.discover_peers()
            except Exception as e:
                logger.error(f"Discovery failed: {e}")
    
    async def _audit_task(self):
        """Periodically audit stored files"""
        while True:
            await asyncio.sleep(config.node.audit_interval)
            try:
                await self.audit.perform_audits()
            except Exception as e:
                logger.error(f"Audit failed: {e}")
    
    def _get_local_ip(self) -> str:
        """Get local IP address"""
        # Simplified - in production, use proper method
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip