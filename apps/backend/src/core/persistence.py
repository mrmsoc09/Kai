from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[5]
REPORTS = ROOT / 'artifacts' / 'reports'
REPORTS.mkdir(parents=True, exist_ok=True)


def persist_submission(run_id: str, content: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    d = REPORTS / run_id
    d.mkdir(parents=True, exist_ok=True)
    rpt = d / 'report.md'
    mfp = d / 'meta.json'
    # Stamp meta
    meta = dict(meta or {})
    meta.setdefault('run_id', run_id)
    meta['saved_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    # Write
    rpt.write_text(content or '')
    mfp.write_text(json.dumps(meta, indent=2))
    from core.merkle import compute_merkle_tree
    info = {'dir': str(d), 'report': str(rpt), 'meta': str(mfp)}
    try:
        m = compute_merkle_tree(d)
        info['merkle'] = m
        # Persist merkle tree into the run directory for audit
        (d / 'merkle.json').write_text(json.dumps(m, indent=2))
    except Exception:
        pass
    return info
