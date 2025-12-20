import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Handles peer discovery and selection"""
    
    def __init__(self, coordinator_url: str, min_reputation: float = 0.5):
        """
        Initialize discovery service
        
        Args:
            coordinator_url: URL of the coordinator server
            min_reputation: Minimum reputation threshold for peer selection
        """
        self.coordinator_url = coordinator_url
        self.min_reputation = min_reputation
        self.known_peers: Dict[str, Dict] = {}
        self.last_discovery = None
        self.discovery_interval = 30  # seconds
        
        logger.info(f"Discovery service initialized: {coordinator_url}")
    
    async def discover_peers(self, session: aiohttp.ClientSession, 
                           min_reputation: float = None) -> List[Dict]:
        """
        Discover peers from coordinator
        
        Args:
            session: aiohttp session
            min_reputation: Optional minimum reputation filter
            
        Returns:
            List of peer information dictionaries
        """
        try:
            min_rep = min_reputation if min_reputation is not None else self.min_reputation
            
            async with session.get(
                f"{self.coordinator_url}/peers",
                params={"min_reputation": min_rep, "limit": 100}
            ) as response:
                if response.status == 200:
                    peers = await response.json()
                    
                    # Update known peers
                    for peer in peers:
                        self.known_peers[peer['peer_id']] = {
                            **peer,
                            'discovered_at': datetime.now()
                        }
                    
                    self.last_discovery = datetime.now()
                    logger.info(f"Discovered {len(peers)} peers")
                    
                    return peers
                else:
                    logger.error(f"Failed to discover peers: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Peer discovery failed: {e}")
            return []
    
    async def find_peers_for_storage(self, session: aiohttp.ClientSession, 
                                    num_peers: int, 
                                    exclude_peers: Set[str] = None) -> List[Dict]:
        """
        Find suitable peers for storing shards
        
        Args:
            session: aiohttp session
            num_peers: Number of peers needed
            exclude_peers: Set of peer IDs to exclude
            
        Returns:
            List of selected peer dictionaries
        """
        try:
            # Discover fresh peer list
            all_peers = await self.discover_peers(session)
            
            if not all_peers:
                logger.warning("No peers available for storage")
                return []
            
            # Filter out excluded peers
            exclude_peers = exclude_peers or set()
            available_peers = [
                p for p in all_peers 
                if p['peer_id'] not in exclude_peers and p['status'] == 'online'
            ]
            
            if len(available_peers) < num_peers:
                logger.warning(f"Only {len(available_peers)} peers available, need {num_peers}")
            
            # Sort by reputation and available storage
            available_peers.sort(
                key=lambda p: (p['reputation'], p['available_storage']),
                reverse=True
            )
            
            # Select top peers with some randomization for load balancing
            if len(available_peers) <= num_peers:
                selected = available_peers
            else:
                # Take top 2x peers and randomly select from them
                top_peers = available_peers[:num_peers * 2]
                selected = random.sample(top_peers, min(num_peers, len(top_peers)))
            
            logger.info(f"Selected {len(selected)} peers for storage")
            return selected
            
        except Exception as e:
            logger.error(f"Failed to find peers for storage: {e}")
            return []
    
    async def find_peers_with_shard(self, session: aiohttp.ClientSession, 
                                   file_hash: str, 
                                   shard_index: int) -> List[str]:
        """
        Find peers that have a specific shard
        
        Args:
            session: aiohttp session
            file_hash: Hash of the file
            shard_index: Index of the shard
            
        Returns:
            List of peer IDs that have the shard
        """
        try:
            async with session.get(
                f"{self.coordinator_url}/file/{file_hash}/locations"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract peer IDs for this shard
                    shard_locations = data.get('shard_locations', {})
                    peer_ids = shard_locations.get(str(shard_index), [])
                    
                    logger.info(f"Found {len(peer_ids)} peers with shard {shard_index}")
                    return peer_ids
                else:
                    logger.error(f"Failed to get shard locations: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to find peers with shard: {e}")
            return []
    
    async def get_peer_info(self, session: aiohttp.ClientSession, 
                          peer_id: str) -> Optional[Dict]:
        """
        Get information about a specific peer
        
        Args:
            session: aiohttp session
            peer_id: ID of the peer
            
        Returns:
            Peer information dictionary or None
        """
        # Check cache first
        if peer_id in self.known_peers:
            cached = self.known_peers[peer_id]
            # Return cached if recent (< 5 minutes old)
            if (datetime.now() - cached['discovered_at']).seconds < 300:
                return cached
        
        # Fetch from coordinator
        try:
            async with session.get(
                f"{self.coordinator_url}/peers",
                params={"limit": 1000}
            ) as response:
                if response.status == 200:
                    peers = await response.json()
                    for peer in peers:
                        if peer['peer_id'] == peer_id:
                            self.known_peers[peer_id] = {
                                **peer,
                                'discovered_at': datetime.now()
                            }
                            return peer
                    
                    logger.warning(f"Peer not found: {peer_id}")
                    return None
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to get peer info: {e}")
            return None
    
    async def monitor_peer_health(self, session: aiohttp.ClientSession, 
                                 peer_id: str, 
                                 peer_url: str) -> bool:
        """
        Check if a peer is healthy/responsive
        
        Args:
            session: aiohttp session
            peer_id: ID of the peer
            peer_url: URL of the peer
            
        Returns:
            True if peer is healthy, False otherwise
        """
        try:
            async with session.get(
                f"{peer_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                is_healthy = response.status == 200
                
                if is_healthy:
                    logger.debug(f"Peer {peer_id[:8]} is healthy")
                else:
                    logger.warning(f"Peer {peer_id[:8]} returned status {response.status}")
                
                return is_healthy
                
        except asyncio.TimeoutError:
            logger.warning(f"Peer {peer_id[:8]} health check timed out")
            return False
        except Exception as e:
            logger.warning(f"Peer {peer_id[:8]} health check failed: {e}")
            return False
    
    def select_best_peers(self, peers: List[Dict], count: int, 
                         strategy: str = 'reputation') -> List[Dict]:
        """
        Select best peers based on strategy
        
        Args:
            peers: List of peer dictionaries
            count: Number of peers to select
            strategy: Selection strategy ('reputation', 'storage', 'random')
            
        Returns:
            List of selected peers
        """
        if not peers:
            return []
        
        if strategy == 'reputation':
            sorted_peers = sorted(peers, key=lambda p: p['reputation'], reverse=True)
        elif strategy == 'storage':
            sorted_peers = sorted(peers, key=lambda p: p['available_storage'], reverse=True)
        elif strategy == 'random':
            sorted_peers = random.sample(peers, len(peers))
        else:
            sorted_peers = peers
        
        return sorted_peers[:count]
    
    def get_cached_peers(self, min_reputation: float = None) -> List[Dict]:
        """
        Get peers from cache
        
        Args:
            min_reputation: Optional minimum reputation filter
            
        Returns:
            List of cached peer dictionaries
        """
        min_rep = min_reputation if min_reputation is not None else self.min_reputation
        
        peers = [
            peer for peer in self.known_peers.values()
            if peer['reputation'] >= min_rep and peer['status'] == 'online'
        ]
        
        return peers
    
    def should_rediscover(self) -> bool:
        """Check if it's time to rediscover peers"""
        if self.last_discovery is None:
            return True
        
        elapsed = (datetime.now() - self.last_discovery).seconds
        return elapsed >= self.discovery_interval
