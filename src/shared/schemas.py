from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

class PeerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SUSPECT = "suspect"

class ShardInfo(BaseModel):
    shard_hash: str
    index: int
    peer_id: str
    size_bytes: int
    timestamp: datetime

class FileMetadata(BaseModel):
    file_hash: str
    original_name: str
    total_size: int
    encrypted_size: int
    shards_total: int
    shards_required: int
    shard_hashes: List[str]
    shard_locations: Dict[int, List[str]]  # shard_index -> [peer_ids]
    encryption_scheme: str = "AES-256-GCM"
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

class PeerInfo(BaseModel):
    peer_id: str
    ip_address: str
    port: int
    public_key: str
    available_storage: int
    reputation: float = 1.0
    status: PeerStatus = PeerStatus.ONLINE
    last_seen: datetime = Field(default_factory=datetime.now)
    capabilities: List[str] = Field(default_factory=list)

class StorageRequest(BaseModel):
    file_data: bytes
    file_name: str
    encryption_key: Optional[str] = None
    redundancy: int = 4
    expires_in_hours: Optional[int] = None

class ChallengeRequest(BaseModel):
    file_hash: str
    nonce: str
    timestamp: datetime

class ProofResponse(BaseModel):
    file_hash: str
    proof: str
    merkle_root: str
    timestamp: datetime
    signature: str