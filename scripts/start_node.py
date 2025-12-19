#!/usr/bin/env python3
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.p2p.node import P2PNode

async def main():
    node = P2PNode()
    await node.start()

if __name__ == "__main__":
    asyncio.run(main())