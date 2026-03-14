import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')
from apps.backend.src.main import app  # noqa: E402
from tests.asgi_test_client import ASGITestClient

client = ASGITestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ['K1_DEV_TOKEN']}"}


def test_validate_requires_sections_and_video():
    payload = {
        "format_id": "google_vrp",
        "finding": {"title":"SQLi","summary":"..","impact":"..","severity":"high","scope":"demo"},
        "evidence": {"repro": "1) ...\n2) ...", "artifacts": {}},
        "mitigation": {"plan":"parameterized queries", "timeline":"ASAP"},
        "run_id": "val-run-001",
        "has_recording": False
    }
    r = client.post('/reports/validate', json=payload, headers=AUTH)
    assert r.status_code == 200
    j = r.json()
    assert j['ok'] is False
    issues = j['result'].get('issues') or []
    assert any(isinstance(it, dict) and it.get('code') == 'screen_recording_missing' for it in issues)

    payload['has_recording'] = True
    r2 = client.post('/reports/validate', json=payload, headers=AUTH)
    assert r2.status_code == 200
    j2 = r2.json()
    issues2 = j2['result'].get('issues') or []
    assert not any(isinstance(it, dict) and it.get('code') == 'screen_recording_missing' for it in issues2)
