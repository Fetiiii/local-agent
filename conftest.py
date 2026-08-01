"""Make the project root importable for pytest and direct test runs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
