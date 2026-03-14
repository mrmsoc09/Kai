from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from apps.backend.src.core.phase7_prediction_service import Phase7PredictionService


def _queue_item(**overrides):
    base = {
        "id": uuid4(),
        "program_id": uuid4(),
        "scope_target_id": uuid4(),
        "workflow_run_id": uuid4(),
        "workflow_template": "workflow_quick_vuln_sweep",
        "vulnerability_type": "sql_injection_candidate",
        "affected_asset": "api.example.com",
        "affected_endpoint": "/v1/users",
        "parameter": "id",
        "evidence_summary": "output/raw/evidence.json",
        "artifact_ref": "output/raw/evidence.json",
        "confidence_score": 0.9,
        "novelty_score": 0.8,
        "reportability_score": 0.85,
        "duplicate_risk_hint": "LOW",
        "severity_hint": "high",
        "details_json": {"reproduction": "Use payload X in parameter id"},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _signal(**overrides):
    base = {
        "id": uuid4(),
        "program_id": uuid4(),
        "scope_target_id": uuid4(),
        "workflow_run_id": uuid4(),
        "signal_type": "vulnerability_candidate",
        "confidence_score": 0.7,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_phase7_duplicate_risk_scoring_increases_with_occurrences():
    svc = Phase7PredictionService.__new__(Phase7PredictionService)
    low = svc._score_duplicate_risk(  # noqa: SLF001
        _queue_item(duplicate_risk_hint="LOW"),
        prior_occurrences=0,
    )
    high = svc._score_duplicate_risk(  # noqa: SLF001
        _queue_item(duplicate_risk_hint="ELEVATED", novelty_score=0.2),
        prior_occurrences=4,
    )
    assert high["score"] > low["score"]
    assert high["risk_band"] in {"MEDIUM", "HIGH"}


def test_phase7_evidence_completeness_detects_missing_fields():
    svc = Phase7PredictionService.__new__(Phase7PredictionService)
    weak = svc._score_evidence_completeness(  # noqa: SLF001
        _queue_item(
            evidence_summary=None,
            artifact_ref=None,
            affected_endpoint=None,
            details_json={},
            confidence_score=0.2,
        )
    )
    strong = svc._score_evidence_completeness(  # noqa: SLF001
        _queue_item()
    )
    assert weak["score"] < strong["score"]
    assert weak["readiness_state"] in {"INSUFFICIENT", "PARTIAL"}
    assert "evidence_summary" in weak["missing_fields"]


def test_phase7_target_yield_and_recommendation_are_deterministic():
    svc = Phase7PredictionService.__new__(Phase7PredictionService)
    yield_score = svc._derive_target_yield(  # noqa: SLF001
        [
            _signal(signal_type="delta_subdomain"),
            _signal(signal_type="vulnerability_candidate"),
            _signal(signal_type="correlation_strength"),
        ],
        [
            _queue_item(reportability_score=0.8, novelty_score=0.9),
            _queue_item(reportability_score=0.75, novelty_score=0.7),
        ],
    )
    assert 0.0 <= yield_score["yield_score"] <= 100.0
    assert 0.0 <= yield_score["signal_density_score"] <= 1.0

    workflow, action = svc._prediction_recommendation(  # noqa: SLF001
        vulnerability_type="secret_exposure",
        duplicate_risk_score=0.1,
        evidence_completeness_score=0.9,
        reportability_score=0.9,
    )
    assert workflow == "workflow_secret_exposure_scan"
    assert action == "escalate_secret_validation"
