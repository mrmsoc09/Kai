# Root-level proxy to enable `import main` in tests and CLIs
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Ensure repo root and backend src are importable so 'apps.backend.src' and 'core' are found
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_SRC = ROOT / 'apps' / 'backend' / 'src'
if BACKEND_SRC.exists() and str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

# Import FastAPI app from package module
from apps.backend.src.main import app  # noqa: E402

__all__ = ['app']
