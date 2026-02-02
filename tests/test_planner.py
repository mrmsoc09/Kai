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

def test_planner_plan_safe_and_blocked():
    # Safe planning
    r = client.post('/planner/plan', json={'technique_id': 'TA0043:T1593'}, headers=AUTH)
    assert r.status_code == 200
    j = r.json()
    assert j['ok'] is True and 'plan' in j
    assert j['plan']['risk_category'] in ('safe-plan','blocked')
    # Blocked destructive technique
    r2 = client.post('/planner/plan', json={'technique_id': 'TA0005:T1562.001'}, headers=AUTH)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2['plan']['risk_category'] == 'blocked'
    assert j2['plan']['execution_allowed'] is False


def test_planner_execute_gates():
    # Execution without HIL is denied
    r = client.post('/planner/execute', json={'run_id': 'r1', 'technique_id': 'TA0043:T1595', 'hil_approved': False}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()['result']['reason'] in ('hil_required','execution_disabled_in_plan_mode')
    # Even with HIL, plan-mode denies execution
    r2 = client.post('/planner/execute', json={'run_id': 'r2', 'technique_id': 'TA0043:T1595', 'hil_approved': True}, headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()['result']['ok'] is False

