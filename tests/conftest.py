import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure project root on path
sys.path.insert(0, '/a0/usr/projects/main-startup-build/k1')
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
