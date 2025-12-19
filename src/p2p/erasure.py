import zfec
import hashlib
import base64
from typing import List, Tuple
import os

class ErasureCoder:
    def __init__(self, required_shards: int = 8, total_shards: int = 20):
        self.required_shards = required_shards
        self.total_shards = total_shards
        self.fec = zfec.Encoder(required_shards, total_shards)
        self.decoder = zfec.Decoder(required_shards, total_shards)
    
    def encode(self, data: bytes) -> List[bytes]:
        """Encode data into shards using Reed-Solomon"""
        # Pad data to be evenly divisible by required_shards
        padding_length = (self.required_shards - (len(data) % self.required_shards)) % self.required_shards
        padded_data = data + b'\0' * padding_length
        
        # Split into required_shards pieces
        chunk_size = len(padded_data) // self.required_shards
        chunks = [
            padded_data[i * chunk_size:(i + 1) * chunk_size]
            for i in range(self.required_shards)
        ]
        
        # Encode into total_shards pieces
        shards = self.fec.encode(chunks)
        
        return shards
    
    def decode(self, shards: List[Tuple[int, bytes]]) -> bytes:
        """Decode shards back to original data"""
        # Sort shards by index and filter out None (missing) shards
        valid_shards = [(i, shard) for i, shard in shards if shard is not None]
        
        if len(valid_shards) < self.required_shards:
            raise ValueError(f"Need at least {self.required_shards} shards, got {len(valid_shards)}")
        
        # Decode
        indices, shard_data = zip(*valid_shards)
        decoded_chunks = self.decoder.decode(shard_data, indices)
        
        # Combine chunks
        reconstructed = b''.join(decoded_chunks)
        
        # Remove padding
        reconstructed = reconstructed.rstrip(b'\0')
        
        return reconstructed
    
    @staticmethod
    def compute_shard_hash(shard_data: bytes) -> str:
        """Compute hash of a shard"""
        return base64.b64encode(hashlib.sha256(shard_data).digest()).decode()
    
    @staticmethod
    def compute_file_hash(file_data: bytes) -> str:
        """Compute hash of entire file"""
        return base64.b64encode(hashlib.sha256(file_data).digest()).decode()

class ShardManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.shards_dir = os.path.join(data_dir, "shards")
        os.makedirs(self.shards_dir, exist_ok=True)
    
    def save_shard(self, file_hash: str, shard_index: int, shard_data: bytes) -> str:
        """Save a shard to disk"""
        shard_hash = ErasureCoder.compute_shard_hash(shard_data)
        filename = f"{file_hash}_{shard_index}_{shard_hash}.shard"
        filepath = os.path.join(self.shards_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(shard_data)
        
        return shard_hash
    
    def load_shard(self, file_hash: str, shard_index: int) -> bytes:
        """Load a shard from disk"""
        pattern = f"{file_hash}_{shard_index}_"
        for filename in os.listdir(self.shards_dir):
            if filename.startswith(pattern):
                with open(os.path.join(self.shards_dir, filename), 'rb') as f:
                    return f.read()
        raise FileNotFoundError(f"Shard {shard_index} for file {file_hash} not found")
    
    def delete_shard(self, file_hash: str, shard_index: int):
        """Delete a shard"""
        pattern = f"{file_hash}_{shard_index}_"
        for filename in os.listdir(self.shards_dir):
            if filename.startswith(pattern):
                os.remove(os.path.join(self.shards_dir, filename))
                return
    
    def list_shards(self) -> List[dict]:
        """List all stored shards"""
        shards = []
        for filename in os.listdir(self.shards_dir):
            if filename.endswith('.shard'):
                parts = filename[:-6].split('_')
                if len(parts) >= 3:
                    shards.append({
                        'file_hash': parts[0],
                        'shard_index': int(parts[1]),
                        'shard_hash': parts[2]
                    })
        return shards