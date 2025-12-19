from dataclasses import dataclass
from typing import List, Optional
import yaml
import os

@dataclass
class CoordinatorConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    secret_key: str = "your-secret-key-change-in-production"
    database_url: str = "sqlite:///./coordinator.db"
    max_peers: int = 1000
    heartbeat_timeout: int = 60  # seconds

@dataclass
class NodeConfig:
    data_dir: str = "./p2p_data"
    port: int = 9000
    max_storage_gb: int = 10
    redundancy_factor: int = 4
    shards_total: int = 20
    shards_required: int = 8
    peer_discovery_interval: int = 30  # seconds
    audit_interval: int = 300  # seconds

@dataclass
class Config:
    coordinator: CoordinatorConfig
    node: NodeConfig
    bootstrap_peers: List[str] = None
    
    @classmethod
    def from_yaml(cls, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(
            coordinator=CoordinatorConfig(**data.get('coordinator', {})),
            node=NodeConfig(**data.get('node', {})),
            bootstrap_peers=data.get('bootstrap_peers', [])
        )

config = Config(
    coordinator=CoordinatorConfig(),
    node=NodeConfig(),
    bootstrap_peers=[]
)