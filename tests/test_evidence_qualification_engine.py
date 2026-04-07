from __future__ import annotations

import os
from pathlib import Path

import pytest

import apps.backend.src.core.evidence_qualification_engine as eq_mod
from apps.backend.src.core.evidence_qualification_engine import qualify_evidence
from apps.backend.src.main import app
from tests.asgi_test_client import ASGITestClient


AUTH = {"Authorization": f"Bearer {os.environ.setdefault('K1_DEV_TOKEN', 'devtoken')}"}


@pytest.fixture(autouse=True)
def _isolate_qualification_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    artifact_dir = tmp_path / "evidence_qualification"
    index_path = artifact_dir / "duplicate_index.json"
    monkeypatch.setenv("K1_EVIDENCE_QUALIFICATION_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("K1_EVIDENCE_QUALIFICATION_INDEX_PATH", str(index_path))
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    eq_mod._ENGINE = None
    yield
    eq_mod._ENGINE = None


def _base_finding() -> dict:
    return {
        "finding_id": "f-001",
        "target": "app.example.com",
        "vulnerability_type": "xss",
        "severity": "high",
        "summary": "Reflected XSS in search endpoint",
        "endpoint": "/search",
        "parameter": "q",
        "confidence_score": 0.91,
        "validation_evidence": ["request/response pair captured"],
    }


def test_high_quality_finding_passes_qualification():
    result = qualify_evidence(
        _base_finding(),
        exploit_results=[
            {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
            {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
            {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
        ],
        scope_metadata={"target": "app.example.com", "in_scope": True},
        mission_id="mission-high-quality",
        stage_id="qualification_test",
        persist=True,
        update_duplicate_history=False,
    )
    assert result.submission_candidate is True
    assert result.rejection_reason is None
    assert result.evidence_quality_score >= 0.75


def test_unstable_exploit_is_rejected():
    result = qualify_evidence(
        _base_finding(),
        exploit_results=[
            {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
            {"status": "failed", "request_signature": "req-b", "response_signature": "res-b"},
            {"status": "failed", "request_signature": "req-c", "response_signature": "res-c"},
        ],
        scope_metadata={"target": "app.example.com", "in_scope": True},
        mission_id="mission-unstable",
        stage_id="qualification_test",
        persist=True,
        update_duplicate_history=False,
    )
    assert result.submission_candidate is False
    assert result.rejection_reason == "unstable_exploit_behavior"


def test_out_of_scope_is_rejected():
    result = qualify_evidence(
        _base_finding(),
        exploit_results=[
            {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
            {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
        ],
        scope_metadata={"target": "app.example.com", "in_scope": False},
        mission_id="mission-oos",
        stage_id="qualification_test",
        persist=True,
        update_duplicate_history=False,
    )
    assert result.submission_candidate is False
    assert result.rejection_reason == "out_of_scope"


def test_duplicate_findings_escalate_risk():
    finding = _base_finding()
    latest = None
    for idx in range(6):
        latest = qualify_evidence(
            finding,
            exploit_results=[
                {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
                {"status": "success", "request_signature": "req-a", "response_signature": "res-a"},
            ],
            scope_metadata={"target": "app.example.com", "in_scope": True},
            mission_id=f"mission-dup-{idx}",
            stage_id="qualification_test",
            persist=True,
            update_duplicate_history=True,
        )
    assert latest is not None
    assert latest.duplicate_risk_score >= 0.80
    assert latest.submission_candidate is False
    assert latest.rejection_reason == "high_duplicate_risk"


def test_reports_submit_hil_has_no_qualification_bypass(tmp_path: Path):
    run_id = "eq-bypass-check"
    recording_dir = tmp_path / "recordings" / run_id
    recording_dir.mkdir(parents=True, exist_ok=True)
    (recording_dir / "seg_0000.mp4").write_bytes(b"ftypmp42")

    client = ASGITestClient(app)
    response = client.post(
        "/reports/submit_hil",
        json={
            "run_id": run_id,
            "format_id": "google_vrp",
            "hil_approved": True,
            "finding": {
                "title": "Thin evidence sample",
                "target": "api.example.com",
                "severity": "medium",
                "in_scope": True,
            },
            "evidence": {},
        },
        headers=AUTH,
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload.get("reason") == "evidence_qualification_rejected"

