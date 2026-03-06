from __future__ import annotations

import pytest

from apps.backend.src.core.submission_lifecycle import (
    SubmissionLifecycleError,
    get_submission_state,
    transition_submission_state,
)


def test_submission_lifecycle_valid_transitions(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_SUBMISSION_STATE_DIR", str(tmp_path / "states"))
    run_id = "run-abc"
    initial = get_submission_state(run_id)
    assert initial["state"] == "drafted"

    s1 = transition_submission_state(run_id, "ready_for_submission", actor="test")
    assert s1["state"] == "ready_for_submission"

    s2 = transition_submission_state(run_id, "packaged", actor="test")
    assert s2["state"] == "packaged"

    s3 = transition_submission_state(run_id, "dispatched", actor="test")
    assert s3["state"] == "dispatched"
    assert len(s3["history"]) == 3


def test_submission_lifecycle_invalid_transition(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_SUBMISSION_STATE_DIR", str(tmp_path / "states"))
    run_id = "run-invalid"

    with pytest.raises(SubmissionLifecycleError):
        transition_submission_state(run_id, "accepted", actor="test")
