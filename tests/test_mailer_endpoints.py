import os, sys
from pathlib import Path
from email.message import EmailMessage

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')
BACKEND_SRC = ROOT / 'k1' / 'apps' / 'backend' / 'src'
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
import main as backend_main  # type: ignore
from fastapi.testclient import TestClient

client = TestClient(backend_main.app)
AUTH = {"Authorization": f"Bearer {os.environ['K1_DEV_TOKEN']}"}

REC_ROOT = ROOT / 'k1' / 'artifacts'
OUTBOX = REC_ROOT / 'submissions' / 'outbox'
SENT = OUTBOX / 'sent'
FOLLOWUPS = OUTBOX / 'followups'

RUN_ID = 'mailer-run-001'
STAKEHOLDER = 'google_vrp'


def test_mailer_archive_no_smtp(tmp_path):
    # Prepare outbox and a simple EML file for the run
    OUTBOX.mkdir(parents=True, exist_ok=True)
    SENT.mkdir(parents=True, exist_ok=True)
    eml_path = OUTBOX / f"{RUN_ID}_{STAKEHOLDER}.eml"
    msg = EmailMessage()
    msg['Subject'] = 'Test Dispatch'
    msg['From'] = 'agent-zero@k1.local'
    msg['To'] = 'vrp@example.com'
    msg.set_content('Body')
    eml_path.write_bytes(msg.as_bytes())

    r = client.post('/mailer/send', json={"run_id": RUN_ID, "stakeholder": STAKEHOLDER}, headers=AUTH)
    assert r.status_code == 200
    j = r.json()
    assert j.get('status') == 'archived'
    archived = Path(j.get('eml'))
    assert archived.exists()
    assert archived.parent == SENT


def test_mailer_followup_prepare(tmp_path):
    FOLLOWUPS.mkdir(parents=True, exist_ok=True)
    r = client.post('/mailer/followup', json={"run_id": RUN_ID, "stakeholder": STAKEHOLDER, "to": "vrp@example.com"}, headers=AUTH)
    assert r.status_code == 200
    j = r.json()
    assert j.get('status') == 'prepared'
    fpath = Path(j.get('eml'))
    assert fpath.exists()
    assert fpath.parent == FOLLOWUPS
