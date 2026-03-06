from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from .reflective_learning import OutcomeRecord, record_outcome


class SubmissionLifecycleError(Exception):
    pass


DEFAULT_STATE = "drafted"
TERMINAL_STATES = {"accepted", "rejected", "withdrawn"}
ALLOWED_TRANSITIONS = {
    "drafted": {"ready_for_submission", "withdrawn"},
    "ready_for_submission": {"packaged", "withdrawn"},
    "packaged": {"dispatched", "withdrawn"},
    "dispatched": {"acknowledged", "needs_info", "rejected", "accepted"},
    "acknowledged": {"in_triage", "needs_info", "accepted", "rejected"},
    "in_triage": {"needs_info", "accepted", "rejected"},
    "needs_info": {"resubmitted", "rejected", "withdrawn"},
    "resubmitted": {"dispatched", "in_triage", "accepted", "rejected"},
    "accepted": set(),
    "rejected": set(),
    "withdrawn": set(),
}


def _state_dir() -> Path:
    root = Path(os.getenv("K1_SUBMISSION_STATE_DIR", "artifacts/submissions/states")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _state_path(run_id: str) -> Path:
    return _state_dir() / f"{run_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_submission_state(run_id: str) -> Dict[str, Any]:
    path = _state_path(run_id)
    if not path.exists():
        return {
            "run_id": run_id,
            "state": DEFAULT_STATE,
            "history": [],
            "updated_at": _now(),
        }
    return json.loads(path.read_text(encoding="utf-8"))


def transition_submission_state(
    run_id: str,
    to_state: str,
    *,
    actor: str = "system",
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if to_state not in ALLOWED_TRANSITIONS:
        raise SubmissionLifecycleError(f"unknown state: {to_state}")

    current = get_submission_state(run_id)
    from_state = str(current.get("state") or DEFAULT_STATE)

    if from_state in TERMINAL_STATES:
        raise SubmissionLifecycleError(f"cannot transition terminal state: {from_state}")

    if to_state != from_state and to_state not in ALLOWED_TRANSITIONS.get(from_state, set()):
        raise SubmissionLifecycleError(f"invalid transition: {from_state} -> {to_state}")

    event = {
        "from_state": from_state,
        "to_state": to_state,
        "timestamp": _now(),
        "actor": actor,
        "metadata": metadata or {},
    }
    history = list(current.get("history") or [])
    history.append(event)

    updated = {
        "run_id": run_id,
        "state": to_state,
        "history": history,
        "updated_at": _now(),
    }
    _state_path(run_id).write_text(json.dumps(updated, indent=2), encoding="utf-8")

    # Reflective learning updates only on terminal judgement states.
    if to_state in {"accepted", "rejected"}:
        meta = metadata or {}
        outcome = str(meta.get("outcome") or to_state)
        try:
            record_outcome(
                OutcomeRecord(
                    run_id=run_id,
                    tactic_id=str(meta.get("tactic_id") or "workflow_submission_v1"),
                    outcome=outcome,
                    evidence_quality=float(meta.get("evidence_quality") or 0.5),
                    cost_cents=float(meta.get("cost_cents") or 0.0),
                    latency_ms=float(meta.get("latency_ms") or 0.0),
                    operator_feedback=str(meta.get("operator_feedback") or ""),
                )
            )
        except Exception:
            # Learning must never block transition flow.
            pass
    return updated
