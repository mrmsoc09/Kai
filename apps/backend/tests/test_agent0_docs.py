"""
Docs endpoint tests.

Note: The agent0 chat/logs endpoints were removed when KAISON AI replaced the legacy system.
Only the /docs/* endpoint tests remain here.
"""
from fastapi.testclient import TestClient
from src.main import app
import os

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ.get('K1_DEV_TOKEN', 'devtoken')}"}


def test_docs_index_requires_auth():
    r = client.get('/docs/index')
    assert r.status_code in (401, 403)


def test_docs_index_ok_and_get():
    r = client.get('/docs/index', headers=AUTH)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    # Try to fetch one known doc if present
    target = None
    for it in items:
        if it['path'].endswith('DEV_STACK_RUN.md'):
            target = it['path']
            break
    if target:
        r2 = client.get(f'/docs/get?path={target}', headers=AUTH)
        assert r2.status_code == 200
        assert 'docker' in r2.text.lower() or len(r2.text) > 10


def test_agent0_endpoints_no_longer_exist():
    """Verify agent0 chat/logs endpoints have been removed (replaced with KAISON AI)."""
    r_chat = client.post('/agent0/chat', json={"text": "ping"}, headers=AUTH)
    assert r_chat.status_code == 404, f"Expected 404 (removed), got {r_chat.status_code}"
    r_logs = client.get('/agent0/logs', headers=AUTH)
    assert r_logs.status_code == 404, f"Expected 404 (removed), got {r_logs.status_code}"
