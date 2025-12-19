from sqlalchemy import create_engine, Column, String, Integer, DateTime, Float, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

Base = declarative_base()

class Peer(Base):
    __tablename__ = "peers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    peer_id = Column(String, unique=True, nullable=False)
    ip_address = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    public_key = Column(String, nullable=False)
    available_storage = Column(Integer, default=0)
    used_storage = Column(Integer, default=0)
    reputation = Column(Float, default=1.0)
    status = Column(String, default="online")
    last_seen = Column(DateTime, default=datetime.now)
    capabilities = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.now)
    
class FileMetadataDB(Base):
    __tablename__ = "files"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_hash = Column(String, unique=True, nullable=False)
    owner_id = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    total_size = Column(Integer, nullable=False)
    encrypted_size = Column(Integer, nullable=False)
    shards_total = Column(Integer, nullable=False)
    shards_required = Column(Integer, nullable=False)
    shard_hashes = Column(JSON, nullable=False)
    shard_locations = Column(JSON, nullable=False)  # {shard_index: [peer_ids]}
    encryption_scheme = Column(String, default="AES-256-GCM")
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_hash = Column(String, nullable=False)
    peer_id = Column(String, nullable=False)
    challenge = Column(String, nullable=False)
    proof = Column(String, nullable=False)
    is_valid = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.now)