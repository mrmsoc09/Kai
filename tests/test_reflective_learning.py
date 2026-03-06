from __future__ import annotations

from apps.backend.src.core.reflective_learning import OutcomeRecord, record_outcome, summarize_reflection


def test_reflective_learning_updates_weights_with_bounds(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_REFLECTIVE_STATE_PATH", str(tmp_path / "reflective.json"))
    for _ in range(50):
        record_outcome(
            OutcomeRecord(
                run_id="run-1",
                tactic_id="tactic-a",
                outcome="accepted",
                evidence_quality=1.0,
                cost_cents=0,
                latency_ms=0,
                operator_feedback="great",
            )
        )
    summary = summarize_reflection(limit=5)
    w = summary["tactic_weights"]["tactic-a"]
    assert 0.1 <= w <= 2.0


def test_submission_transition_triggers_reflective_update(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_SUBMISSION_STATE_DIR", str(tmp_path / "states"))
    monkeypatch.setenv("K1_REFLECTIVE_STATE_PATH", str(tmp_path / "reflective.json"))
    from apps.backend.src.core.submission_lifecycle import transition_submission_state

    transition_submission_state("run-2", "ready_for_submission")
    transition_submission_state("run-2", "packaged")
    transition_submission_state("run-2", "dispatched")
    transition_submission_state(
        "run-2",
        "accepted",
        metadata={
            "tactic_id": "submission_tactic_v1",
            "evidence_quality": 0.9,
            "cost_cents": 200,
            "latency_ms": 1000,
            "operator_feedback": "accepted by triage",
        },
    )
    summary = summarize_reflection(limit=10)
    assert "submission_tactic_v1" in summary["tactic_weights"]
    assert len(summary["recent_changes"]) >= 1
