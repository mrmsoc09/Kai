from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.backend.src.core.submission_sla import compute_submission_sla


def test_submission_sla_overdue_detection():
    ts = (datetime.now(timezone.utc) - timedelta(hours=80)).isoformat()
    state = {
        "run_id": "r1",
        "state": "dispatched",
        "history": [{"timestamp": ts, "to_state": "dispatched"}],
        "updated_at": ts,
    }
    result = compute_submission_sla(state)
    assert result["state"] == "dispatched"
    assert result["is_overdue"] is True
    assert result["next_action_prompt"]


def test_submission_sla_non_timed_state():
    now = datetime.now(timezone.utc).isoformat()
    state = {"run_id": "r2", "state": "accepted", "history": [], "updated_at": now}
    result = compute_submission_sla(state)
    assert result["due_at"] is None
    assert result["is_overdue"] is False
