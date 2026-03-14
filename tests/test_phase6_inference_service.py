from __future__ import annotations

from types import SimpleNamespace

from apps.backend.src.core.recon_inference_service import ReconInferenceService


def _signal(signal_type: str, *, confidence: float = 0.6, severity: str | None = None):
    return SimpleNamespace(
        signal_type=signal_type,
        confidence_score=confidence,
        severity_hint=severity,
    )


def _queue_item(*, reportability: float, duplicate_hint: str = "LOW"):
    return SimpleNamespace(
        reportability_score=reportability,
        duplicate_risk_hint=duplicate_hint,
    )


def test_score_target_signals_prefers_secret_scan():
    svc = ReconInferenceService.__new__(ReconInferenceService)
    scoring = svc._score_target_signals(  # noqa: SLF001
        [
            _signal("delta_endpoint"),
            _signal("vulnerability_candidate", confidence=0.8, severity="high"),
            _signal("delta_secret", confidence=0.9),
        ],
        queue_items=[_queue_item(reportability=0.8)],
        program_config={"reward_metadata": {"max_reward_usd": 5000}},
    )
    assert scoring["recommended_workflow"] == "workflow_secret_exposure_scan"
    assert scoring["opportunity_score"] > 0
    assert scoring["target_priority_score"] > 0


def test_score_target_signals_vuln_validation_path():
    svc = ReconInferenceService.__new__(ReconInferenceService)
    scoring = svc._score_target_signals(  # noqa: SLF001
        [
            _signal("vulnerability_candidate", confidence=0.8, severity="high"),
            _signal("vulnerability_candidate", confidence=0.7, severity="medium"),
            _signal("vulnerability_candidate", confidence=0.65, severity="high"),
            _signal("correlation_strength", confidence=0.7),
        ],
        queue_items=[_queue_item(reportability=0.7)],
        program_config=None,
    )
    assert scoring["recommended_workflow"] == "workflow_quick_vuln_sweep"
    assert scoring["next_best_action"] == "schedule_vuln_validation"


def test_score_target_signals_duplicate_risk_reduces_score():
    svc = ReconInferenceService.__new__(ReconInferenceService)
    low_dup = svc._score_target_signals(  # noqa: SLF001
        [_signal("delta_endpoint"), _signal("correlation_strength")],
        queue_items=[_queue_item(reportability=0.5, duplicate_hint="LOW")],
        program_config=None,
    )
    high_dup = svc._score_target_signals(  # noqa: SLF001
        [_signal("delta_endpoint"), _signal("correlation_strength")],
        queue_items=[_queue_item(reportability=0.5, duplicate_hint="ELEVATED")],
        program_config=None,
    )
    assert high_dup["opportunity_score"] < low_dup["opportunity_score"]
