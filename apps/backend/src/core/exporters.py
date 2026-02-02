from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import orjson, json

ROOT = Path(__file__).resolve().parents[4]
RECS = ROOT / 'artifacts' / 'recordings'
ING = ROOT / 'artifacts' / 'ingest'
ING.mkdir(parents=True, exist_ok=True)


def export_recordings_metadata(run_id: str) -> Dict[str, Any]:
    d = RECS / run_id
    if not d.exists():
        return {'ok': False, 'error': 'run_missing'}
    out = ING / f'{run_id}_recordings.ndjson'
    count = 0
    with out.open('wb') as f:
        for m in sorted(d.glob('seg_*.json')):
            try:
                obj = json.loads(m.read_text())
                f.write(orjson.dumps(obj)+b"\n")
                count += 1
            except Exception:
                pass
    return {'ok': True, 'file': str(out), 'count': count}
