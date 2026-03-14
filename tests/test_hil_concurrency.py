import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from tests.asgi_test_client import ASGITestClient

from apps.backend.src.main import app


pytestmark = pytest.mark.skipif(
    os.getenv("K1_RUN_DB_TESTS", "false").lower() != "true",
    reason="Set K1_RUN_DB_TESTS=true with a real DATABASE_URL to run concurrency tests.",
)


AUTH = {"Authorization": f"Bearer {os.getenv('K1_DEV_TOKEN', 'devtoken')}"}
client = ASGITestClient(app)


def _create_finding():
    body = {
        "program": "demo-program",
        "asset": "app.demo.local",
        "title": "Race condition test finding",
        "description": "Testing duplicate HiL approvals.",
        "severity": "HIGH",
    }
    resp = client.post("/findings/", json=body, headers=AUTH)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _approve(finding_id: str):
    payload = {
        "checklist": {
            "repro_steps": True,
            "http_traces_or_logs": True,
            "poc_or_screencap": True,
            "scope_confirmation": True,
            "impact_rationale": True,
        },
        "notes": "parallel approval attempt",
    }
    return client.post(f"/hil/findings/{finding_id}/approve", json=payload, headers=AUTH)


def test_duplicate_hil_approval_returns_conflict():
    finding_id = _create_finding()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_approve, finding_id) for _ in range(2)]
        responses = [f.result() for f in as_completed(futures)]

    statuses = sorted([r.status_code for r in responses])
    assert statuses == [200, 409], f"unexpected status codes: {statuses}"
