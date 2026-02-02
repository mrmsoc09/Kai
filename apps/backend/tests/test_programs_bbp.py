import os, sys, json
from fastapi.testclient import TestClient

# Ensure import path
sys.path.insert(0, '/a0/usr/projects/main-startup-build/k1')

# Set dev token for auth like other tests
os.environ['K1_DEV_TOKEN'] = os.environ.get('K1_DEV_TOKEN', 'devtoken')

from apps.backend.src.main import app

client = TestClient(app)
AUTH = {'Authorization': f"Bearer {os.environ['K1_DEV_TOKEN']}"}


def test_bbp_top10_ok():
    r = client.get('/programs/bbp/top10', headers=AUTH)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'programs' in data and isinstance(data['programs'], list)
    assert data.get('count', 0) > 0


def test_bbp_top50_validation_available():
    r = client.get('/programs/bbp/top50/validation', headers=AUTH)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'available' in data


def test_bbp_queue_plan_creates_run():
    # Queue and auto-run a plan-mode run (no external calls)
    r = client.post('/programs/bbp/queue', headers=AUTH, json={'target': 'example.com', 'mode': 'plan', 'auto': True})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get('queued') is True
    # Confirm runs list increments/contains latest
    r2 = client.get('/runs', headers=AUTH)
    assert r2.status_code == 200
    runs = r2.json()
    assert isinstance(runs, list) and len(runs) >= 1
