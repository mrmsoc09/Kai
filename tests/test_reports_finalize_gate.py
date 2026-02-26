import os
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')
from apps.backend.src.main import app  # noqa: E402

from fastapi.testclient import TestClient

client = TestClient(app)
AUTH = {"Authorization": f"Bearer {os.environ['K1_DEV_TOKEN']}"}
REC_ROOT = REPO_ROOT / 'artifacts' / 'recordings'
RUN_ID = 'pytest-run-001'
RUN_DIR = REC_ROOT / RUN_ID

def test_finalize_requires_mitigation_plan_and_recording(tmp_path):
    # Clean run dir
    if RUN_DIR.exists():
        for f in RUN_DIR.iterdir():
            f.unlink()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    rec_path = f"artifacts/recordings/{RUN_ID}/seg_0000.mp4"
    (RUN_DIR / 'seg_0000.mp4').write_bytes(b'ftypmp42')
    mitig = "Immediate patch deployment scheduled"
    resp = client.post(f"/reports/render", json={"run_id": RUN_ID, "format_id": "google_vrp", "finding": {"title": "Test"}}, headers=AUTH)
    assert resp.status_code in (200, 201)
    # POST failing cases
    r = client.post(f"/reports/finalize", json={}, headers=AUTH)
    assert r.status_code == 409
    assert "mitigation" in r.json()["reason"] and "recording" in r.json()["reason"]
    r = client.post(f"/reports/finalize", json={"recording_path": rec_path}, headers=AUTH)
    assert r.status_code == 409
    assert "mitigation" in r.json()["reason"]
    r = client.post(f"/reports/finalize", json={"mitigation_plan": mitig}, headers=AUTH)
    assert r.status_code == 409
    assert "recording" in r.json()["reason"]
    r = client.post(f"/reports/finalize", json={"mitigation_plan": mitig, "recording_path": rec_path}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["ok"] is True
