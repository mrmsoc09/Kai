import os
import sys
from pathlib import Path

os.environ.setdefault("K1_TEST_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("K1_DEV_TOKEN", "devtoken")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("K1_ENABLE_BOOTSTRAP_AUTH", "true")

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
