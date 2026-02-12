
import json, time
from pathlib import Path
from typing import Dict, Any, List
from .metrics import compute_run_metrics, aggregate_metrics

ROOT = Path(__file__).resolve().parents[4]
ART_DORK = ROOT / "artifacts" / "dork_runs"
ART_DORK.mkdir(parents=True, exist_ok=True)

def run_dir(run_id: str) -> Path:
    d = ART_DORK / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def write_run_record(run_id: str, run: Dict[str, Any]) -> str:
    d = run_dir(run_id)
    p = d / "run.json"
    run.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    run["metrics"] = compute_run_metrics(run)
    p.write_text(json.dumps(run, ensure_ascii=False, indent=2))
    return str(p)

def load_all_runs() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for sub in sorted(ART_DORK.glob('*/run.json')):
        try:
            out.append(json.loads(sub.read_text()))
        except Exception:
            pass
    return out

def aggregate_all() -> Dict[str, Any]:
    return aggregate_metrics(load_all_runs())

from typing import Optional

def load_run(run_id: str) -> Optional[Dict[str, Any]]:
    p = (ROOT / "artifacts" / "dork_runs" / run_id / "run.json")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def append_finding(run_id: str, finding: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append a finding to a run record (creates run if missing).
    """
    run = load_run(run_id) or {"id": run_id, "findings": []}
    fins = run.setdefault("findings", [])
    fins.append(finding)
    save_run_record(run_id, run)
    return run

# alias for explicit save
save_run_record = write_run_record
