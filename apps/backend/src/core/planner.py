from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime, timezone

SAFE_TECHNIQUES = {
    # Passive recon and safe assessment techniques (illustrative)
    'TA0043:T1595': 'Active Scanning (plan-mode only)',
    'TA0043:T1595.001': 'Scans for Vulnerabilities (plan-mode only)',
    'TA0043:T1590': 'Gather Victim Identity Information (OSINT)',
    'TA0043:T1593': 'Search Open Websites/Domains (OSINT)',
    'TA0043:T1046': 'Network Service Scanning (simulation)',
}

# techniques we will never execute; only produce high-level muted plans
BLOCKED_TECHNIQUES = {
    'TA0005:T1562',      # Impair Defenses (and sub-techniques)
    'TA0005:T1562.001',  # Disable or Modify Tools
    'TA0010:T1041',      # Exfil over C2
    'TA0010:T1048',      # Exfil over Alt Channels
}

NON_STANDARD_EXFIL = {
    'T1048.003': {
        'name': 'Exfiltration Over Unencrypted/Non-Standard Port (Webhook Variant - Muted)',
        'note': 'Planning/education only. No execution. Use dummy endpoints and redact secrets.'
    }
}

class PlannerError(Exception):
    pass


def is_blocked(technique_id: str) -> bool:
    tid = (technique_id or '').upper().strip()
    return any(tid.startswith(b) for b in BLOCKED_TECHNIQUES)


def mitre_plan(technique_id: str) -> Dict[str, Any]:
    """
    Produce a muted (non-executable) plan for the requested technique.
    Plans are informational only and categorized for safety. Execution requires HiL and is disabled for destructive classes.
    """
    if not technique_id:
        raise PlannerError('technique_id required')
    tid = technique_id.upper().strip()

    plan: Dict[str, Any] = {
        'technique_id': tid,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'risk_category': 'blocked' if is_blocked(tid) else 'safe-plan',
        'execution_allowed': False,
        'hil_required': True,
        'steps': [],
        'notes': [],
    }

    if is_blocked(tid):
        plan['notes'].append('This technique class is destructive or policy-restricted. Execution is permanently disabled. Provided plan is educational only.')
        plan['steps'] = [
            {'id': 'doc-1', 'action': 'Review stakeholder scope and policies', 'type': 'documentation'},
            {'id': 'doc-2', 'action': 'Consider alternative, non-destructive assessment methods', 'type': 'documentation'},
        ]
        return plan

    # Safe/plan-mode examples
    if tid in SAFE_TECHNIQUES:
        plan['steps'] = [
            {'id': 'prep-1', 'action': 'Load program scope from /programs/get/<slug>', 'type': 'plan'},
            {'id': 'osint-1', 'action': 'Enumerate domain assets via passive DNS and certificate transparency logs (plan-mode)', 'type': 'plan'},
            {'id': 'analysis-1', 'action': 'Correlate exposures with CVE/CWE heuristics (no exploit)', 'type': 'plan'},
            {'id': 'report-1', 'action': 'Draft report sections (title, summary, impact, scope, repro in lab, mitigation)', 'type': 'plan'},
            {'id': 'gate-1', 'action': 'Submit for HiL approval before any further action', 'type': 'gate'},
        ]
        plan['notes'].append(SAFE_TECHNIQUES[tid])
    else:
        # generic fallback plan
        plan['steps'] = [
            {'id': 'prep-1', 'action': 'Map assets and scope (read-only sources)', 'type': 'plan'},
            {'id': 'intel-1', 'action': 'Collect public indicators and historical signals', 'type': 'plan'},
            {'id': 'analysis-1', 'action': 'Score potential risks; prepare non-invasive validations', 'type': 'plan'},
            {'id': 'gate-1', 'action': 'HiL gate prior to any execution', 'type': 'gate'},
        ]
        plan['notes'].append('Generic safe planning profile applied.')

    # Add muted exfil pattern description when requested technique matches 1048.003
    if tid.endswith('T1048.003'):
        ex = NON_STANDARD_EXFIL['T1048.003']
        plan['notes'].append(f"Muted exfil pattern: {ex['name']} - {ex['note']}")
        plan['steps'].append({'id': 'exfil-educ', 'action': 'Document webhook-based exfil simulation with dummy endpoint (no data sent)', 'type': 'documentation'})

    return plan


def execute_plan(run_id: str, technique_id: str, hil_approved: bool) -> Dict[str, Any]:
    """
    Execution is blocked by default. If technique is blocked (destructive), execution always denies.
    Otherwise, still deny in this build (plan-mode only). This function exists to assert gates.
    """
    if not run_id:
        raise PlannerError('run_id required')
    tid = (technique_id or '').upper().strip()
    if is_blocked(tid):
        return {'ok': False, 'reason': 'blocked_technique', 'executed': False}
    if not hil_approved:
        return {'ok': False, 'reason': 'hil_required', 'executed': False}
    # In this platform build, external execution is disabled by policy; return deny
    return {'ok': False, 'reason': 'execution_disabled_in_plan_mode', 'executed': False}
