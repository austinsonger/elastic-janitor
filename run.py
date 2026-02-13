#!/usr/bin/env python3
"""
Launcher script for Elastic Janitor.
Run this from within the janitor/ directory.
"""
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Now import and run
from janitor.menus import main

if __name__ == "__main__":
    main()

