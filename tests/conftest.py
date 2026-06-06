# conftest.py
import sys
from pathlib import Path

# Add the outer aafs directory to python path so aafs package is importable
aafs_outer_dir = Path(__file__).parent.parent / "aafs"
if str(aafs_outer_dir) not in sys.path:
    sys.path.insert(0, str(aafs_outer_dir))
