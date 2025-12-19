#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.coordinator.server import start_coordinator

if __name__ == "__main__":
    start_coordinator()