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
REC_ROOT = ROOT / 'k1' / 'artifacts' / 'recordings'
RUN_ID = 'submit-run-001'

def setup_recording():
    d = REC_ROOT / RUN_ID
    d.mkdir(parents=True, exist_ok=True)
    (d / 'seg_0000.mp4').write_bytes(b'ftypmp42')

def test_submit_hil_persists_artifacts(tmp_path):
    setup_recording()
    dummy_rec = f"artifacts/recordings/{RUN_ID}/seg_0000.mp4"
    mitigation = "Revoke exposed credentials and rotate keys."
    resp = client.post(f"/reports/validate", json={"run_id": RUN_ID, "format_id": "google_vrp", "finding": {"title": "Test"}}, headers=AUTH)
    assert resp.status_code in (200, 201)
    res = client.post(f"/reports/submit_hil", json={}, headers=AUTH)
    assert res.status_code == 409
    assert "recording" in res.json()["reason"]
    res = client.post(f"/reports/submit_hil", json={"recording_path": dummy_rec}, headers=AUTH)
    assert res.status_code == 409
    assert "mitigation" in res.json()["reason"]
    res = client.post(f"/reports/submit_hil", json={"mitigation_plan": mitigation}, headers=AUTH)
    assert res.status_code == 409
    assert "recording" in res.json()["reason"]
    res = client.post(f"/reports/submit_hil", json={"mitigation_plan": mitigation, "recording_path": dummy_rec}, headers=AUTH)
    assert res.status_code == 200
    assert res.json()["ok"] is True