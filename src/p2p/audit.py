import asyncio
import aiohttp
import logging
import hashlib
import secrets
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..shared.crypto import CryptoUtils

logger = logging.getLogger(__name__)


class AuditService:
    """Handles proof-of-retrievability auditing"""
    
    def __init__(self, coordinator_url: str, audit_interval: int = 300):
        self.coordinator_url = coordinator_url
        self.audit_interval = audit_interval
        self.crypto = CryptoUtils()
        self.audit_history = []
        self.last_audit = None
        logger.info(f"Audit service initialized (interval: {audit_interval}s)")
    
    async def create_challenge(self, session: aiohttp.ClientSession,
                              file_hash: str, peer_id: str) -> Optional[Dict]:
        """Create a challenge for a peer to prove they have a file"""
        try:
            nonce = secrets.token_hex(32)
            challenge = {
                'file_hash': file_hash,
                'peer_id': peer_id,
                'nonce': nonce,
                'timestamp': datetime.now().isoformat()
            }
            
            async with session.post(
                f"{self.coordinator_url}/challenge/create", json=challenge
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Created challenge for peer {peer_id[:8]}")
                    return result
                return None
        except Exception as e:
            logger.error(f"Challenge creation failed: {e}")
            return None
    
    async def respond_to_challenge(self, challenge: Dict,
                                  shard_data: bytes,
                                  private_key: bytes) -> Dict:
        """Respond to an audit challenge"""
        proof_input = challenge['nonce'].encode() + shard_data
        proof_hash = hashlib.sha256(proof_input).hexdigest()
        merkle_root = hashlib.sha256(shard_data).hexdigest()
        signature = self.crypto.sign_data(proof_hash.encode(), private_key)
        
        return {
            'file_hash': challenge['file_hash'],
            'proof': proof_hash,
            'merkle_root': merkle_root,
            'timestamp': datetime.now().isoformat(),
            'signature': signature
        }
    
    async def verify_proof(self, session: aiohttp.ClientSession,
                          proof: Dict, public_key: bytes) -> bool:
        """Verify a proof-of-retrievability response"""
        try:
            is_valid_signature = self.crypto.verify_signature(
                proof['proof'].encode(), proof['signature'], public_key
            )
            
            if not is_valid_signature:
                logger.error("Invalid signature in proof")
                return False
            
            async with session.post(
                f"{self.coordinator_url}/challenge/verify", json=proof
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('valid', False)
                return False
        except Exception as e:
            logger.error(f"Proof verification failed: {e}")
            return False
    
    async def audit_peer(self, session: aiohttp.ClientSession,
                        peer_id: str, peer_url: str, file_hash: str) -> bool:
        """Audit a peer to verify they still have a file"""
        try:
            challenge = await self.create_challenge(session, file_hash, peer_id)
            if not challenge:
                return False
            
            async with session.post(
                f"{peer_url}/audit/challenge", json=challenge,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    proof = await response.json()
                    peer_info = await self._get_peer_info(session, peer_id)
                    if not peer_info:
                        return False
                    
                    public_key = peer_info['public_key'].encode()
                    is_valid = await self.verify_proof(session, proof, public_key)
                    
                    self.audit_history.append({
                        'peer_id': peer_id,
                        'file_hash': file_hash,
                        'timestamp': datetime.now(),
                        'passed': is_valid
                    })
                    return is_valid
                return False
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return False
    
    async def _get_peer_info(self, session: aiohttp.ClientSession,
                           peer_id: str) -> Optional[Dict]:
        """Get peer information from coordinator"""
        try:
            async with session.get(
                f"{self.coordinator_url}/peers", params={"limit": 1000}
            ) as response:
                if response.status == 200:
                    peers = await response.json()
                    for peer in peers:
                        if peer['peer_id'] == peer_id:
                            return peer
                return None
        except Exception as e:
            logger.error(f"Failed to get peer info: {e}")
            return None
    
    def get_audit_stats(self) -> Dict:
        """Get audit statistics"""
        if not self.audit_history:
            return {'total_audits': 0, 'success_rate': 0, 'last_audit': None}
        
        total = len(self.audit_history)
        passed = sum(1 for a in self.audit_history if a['passed'])
        
        return {
            'total_audits': total,
            'passed': passed,
            'failed': total - passed,
            'success_rate': (passed / total) * 100 if total > 0 else 0,
            'last_audit': self.last_audit.isoformat() if self.last_audit else None
        }
