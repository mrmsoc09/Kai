from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, List
import json, time, uuid

ROOT = Path(__file__).resolve().parents[4]
JOBS = ROOT / 'artifacts' / 'jobs.jsonl'
JOBS.parent.mkdir(parents=True, exist_ok=True)


def enqueue(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    job = {
        'id': str(uuid.uuid4()),
        'kind': kind,
        'payload': payload,
        'ts': int(time.time()),
        'state': 'queued'
    }
    with JOBS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(job) + "\n")
    return job


def _read_all() -> List[Dict[str, Any]]:
    if not JOBS.exists():
        return []
    out = []
    with JOBS.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def list_jobs(state: Optional[str] = None) -> List[Dict[str, Any]]:
    jobs = _read_all()
    return [j for j in jobs if (state is None or j.get('state') == state)]
