"""
Root conftest.py to ensure proper Python path configuration for tests.
This file ensures that the 'src' module can be imported from tests.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print(f"Project root added to Python path: {project_root}")

