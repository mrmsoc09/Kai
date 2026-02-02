
from typing import Dict, Any
from datetime import datetime

def _to_ts(s: str | None) -> float | None:
    if not s: return None
    try:
        return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
    except Exception:
        return None

def compute_run_metrics(run: Dict[str, Any]) -> Dict[str, Any]:
    findings = run.get('findings', []) or []
    validated = len([f for f in findings if f.get('status') == 'VALIDATED'])
    invalidated = len([f for f in findings if f.get('status') == 'INVALID'])
    t_start = _to_ts(run.get('timestamp'))
    t_signal = _to_ts(run.get('first_signal_at'))
    t_valid = _to_ts(run.get('first_validated_at'))
    ttfs = (t_signal - t_start) if (t_start and t_signal and t_signal >= t_start) else None
    ttv = (t_valid - t_start) if (t_start and t_valid and t_valid >= t_start) else None
    chain_candidates = len(run.get('planned_queries', []) or [])
    art = run.get('artifacts', {}) or {}
    expected = ['audit_bundle_path']
    present = sum(1 for k in expected if art.get(k))
    ecr = present / len(expected) if expected else 0.0
    return {
        'validated_findings_count': validated,
        'invalidated_findings_count': invalidated,
        'time_to_first_signal': ttfs,
        'time_to_validated': ttv,
        'chain_candidate_count': chain_candidates,
        'evidence_completeness_ratio': round(ecr, 3)
    }

def aggregate_metrics(runs: list[dict[str, Any]]) -> Dict[str, Any]:
    agg = {
        'runs': len(runs),
        'validated_total': 0,
        'invalidated_total': 0,
        'avg_chain_candidates': 0.0,
        'avg_evidence_completeness_ratio': 0.0
    }
    if not runs:
        return agg
    ecs = []
    ccs = []
    for r in runs:
        m = r.get('metrics') or {}
        agg['validated_total'] += int(m.get('validated_findings_count') or 0)
        agg['invalidated_total'] += int(m.get('invalidated_findings_count') or 0)
        ccs.append(int(m.get('chain_candidate_count') or 0))
        ecs.append(float(m.get('evidence_completeness_ratio') or 0.0))
    agg['avg_chain_candidates'] = round(sum(ccs)/len(ccs), 2)
    agg['avg_evidence_completeness_ratio'] = round(sum(ecs)/len(ecs), 3)
    return agg
