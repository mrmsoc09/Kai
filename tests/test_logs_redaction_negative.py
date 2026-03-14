from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("K1_DEV_TOKEN", "test-token")

try:
    from apps.backend.src.main import app
    from apps.backend.src.core import trace
    from tests.asgi_test_client import ASGITestClient
except Exception as exc:  # pragma: no cover
    pytest.skip(f"backend import failed: {exc}", allow_module_level=True)

client = ASGITestClient(app)


def test_decision_trace_redacts_sensitive_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    run_id = "redact-test"
    entry = {
        "id": "entry-1",
        "gpee_step": "plan",
        "ooda_step": "decide",
        "action": "query apikey=secret",
        "score": {},
        "outcome": "BEGIN RSA PRIVATE KEY should be removed",
        "category": "plan",
        "tags": ["test"],
    }

    trace.append_decision_trace(run_id, entry)
    paths = trace.log_paths(run_id)
    text = Path(paths["decision_trace"]).read_text(encoding="utf-8")

    assert "apikey=" not in text
    assert "BEGIN RSA PRIVATE KEY" not in text
    # tmp_path fixture handles cleanup automatically


def test_evidence_immutable_blocks_update(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    ev_id = f"ev-immu-{uuid.uuid4().hex[:8]}"
    ev = {"id": ev_id, "name": "t", "path": "/evidence/t.log"}
    headers = {"Authorization": f"Bearer {os.environ['K1_DEV_TOKEN']}"}

    r = client.post("/evidence/register", json=ev, headers=headers)
    assert r.status_code == 200

    r2 = client.post("/evidence/finalize", json={"id": ev_id}, headers=headers)
    assert r2.status_code == 200

    r3 = client.post(
        "/evidence/update", json={"id": ev_id, "name": "changed"}, headers=headers
    )
    assert r3.status_code == 409
