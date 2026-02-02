from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[4]
LOGS = ROOT / 'artifacts' / 'logs'


def _utc_parts():
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}", f"{now.month:02d}", f"{now.day:02d}"


def run_dir(run_id: str, create: bool = True) -> Path:
    y, m, d = _utc_parts()
    dpath = LOGS / y / m / d / 'runs' / run_id
    if create:
        dpath.mkdir(parents=True, exist_ok=True)
    return dpath


def log_decision(run_id: str, event: str, data: Dict[str, Any]) -> Path:
    d = run_dir(run_id, True)
    fp = d / 'decision_trace.jsonl'
    rec = {'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'event': event, 'data': data}
    with fp.open('a') as f:
        f.write(json.dumps(rec) + '\n')
    return fp


def write_summary(run_id: str, text: str) -> Path:
    d = run_dir(run_id, True)
    fp = d / 'summary.md'
    fp.write_text(text)
    return fp


def read_decision_trace(run_id: str) -> List[Dict[str, Any]]:
    d = run_dir(run_id, False)
    fp = d / 'decision_trace.jsonl'
    out: List[Dict[str, Any]] = []
    if not fp.exists():
        return out
    with fp.open() as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def read_summary(run_id: str) -> str:
    d = run_dir(run_id, False)
    fp = d / 'summary.md'
    return fp.read_text() if fp.exists() else ''
