#!/usr/bin/env python3
"""
Entry point for US Tax Return Preparation Agent
Run this script to start the agent
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import main, demo_mode

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_mode()
    else:
        main()
