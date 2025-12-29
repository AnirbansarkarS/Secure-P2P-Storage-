#!/usr/bin/env python3
"""Test script to diagnose peer node startup issues"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

async def test_peer_startup():
    try:
        print("=" * 60)
        print("Testing P2P Peer Node Startup")
        print("=" * 60)
        
        # Test imports
        print("\n[1/5] Testing imports...")
        from src.p2p.node import P2PNode
        from src.shared.config import config
        print("✓ Imports successful")
        
        # Test identity creation
        print(f"\n[2/5] Creating node instance...")
        print(f"  Data directory: {config.node.data_dir}")
        node = P2PNode()
        print(f"✓ Node created")
        print(f"  Peer ID: {node.state.peer_id}")
        print(f"  Public Key Length: {len(node.state.public_key)} bytes")
        
        # Test storage manager
        print(f"\n[3/5] Testing storage manager...")
        available = node.storage_manager.get_available_space()
        stats = node.storage_manager.get_storage_stats()
        print(f"✓ Storage manager operational")
        print(f"  Available space: {available / (1024**3):.2f} GB")
        print(f"  Total capacity: {stats['max_gb']} GB")
        
        # Test coordinator connection
        print(f"\n[4/5] Testing coordinator connection...")
        print(f"  Coordinator URL: {node.coordinator_url}")
        
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{node.coordinator_url}/peers", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        peers = await response.json()
                        print(f"✓ Coordinator reachable")
                        print(f"  Current peers: {len(peers)}")
                    else:
                        print(f"⚠ Coordinator returned status {response.status}")
        except asyncio.TimeoutError:
            print("✗ Coordinator connection timeout")
            print("  Make sure coordinator is running: python scripts/start_coordinator.py")
            return False
        except Exception as e:
            print(f"✗ Coordinator connection failed: {e}")
            print("  Make sure coordinator is running: python scripts/start_coordinator.py")
            return False
        
        # Test peer registration
        print(f"\n[5/5] Testing peer registration...")
        try:
            await node._register_with_coordinator(config.node.port)
            print("✓ Peer registration test completed")
        except Exception as e:
            print(f"✗ Registration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Keep coordinator running in one terminal")
        print("  2. Run: python scripts/start_node.py")
        print("  3. Open web UI to see active peers")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_peer_startup())
    sys.exit(0 if success else 1)
