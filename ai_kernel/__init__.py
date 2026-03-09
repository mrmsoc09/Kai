"""Shim package that exposes ai-kernel modules under a Python-safe name."""

import sys
from pathlib import Path

_ALT_ROOT = Path(__file__).resolve().parents[1] / "ai-kernel"
if _ALT_ROOT.exists():
    sys.path.append(str(_ALT_ROOT))
