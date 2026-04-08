from __future__ import annotations

from pathlib import Path

import pytest

import apps.backend.src.core.impact_validation_engine as iv_mod
from apps.backend.src.core.impact_validation_engine import validate_impact


@pytest.fixture(autouse=True)
def _isolated_impact_validation_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("K1_IMPACT_VALIDATION_ARTIFACT_DIR", str(tmp_path / "impact_validation"))
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    iv_mod._ENGINE = None
    yield
    iv_mod._ENGINE = None


def _base_finding(vulnerability_type: str) -> dict:
    return {
        "finding_id": "finding-001",
        "target": "api.example.com",
        "vulnerability_type": vulnerability_type,
        "endpoint": "/v1/resource",
        "severity": "high",
        "summary": "Validation sample",
        "description": "Validation sample description",
    }


def test_out_of_scope_is_prevented():
    result = validate_impact(
        _base_finding("idor"),
        scope_metadata={"target": "api.example.com", "in_scope": False},
        mission_id="mission-oos",
        stage_id="impact_test",
        persist=True,
    )
    assert result.scope_compliance_status == "out_of_scope"
    assert result.impact_limited_due_to_scope is True
    assert result.submission_candidate is False
    assert "all_actions_blocked_out_of_scope" in result.blocked_actions


def test_rce_safe_command_enforcement():
    finding = _base_finding("rce")
    finding["impact_probe_commands"] = ["whoami", "id", "cat /etc/passwd", "echo test", "uname -a"]
    result = validate_impact(
        finding,
        scope_metadata={"target": "api.example.com", "in_scope": True},
        mission_id="mission-rce",
        stage_id="impact_test",
        persist=True,
    )
    assert set(result.commands_executed) == {"whoami", "id", "echo test"}
    assert any(item.startswith("blocked_command:cat /etc/passwd") for item in result.blocked_actions)
    assert any(item.startswith("blocked_command:uname -a") for item in result.blocked_actions)


def test_ssrf_safe_endpoint_handling():
    finding = _base_finding("ssrf")
    finding["ssrf_endpoints_tested"] = [
        "/health",
        "/admin",
        "http://127.0.0.1/status",
        "http://169.254.169.254/latest/meta-data",
    ]
    result = validate_impact(
        finding,
        scope_metadata={"target": "api.example.com", "in_scope": True},
        mission_id="mission-ssrf",
        stage_id="impact_test",
        persist=True,
    )
    safe = result.capability_validation_results.get("safe_endpoints_validated", [])
    assert "/health" in safe
    assert "http://127.0.0.1/status" in safe
    assert any(item.startswith("blocked_ssrf_endpoint:") for item in result.blocked_actions)


def test_idor_validation_without_data_abuse():
    finding = _base_finding("idor")
    finding["cross_resource_access"] = True
    result = validate_impact(
        finding,
        baseline_response={"status_code": 403, "body": "unauthorized"},
        exploit_response={"status_code": 200, "body": "other_user profile metadata"},
        scope_metadata={"target": "api.example.com", "in_scope": True},
        mission_id="mission-idor",
        stage_id="impact_test",
        persist=True,
    )
    assert result.capability_validation_results["status"] == "validated"
    assert "read_only_cross_resource_access_check" in result.allowed_actions_taken
    assert "sensitive_record_enumeration_blocked" in result.blocked_actions


def test_impact_statement_generation_correctness():
    finding = _base_finding("injection")
    result = validate_impact(
        finding,
        baseline_response={"status_code": 200, "body": "ok"},
        exploit_response={"status_code": 500, "body": "SQL syntax error near token"},
        scope_metadata={"target": "api.example.com", "in_scope": True},
        mission_id="mission-statement",
        stage_id="impact_test",
        persist=True,
    )
    statement = result.impact_statement
    assert "impact_summary" in statement
    assert "technical_impact" in statement
    assert "business_impact" in statement
    assert statement.get("severity_estimate") in {"low", "medium", "high", "critical"}


def test_unsupported_vulnerability_type_is_not_submission_candidate():
    finding = _base_finding("open_redirect")
    result = validate_impact(
        finding,
        scope_metadata={"target": "api.example.com", "in_scope": True},
        mission_id="mission-unsupported",
        stage_id="impact_test",
        persist=True,
    )
    assert result.capability_validation_results["status"] == "limited"
    assert result.submission_candidate is False
