import hashlib
import hmac
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidTag
import base64
import json
from typing import Tuple, Optional, List

class CryptoUtils:
    @staticmethod
    def generate_key_pair():
        """Generate ECC key pair for peer identity"""
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        
        # Serialize
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return priv_pem, pub_pem
    
    @staticmethod
    def derive_key(password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """Derive encryption key from password"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        return key, salt
    
    @staticmethod
    def encrypt_data(data: bytes, key: bytes) -> dict:
        """Encrypt data using AES-GCM"""
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        encrypted_data = aesgcm.encrypt(nonce, data, None)
        
        return {
            'ciphertext': encrypted_data,
            'nonce': nonce,
            'tag': encrypted_data[-16:]  # GCM tag is appended
        }
    
    @staticmethod
    def decrypt_data(encrypted_obj: dict, key: bytes) -> bytes:
        """Decrypt AES-GCM encrypted data"""
        aesgcm = AESGCM(key)
        ciphertext = encrypted_obj['ciphertext']
        nonce = encrypted_obj['nonce']
        
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    @staticmethod
    def compute_merkle_root(data_chunks: List[bytes]) -> str:
        """Compute Merkle root for data chunks"""
        if not data_chunks:
            return ""
        
        # Hash each chunk
        leaf_hashes = [hashlib.sha256(chunk).digest() for chunk in data_chunks]
        
        # Build Merkle tree
        while len(leaf_hashes) > 1:
            new_level = []
            for i in range(0, len(leaf_hashes), 2):
                left = leaf_hashes[i]
                right = leaf_hashes[i + 1] if i + 1 < len(leaf_hashes) else left
                parent = hashlib.sha256(left + right).digest()
                new_level.append(parent)
            leaf_hashes = new_level
        
        return base64.b64encode(leaf_hashes[0]).decode()
    
    @staticmethod
    def sign_data(data: bytes, private_key_pem: bytes) -> str:
        """Sign data with private key"""
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None
        )
        
        signature = private_key.sign(
            data,
            ec.ECDSA(hashes.SHA256())
        )
        
        return base64.b64encode(signature).decode()
    
    @staticmethod
    def verify_signature(data: bytes, signature: str, public_key_pem: bytes) -> bool:
        """Verify signature with public key"""
        try:
            public_key = serialization.load_pem_public_key(public_key_pem)
            sig_bytes = base64.b64decode(signature)
            
            public_key.verify(
                sig_bytes,
                data,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception:
            return False