from fastapi.testclient import TestClient
from src.main import app
import os

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ.get('K1_DEV_TOKEN', 'devtoken')}"}

def test_docs_index_requires_auth():
    r = client.get('/docs/index')
    assert r.status_code in (401,403)


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


def test_agent0_chat_and_logs_with_auth():
    r = client.post('/agent0/chat', json={"text": "ping"}, headers=AUTH)
    assert r.status_code == 200
    j = r.json()
    assert 'reply' in j
    r2 = client.get('/agent0/logs', headers=AUTH)
    assert r2.status_code == 200
    j2 = r2.json()
    assert 'logs' in j2 and isinstance(j2['logs'], list)


def test_agent0_requires_auth():
    r = client.post('/agent0/chat', json={"text": "noauth"})
    assert r.status_code in (401,403)
