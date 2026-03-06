from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict


SLA_HOURS_BY_STATE = {
    "ready_for_submission": 24,
    "packaged": 12,
    "dispatched": 72,
    "acknowledged": 72,
    "in_triage": 168,
    "needs_info": 24,
    "resubmitted": 72,
}

NEXT_ACTION_PROMPTS = {
    "drafted": "Finalize report evidence and mitigation plan for submission readiness.",
    "ready_for_submission": "Package and dispatch the submission to start external triage.",
    "packaged": "Dispatch the prepared package to outbox and record submission event.",
    "dispatched": "Monitor acknowledgements and update triage state when stakeholder responds.",
    "acknowledged": "Track triage progress and capture any follow-up questions in linked thread.",
    "in_triage": "Monitor SLA and prepare supporting artifacts for potential clarification requests.",
    "needs_info": "Respond with requested evidence and transition to resubmitted.",
    "resubmitted": "Track stakeholder feedback and update to triage/decision state.",
    "accepted": "Record payout expectations and move to reconciliation workflow.",
    "rejected": "Capture rejection rationale for reflective learning and quality gates.",
    "withdrawn": "Close workflow and archive reasoning/evidence for audit.",
}


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def compute_submission_sla(state_obj: Dict[str, Any]) -> Dict[str, Any]:
    state = str(state_obj.get("state") or "drafted")
    history = list(state_obj.get("history") or [])
    last_event = history[-1] if history else {}
    last_transition_at = _parse_dt(last_event.get("timestamp") or state_obj.get("updated_at"))
    now = datetime.now(timezone.utc)
    sla_hours = SLA_HOURS_BY_STATE.get(state)

    if sla_hours is None:
        return {
            "state": state,
            "last_transition_at": last_transition_at.isoformat(),
            "due_at": None,
            "is_overdue": False,
            "remaining_seconds": None,
            "sla_hours": None,
            "next_action_prompt": NEXT_ACTION_PROMPTS.get(state, "Continue workflow with policy-compliant updates."),
        }

    due_at = last_transition_at + timedelta(hours=sla_hours)
    remaining = int((due_at - now).total_seconds())
    return {
        "state": state,
        "last_transition_at": last_transition_at.isoformat(),
        "due_at": due_at.isoformat(),
        "is_overdue": remaining < 0,
        "remaining_seconds": remaining,
        "sla_hours": sla_hours,
        "next_action_prompt": NEXT_ACTION_PROMPTS.get(state, "Follow up and keep workflow moving."),
    }
