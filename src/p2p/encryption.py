import os
import hashlib
from typing import Optional, Tuple
from ..shared.crypto import CryptoUtils
import logging

logger = logging.getLogger(__name__)


class FileEncryptor:
    """Handles file encryption and decryption with password-based keys"""
    
    def __init__(self):
        self.crypto = CryptoUtils()
    
    def encrypt_file(self, file_data: bytes, password: str) -> Tuple[bytes, dict]:
        """
        Encrypt file data with password-based encryption
        
        Args:
            file_data: Raw file bytes
            password: User password for encryption
            
        Returns:
            Tuple of (encrypted_data, metadata_dict)
        """
        try:
            # Derive encryption key from password
            key, salt = self.crypto.derive_key(password)
            
            # Encrypt the file data
            encrypted_obj = self.crypto.encrypt_data(file_data, key)
            
            # Create metadata
            metadata = {
                'salt': salt,
                'nonce': encrypted_obj['nonce'],
                'original_size': len(file_data),
                'encrypted_size': len(encrypted_obj['ciphertext']),
                'encryption_scheme': 'AES-256-GCM'
            }
            
            logger.info(f"Encrypted file: {len(file_data)} bytes -> {len(encrypted_obj['ciphertext'])} bytes")
            
            return encrypted_obj['ciphertext'], metadata
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt_file(self, encrypted_data: bytes, password: str, metadata: dict) -> bytes:
        """
        Decrypt file data with password
        
        Args:
            encrypted_data: Encrypted file bytes
            password: User password for decryption
            metadata: Encryption metadata (salt, nonce, etc.)
            
        Returns:
            Decrypted file bytes
        """
        try:
            # Derive the same key from password and salt
            key, _ = self.crypto.derive_key(password, metadata['salt'])
            
            # Reconstruct encrypted object
            encrypted_obj = {
                'ciphertext': encrypted_data,
                'nonce': metadata['nonce']
            }
            
            # Decrypt
            decrypted_data = self.crypto.decrypt_data(encrypted_obj, key)
            
            logger.info(f"Decrypted file: {len(encrypted_data)} bytes -> {len(decrypted_data)} bytes")
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Decryption failed - incorrect password or corrupted data")
    
    def encrypt_chunks(self, file_data: bytes, password: str, chunk_size: int = 1024 * 1024) -> Tuple[list, dict]:
        """
        Encrypt large files in chunks for memory efficiency
        
        Args:
            file_data: Raw file bytes
            password: User password
            chunk_size: Size of each chunk (default 1MB)
            
        Returns:
            Tuple of (list of encrypted chunks, metadata)
        """
        try:
            # Derive encryption key
            key, salt = self.crypto.derive_key(password)
            
            encrypted_chunks = []
            chunk_metadata = []
            
            # Process file in chunks
            for i in range(0, len(file_data), chunk_size):
                chunk = file_data[i:i + chunk_size]
                encrypted_obj = self.crypto.encrypt_data(chunk, key)
                
                encrypted_chunks.append(encrypted_obj['ciphertext'])
                chunk_metadata.append({
                    'nonce': encrypted_obj['nonce'],
                    'size': len(encrypted_obj['ciphertext'])
                })
            
            metadata = {
                'salt': salt,
                'chunks': chunk_metadata,
                'original_size': len(file_data),
                'chunk_size': chunk_size,
                'encryption_scheme': 'AES-256-GCM-CHUNKED'
            }
            
            logger.info(f"Encrypted file in {len(encrypted_chunks)} chunks")
            
            return encrypted_chunks, metadata
            
        except Exception as e:
            logger.error(f"Chunked encryption failed: {e}")
            raise
    
    def decrypt_chunks(self, encrypted_chunks: list, password: str, metadata: dict) -> bytes:
        """
        Decrypt chunked file data
        
        Args:
            encrypted_chunks: List of encrypted chunk bytes
            password: User password
            metadata: Encryption metadata
            
        Returns:
            Decrypted file bytes
        """
        try:
            # Derive key
            key, _ = self.crypto.derive_key(password, metadata['salt'])
            
            decrypted_data = b''
            
            # Decrypt each chunk
            for i, encrypted_chunk in enumerate(encrypted_chunks):
                chunk_meta = metadata['chunks'][i]
                encrypted_obj = {
                    'ciphertext': encrypted_chunk,
                    'nonce': chunk_meta['nonce']
                }
                
                decrypted_chunk = self.crypto.decrypt_data(encrypted_obj, key)
                decrypted_data += decrypted_chunk
            
            logger.info(f"Decrypted {len(encrypted_chunks)} chunks")
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Chunked decryption failed: {e}")
            raise ValueError("Decryption failed - incorrect password or corrupted data")
    
    @staticmethod
    def compute_file_hash(file_data: bytes) -> str:
        """Compute SHA-256 hash of file"""
        return hashlib.sha256(file_data).hexdigest()
    
    def encrypt_metadata(self, metadata: dict, password: str) -> bytes:
        """
        Encrypt metadata for privacy
        
        Args:
            metadata: Metadata dictionary
            password: Password for encryption
            
        Returns:
            Encrypted metadata bytes
        """
        import json
        metadata_json = json.dumps(metadata).encode()
        encrypted, _ = self.encrypt_file(metadata_json, password)
        return encrypted
    
    def decrypt_metadata(self, encrypted_metadata: bytes, password: str, salt: bytes, nonce: bytes) -> dict:
        """
        Decrypt metadata
        
        Args:
            encrypted_metadata: Encrypted metadata bytes
            password: Password for decryption
            salt: Salt used in encryption
            nonce: Nonce used in encryption
            
        Returns:
            Decrypted metadata dictionary
        """
        import json
        metadata = {
            'salt': salt,
            'nonce': nonce
        }
        decrypted = self.decrypt_file(encrypted_metadata, password, metadata)
        return json.loads(decrypted.decode())
