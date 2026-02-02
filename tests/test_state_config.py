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


def test_state_config_reports_providers_and_vector(tmp_path):
    os.environ['K1_MODEL_GEMINI'] = 'gpt-2.5'
    r = client.get('/state/config', headers=AUTH)
    assert r.status_code == 200
    j = r.json()
    assert 'providers' in j and 'vector' in j
    models = j['providers']['models']
    assert models['gemini']['name'] == 'gpt-2.5'
    assert models['gemini']['valid'] is False
    assert j['vector']['backend'] in ('memory', 'pgvector')
    assert isinstance(j['vector']['mem_count'], int)
