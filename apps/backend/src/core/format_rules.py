from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import yaml

ROOT = Path(__file__).resolve().parents[4]
RULES_DIR = ROOT / 'config' / 'report_formats'

# Basic rules per stakeholder; pull from existing Jinja/meta where possible
REQUIRED_FIELDS = {
    'google_vrp': ['title', 'summary', 'impact', 'scope', 'repro', 'mitigation.plan', 'severity'],
    'hackerone': ['title', 'weakness', 'severity', 'asset', 'repro', 'impact', 'mitigation.plan'],
    'bugcrowd': ['title', 'summary', 'vulnerability', 'asset', 'repro', 'impact', 'mitigation.plan'],
    'intigriti': ['title', 'summary', 'vuln_type', 'asset', 'repro', 'impact', 'mitigation.plan'],
    'msrc': ['title', 'product', 'component', 'version', 'repro', 'impact', 'mitigation.plan'],
}

MULTIPLIER_HINTS = {
    'google_vrp': ['repro is deterministic', 'scope explicitly cited', 'minimal data exposure', 'no service degradation', 'mitigation concrete'],
}

def _get(d: Dict[str, Any], path: str):
    cur: Any = d
    for p in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def check_format(stakeholder: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = stakeholder.lower()
    req = REQUIRED_FIELDS.get(st) or REQUIRED_FIELDS.get('google_vrp', [])
    # Build a flat dict of fields from finding/evidence/mitigation
    finding = payload.get('finding') or {}
    evidence = payload.get('evidence') or {}
    mitigation = payload.get('mitigation') or {}
    ctx = { **finding, **{ 'repro': evidence.get('repro') }, 'mitigation': mitigation }
    missing: List[str] = []
    for fld in req:
        if _get(ctx, fld) in (None, '', []):
            missing.append(fld)
    eligible_hints: List[str] = []
    if st in MULTIPLIER_HINTS:
        eligible_hints = MULTIPLIER_HINTS[st]
    return {
        'stakeholder': stakeholder,
        'required': req,
        'missing': missing,
        'ok': len(missing) == 0,
        'multiplier_hints': eligible_hints
    }
