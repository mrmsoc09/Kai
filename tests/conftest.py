import os
import sys
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Ensure repository root on path (avoid environment-specific hardcoded paths)
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from apps.backend.src.main import app  # noqa: E402

@pytest.fixture(scope='session')
def auth_headers():
    os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')
    return {'Authorization': f"Bearer {os.environ['K1_DEV_TOKEN']}"}

@pytest.fixture(scope='session')
def client(auth_headers):
    c = TestClient(app)
    # Set default auth header for all requests in tests
    c.headers.update(auth_headers)
    return c
