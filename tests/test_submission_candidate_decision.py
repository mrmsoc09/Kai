from __future__ import annotations

import os
from pathlib import Path

from apps.backend.src.core.impact_validation_engine import resolve_submission_candidate_decision
from apps.backend.src.main import app
from tests.asgi_test_client import ASGITestClient


AUTH = {"Authorization": f"Bearer {os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')}"}


def test_decision_rejects_when_qualification_missing():
    decision = resolve_submission_candidate_decision(
        evidence_qualification=None,
        impact_validation={"submission_candidate": True, "impact_statement": {"impact_summary": "ok"}},
    )
    assert decision["submission_candidate"] is False
    assert decision["rejection_reason"] == "evidence_qualification_missing"


def test_decision_rejects_when_impact_missing():
    decision = resolve_submission_candidate_decision(
        evidence_qualification={"submission_candidate": True, "evidence_quality_score": 0.9},
        impact_validation=None,
    )
    assert decision["submission_candidate"] is False
    assert decision["rejection_reason"] == "impact_validation_missing"


def test_decision_passes_when_both_layers_pass():
    decision = resolve_submission_candidate_decision(
        evidence_qualification={"submission_candidate": True, "evidence_quality_score": 0.92},
        impact_validation={
            "submission_candidate": True,
            "impact_score": 0.81,
            "impact_statement": {
                "impact_summary": "validated",
                "technical_impact": "validated",
                "business_impact": "validated",
                "severity_estimate": "high",
            },
            "scope_compliance_status": "in_scope",
            "impact_limited_due_to_scope": False,
        },
    )
    assert decision["submission_candidate"] is True
    assert decision["rejection_reason"] is None


def test_decision_rejects_when_impact_score_is_below_threshold():
    decision = resolve_submission_candidate_decision(
        evidence_qualification={"submission_candidate": True, "evidence_quality_score": 0.91},
        impact_validation={
            "submission_candidate": True,
            "impact_score": 0.20,
            "impact_statement": {
                "impact_summary": "weak signal",
                "technical_impact": "limited",
                "business_impact": "limited",
                "severity_estimate": "low",
            },
            "scope_compliance_status": "in_scope",
            "impact_limited_due_to_scope": False,
        },
    )
    assert decision["submission_candidate"] is False
    assert decision["rejection_reason"] == "impact_score_below_threshold"


def test_decision_rejects_when_evidence_quality_below_threshold():
    decision = resolve_submission_candidate_decision(
        evidence_qualification={"submission_candidate": True, "evidence_quality_score": 0.51},
        impact_validation={
            "submission_candidate": True,
            "impact_score": 0.92,
            "impact_statement": {
                "impact_summary": "validated",
                "technical_impact": "validated",
                "business_impact": "validated",
                "severity_estimate": "high",
            },
            "scope_compliance_status": "in_scope",
            "impact_limited_due_to_scope": False,
        },
    )
    assert decision["submission_candidate"] is False
    assert decision["rejection_reason"] == "evidence_quality_below_threshold"


def test_reports_submit_hil_blocks_when_impact_layer_rejects(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))

    run_id = "impact-gate-reject"
    recording_dir = tmp_path / "recordings" / run_id
    recording_dir.mkdir(parents=True, exist_ok=True)
    (recording_dir / "seg_0000.mp4").write_bytes(b"ftypmp42")

    import apps.backend.src.routers.reports as reports_router

    class _FakeResult:
        def __init__(self, payload: dict):
            self._payload = payload

        def to_dict(self):
            return dict(self._payload)

    monkeypatch.setattr(
        reports_router,
        "qualify_evidence",
        lambda *args, **kwargs: _FakeResult(
            {
                "submission_candidate": True,
                "evidence_quality_score": 0.91,
            }
        ),
    )
    monkeypatch.setattr(
        reports_router,
        "validate_impact",
        lambda *args, **kwargs: _FakeResult(
            {
                "submission_candidate": False,
                "scope_reason": "impact_limited_due_to_scope",
                "impact_score": 0.2,
                "impact_statement": {"impact_summary": "limited"},
            }
        ),
    )

    client = ASGITestClient(app)
    response = client.post(
        "/reports/submit_hil",
        json={
            "run_id": run_id,
            "format_id": "google_vrp",
            "hil_approved": True,
            "finding": {"title": "Sample", "target": "api.example.com"},
            "evidence": {},
        },
        headers=AUTH,
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload.get("reason") == "submission_candidate_rejected"
    assert payload.get("rejection_reason") == "impact_limited_due_to_scope"
