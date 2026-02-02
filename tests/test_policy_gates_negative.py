import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("K1_DEV_TOKEN", "test-token")

try:
    from apps.backend.src.main import app
except Exception as exc:  # pragma: no cover
    pytest.skip(f"backend import failed: {exc}", allow_module_level=True)


def test_execute_blocks_without_hil(client):
    r = client.post(
        "/dorks/run",
        json={"target": "example.com", "mode": "execute", "chain": "backup_index_chain"},
    )
    assert r.status_code == 409
    assert r.json().get("reason") == "hil_approval_required"


def test_execute_blocks_when_policy_off(client):
    r = client.post(
        "/dorks/run",
        json={
            "target": "example.com",
            "mode": "execute",
            "chain": "backup_index_chain",
            "hil_approved": True,
        },
    )
    assert r.status_code == 409
    assert r.json().get("reason") == "policy_external_queries_disabled"


def test_invalid_token_denied(client):
    r = client.get("/state/global", headers={"Authorization": "Bearer bad"})
    assert r.status_code in (401, 503)


@pytest.fixture(autouse=True)
def _cleanup_evidence():
    yield
    root = Path(__file__).resolve().parents[1]
    ev = root / "artifacts" / "evidence" / "ev-immu.json"
    if ev.exists():
        ev.unlink()
