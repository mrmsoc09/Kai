import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')
from apps.backend.src.main import app  # noqa: E402
from fastapi.testclient import TestClient

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ['K1_DEV_TOKEN']}"}


def test_vector_info_upsert_search():
    r = client.get('/vector/info', headers=AUTH)
    assert r.status_code == 200
    j = r.json()
    assert 'backend' in j

    items = [
        {"id": "run-1", "text": "SQLi detected in login endpoint", "meta": {"severity": "high"}},
        {"id": "run-2", "text": "Reflected XSS on search page", "meta": {"severity": "medium"}}
    ]
    r2 = client.post('/vector/upsert', json={"items": items}, headers=AUTH)
    assert r2.status_code == 200
    assert r2.json().get('count') == 2

    r3 = client.post('/vector/search', json={"query": "sql injection login", "top_k": 5, "min_score": 0.1}, headers=AUTH)
    assert r3.status_code == 200
    out = r3.json().get('results')
    assert isinstance(out, list)
    assert any(res.get('id') == 'run-1' for res in out)
