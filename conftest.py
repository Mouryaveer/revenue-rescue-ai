"""
Root conftest.py — adds project root to sys.path so all modules resolve correctly.
"""

import sys
from pathlib import Path

# Ensure project root is on the path for all test suites
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "backend"))
