"""Python-safe alias package for modules stored under ``ai-kernel``.

The canonical source tree lives in ``ai-kernel/``. This package exposes that
tree as ``ai_kernel`` so imports like ``ai_kernel.governance`` continue to
work without duplicating module files.
"""

from pathlib import Path


_HERE = Path(__file__).resolve().parent
_ALT_ROOT = _HERE.parent / "ai-kernel"

# Search the canonical ai-kernel tree first for subpackages/modules.
if _ALT_ROOT.exists():
    __path__ = [str(_ALT_ROOT), str(_HERE)]
else:
    __path__ = [str(_HERE)]
