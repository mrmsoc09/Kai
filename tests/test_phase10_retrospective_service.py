from __future__ import annotations

from types import SimpleNamespace

from apps.backend.src.core.phase10_retrospective_service import Phase10RetrospectiveService


def test_phase10_case_outcome_classification_is_deterministic():
    service = Phase10RetrospectiveService.__new__(Phase10RetrospectiveService)

    submitted = service._classify_case_outcome(  # noqa: SLF001
        SimpleNamespace(status="submitted", closure_reason=None)
    )
    duplicate = service._classify_case_outcome(  # noqa: SLF001
        SimpleNamespace(status="duplicate", closure_reason=None)
    )
    dismissed = service._classify_case_outcome(  # noqa: SLF001
        SimpleNamespace(status="dismissed", closure_reason="false positive")
    )
    unresolved = service._classify_case_outcome(  # noqa: SLF001
        SimpleNamespace(status="triaging", closure_reason=None)
    )

    assert submitted[0] == "reportable_vulnerability"
    assert duplicate[0] == "duplicate_vulnerability"
    assert dismissed[0] == "dismissed_false_positive"
    assert unresolved[0] == "unresolved_stale"


def test_phase10_scoring_modifiers_reward_quality_signal():
    service = Phase10RetrospectiveService.__new__(Phase10RetrospectiveService)
    modifiers = service._derive_scoring_modifiers(  # noqa: SLF001
        workflow_reportability_rate=0.8,
        workflow_noise_rate=0.1,
        target_reportability_rate=0.75,
        target_duplicate_rate=0.1,
        target_yield_score=84.0,
        recommendation_success_rate=0.9,
        alert_noise_rate=0.1,
    )

    assert modifiers["opportunity_multiplier"] > 1.0
    assert modifiers["yield_multiplier"] > 1.0
    assert modifiers["duplicate_risk_multiplier"] < 1.2
    assert modifiers["evidence_multiplier"] > 1.0
    assert isinstance(modifiers["reasoning_summary"], str)


def test_phase10_scoring_modifiers_penalize_noisy_feedback():
    service = Phase10RetrospectiveService.__new__(Phase10RetrospectiveService)
    modifiers = service._derive_scoring_modifiers(  # noqa: SLF001
        workflow_reportability_rate=0.15,
        workflow_noise_rate=0.8,
        target_reportability_rate=0.1,
        target_duplicate_rate=0.7,
        target_yield_score=20.0,
        recommendation_success_rate=0.1,
        alert_noise_rate=0.9,
    )

    assert modifiers["opportunity_multiplier"] < 1.0
    assert modifiers["yield_multiplier"] < 1.0
    assert modifiers["duplicate_risk_multiplier"] > 1.0
    assert modifiers["evidence_multiplier"] <= 1.0
