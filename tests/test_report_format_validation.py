import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')
BACKEND_SRC = ROOT / 'k1' / 'apps' / 'backend' / 'src'
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
import main as backend_main  # type: ignore
from fastapi.testclient import TestClient

client = TestClient(backend_main.app)
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
    assert 'screen_recording_missing' in j['result']['issues']

    payload['has_recording'] = True
    r2 = client.post('/reports/validate', json=payload, headers=AUTH)
    assert r2.status_code == 200
    j2 = r2.json()
    assert 'screen_recording_missing' not in j2['result']['issues']
