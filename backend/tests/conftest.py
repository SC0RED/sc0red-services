"""Root test configuration."""

import sys
from pathlib import Path

# Ensure backend/src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
