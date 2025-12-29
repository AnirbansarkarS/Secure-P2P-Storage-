from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import uvicorn
from typing import List, Optional
import logging
import json

from .models import Base, Peer, FileMetadataDB, AuditLog
from .database import engine, SessionLocal
from ..shared.schemas import (
    PeerInfo, FileMetadata, StorageRequest, 
    ChallengeRequest, ProofResponse
)
from ..shared.crypto import CryptoUtils
from ..shared.config import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="P2P Storage Coordinator")
security = HTTPBearer()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register", response_model=dict)
async def register_peer(peer_info: PeerInfo, db: Session = Depends(get_db)):
    """Register a new peer or update existing peer"""
    try:
        # Check if peer already exists
        existing = db.query(Peer).filter(Peer.peer_id == peer_info.peer_id).first()
        
        if existing:
            # Update existing peer
            existing.ip_address = peer_info.ip_address
            existing.port = peer_info.port
            existing.available_storage = peer_info.available_storage
            existing.reputation = peer_info.reputation
            existing.status = peer_info.status.value
            existing.last_seen = peer_info.last_seen
            existing.capabilities = peer_info.capabilities
        else:
            # Create new peer
            new_peer = Peer(
                peer_id=peer_info.peer_id,
                ip_address=peer_info.ip_address,
                port=peer_info.port,
                public_key=peer_info.public_key,
                available_storage=peer_info.available_storage,
                reputation=peer_info.reputation,
                status=peer_info.status.value,
                last_seen=peer_info.last_seen,
                capabilities=peer_info.capabilities
            )
            db.add(new_peer)
        
        db.commit()
        logger.info(f"Peer {peer_info.peer_id} registered/updated")
        
        return {
            "status": "success",
            "peer_id": peer_info.peer_id,
            "message": "Peer registered successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error registering peer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/file/register", response_model=dict)
async def register_file(
    metadata: FileMetadata,
    db: Session = Depends(get_db)
):
    """Register file metadata"""
    try:
        # Check if file already exists
        existing = db.query(FileMetadataDB).filter(
            FileMetadataDB.file_hash == metadata.file_hash
        ).first()
        
        if existing:
            # Update shard locations
            existing.shard_locations = metadata.shard_locations
        else:
            # Create new file record
            new_file = FileMetadataDB(
                file_hash=metadata.file_hash,
                owner_id="anonymous",  # In production, use authenticated user
                original_name=metadata.original_name,
                total_size=metadata.total_size,
                encrypted_size=metadata.encrypted_size,
                shards_total=metadata.shards_total,
                shards_required=metadata.shards_required,
                shard_hashes=metadata.shard_hashes,
                shard_locations=metadata.shard_locations,
                encryption_scheme=metadata.encryption_scheme,
                expires_at=metadata.expires_at
            )
            db.add(new_file)
        
        db.commit()
        
        return {
            "status": "success",
            "file_hash": metadata.file_hash,
            "message": "File metadata registered"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/file/{file_hash}/locations", response_model=dict)
async def get_file_locations(file_hash: str, db: Session = Depends(get_db)):
    """Get all locations for a file's shards"""
    file_meta = db.query(FileMetadataDB).filter(
        FileMetadataDB.file_hash == file_hash
    ).first()
    
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "file_hash": file_hash,
        "shard_locations": file_meta.shard_locations,
        "shards_required": file_meta.shards_required,
        "shards_total": file_meta.shards_total
    }

@app.get("/peers", response_model=List[dict])
async def list_peers(
    min_reputation: float = 0.0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List available peers with filtering"""
    peers = db.query(Peer).filter(
        Peer.reputation >= min_reputation,
        Peer.status == "online"
    ).limit(limit).all()
    
    return [
        {
            "peer_id": p.peer_id,
            "ip_address": p.ip_address,
            "port": p.port,
            "available_storage": p.available_storage,
            "reputation": p.reputation,
            "last_seen": p.last_seen.isoformat()
        }
        for p in peers
    ]

@app.post("/audit/challenge", response_model=dict)
async def create_challenge(
    request: ChallengeRequest,
    db: Session = Depends(get_db)
):
    """Create a challenge for proof of retrievability"""
    # Store challenge for verification
    # In production, use Redis or similar for temporary storage
    return {
        "challenge_id": CryptoUtils.compute_merkle_root([request.nonce.encode()]),
        "nonce": request.nonce,
        "timestamp": request.timestamp.isoformat()
    }

@app.post("/audit/verify", response_model=dict)
async def verify_proof(
    proof: ProofResponse,
    db: Session = Depends(get_db)
):
    """Verify a proof of retrievability"""
    try:
        # Verify signature
        proof_data = json.dumps({
            "file_hash": proof.file_hash,
            "proof": proof.proof,
            "merkle_root": proof.merkle_root,
            "timestamp": proof.timestamp.isoformat()
        }).encode()
        
        # Get peer's public key
        peer = db.query(Peer).filter(
            Peer.peer_id == proof.signature  # In reality, signature would be separate
        ).first()
        
        if not peer:
            return {"valid": False, "reason": "Peer not found"}
        
        # Verify the proof (simplified)
        # In production, implement proper Merkle proof verification
        
        # Log audit result
        audit_log = AuditLog(
            file_hash=proof.file_hash,
            peer_id=peer.peer_id,
            challenge="stored_challenge",  # Get from storage
            proof=proof.proof,
            is_valid=True
        )
        db.add(audit_log)
        db.commit()
        
        return {"valid": True, "message": "Proof verified"}
    except Exception as e:
        logger.error(f"Error verifying proof: {e}")
        return {"valid": False, "reason": str(e)}

@app.delete("/peer/{peer_id}", response_model=dict)
async def deregister_peer(
    peer_id: str,
    reason: str = "manual",
    db: Session = Depends(get_db)
):
    """Deregister a peer"""
    peer = db.query(Peer).filter(Peer.peer_id == peer_id).first()
    
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")
    
    # Update status
    peer.status = "offline"
    db.commit()
    
    logger.info(f"Peer {peer_id} deregistered: {reason}")
    
    return {
        "status": "success",
        "message": f"Peer {peer_id} deregistered"
    }

def start_coordinator():
    """Start the coordinator server"""
    uvicorn.run(
        app,
        host=config.coordinator.host,
        port=config.coordinator.port,
        log_level="info"
    )

if __name__ == "__main__":
    start_coordinator()