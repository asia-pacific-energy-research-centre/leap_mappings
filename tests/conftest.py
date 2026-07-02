"""Test bootstrap for leap_mappings.

Add the repo root to sys.path so pytest can import ``codebase`` from a clean
checkout without requiring callers to set PYTHONPATH manually.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
