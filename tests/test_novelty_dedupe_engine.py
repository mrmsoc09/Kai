from __future__ import annotations

import json
from pathlib import Path

import pytest

import apps.backend.src.core.novelty_dedupe_engine as nd_mod
from apps.backend.src.core.finding_router import FindingRouter, FindingRoute
from apps.backend.src.core.novelty_dedupe_engine import evaluate_novelty_dedupe


@pytest.fixture(autouse=True)
def _isolated_novelty_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    artifact_dir = tmp_path / "novelty_dedupe"
    monkeypatch.setenv("K1_NOVELTY_DEDUPE_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("K1_NOVELTY_DEDUPE_STATE_PATH", str(artifact_dir / "state.json"))
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    nd_mod._ENGINE = None
    yield
    nd_mod._ENGINE = None


def _intel_payload(match: float = 0.9, similarity: float = 0.9, source: str = "searchsploit") -> dict:
    return {
        "known_pattern_match_score": match,
        "exploit_similarity_score": similarity,
        "matched_intelligence_ids": ["id-1"],
        "matched_sources": [source],
        "reference_sources": [source],
    }


def _base_finding(**overrides) -> dict:
    payload = {
        "finding_id": "f-001",
        "target": "api.example.com",
        "vulnerability_type": "sql_injection",
        "endpoint": "/api/v1/users/123",
        "parameter": "id",
        "summary": "SQL syntax error in response",
    }
    payload.update(overrides)
    return payload


def test_similar_findings_cluster_together():
    first = evaluate_novelty_dedupe(
        _base_finding(finding_id="f-a"),
        vulnerability_intelligence=_intel_payload(),
        impact_validation={"impact_score": 0.55},
        submission_decision={"submission_candidate": True},
        mission_id="m1",
        stage_id="s1",
        persist=True,
        update_history=True,
    )
    second = evaluate_novelty_dedupe(
        _base_finding(finding_id="f-b", endpoint="/api/v1/users/124"),
        vulnerability_intelligence=_intel_payload(),
        impact_validation={"impact_score": 0.56},
        submission_decision={"submission_candidate": True},
        mission_id="m1",
        stage_id="s1",
        persist=True,
        update_history=True,
    )
    assert first.duplicate_cluster_key == second.duplicate_cluster_key


def test_materially_different_findings_separate_clusters():
    sqli = evaluate_novelty_dedupe(
        _base_finding(finding_id="f-sqli"),
        vulnerability_intelligence=_intel_payload(match=0.85, similarity=0.8),
        impact_validation={"impact_score": 0.55},
        submission_decision={"submission_candidate": True},
        mission_id="m2",
        stage_id="s2",
        persist=True,
        update_history=True,
    )
    logic = evaluate_novelty_dedupe(
        _base_finding(
            finding_id="f-logic",
            vulnerability_type="business_logic",
            endpoint="/api/v3/reconcile/workflow/token/approve",
            parameter="workflow_token",
            summary="State transition bypass with non-standard workflow token reuse",
        ),
        vulnerability_intelligence=_intel_payload(match=0.1, similarity=0.05, source="local_seed"),
        impact_validation={"impact_score": 0.8},
        submission_decision={"submission_candidate": True},
        mission_id="m2",
        stage_id="s2",
        persist=True,
        update_history=True,
    )
    assert sqli.duplicate_cluster_key != logic.duplicate_cluster_key


def test_high_overlap_low_novelty_is_suppressed_from_default_hil_view():
    for idx in range(6):
        result = evaluate_novelty_dedupe(
            _base_finding(finding_id=f"f-sup-{idx}"),
            vulnerability_intelligence=_intel_payload(match=0.96, similarity=0.92),
            impact_validation={"impact_score": 0.45},
            submission_decision={"submission_candidate": True},
            mission_id="m3",
            stage_id="s3",
            persist=True,
            update_history=True,
        )
    assert result.suppression_recommendation == "suppress_from_default_hil_view"
    assert result.duplicate_likelihood_score >= 0.78
    assert result.novelty_score < 0.42


def test_high_novelty_finding_remains_visible():
    result = evaluate_novelty_dedupe(
        _base_finding(
            finding_id="f-novel",
            vulnerability_type="business_logic",
            endpoint="/api/v9/internal/reconciliation/approval/nonce/workflow",
            parameter="approval_nonce",
            summary="Cross-step approval token replay creates non-obvious workflow bypass",
        ),
        vulnerability_intelligence=_intel_payload(match=0.05, similarity=0.02, source="local_seed"),
        impact_validation={"impact_score": 0.8},
        submission_decision={"submission_candidate": True},
        mission_id="m4",
        stage_id="s4",
        persist=True,
        update_history=True,
    )
    assert result.suppression_recommendation == "none"
    assert result.novelty_priority in {"high", "medium"}


def test_suppressed_findings_are_retrievable_and_not_deleted(tmp_path: Path):
    result = evaluate_novelty_dedupe(
        _base_finding(finding_id="f-persist"),
        vulnerability_intelligence=_intel_payload(match=0.95, similarity=0.9),
        impact_validation={"impact_score": 0.4},
        submission_decision={"submission_candidate": True},
        mission_id="m5",
        stage_id="s5",
        persist=True,
        update_history=True,
    )
    assert result.artifact_path
    artifact_path = Path(result.artifact_path)
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload.get("decision_id") == result.decision_id
    assert payload.get("finding")
    mission_log = tmp_path / "novelty_dedupe" / "m5" / "mission_log.jsonl"
    assert mission_log.exists()
    assert mission_log.read_text(encoding="utf-8").strip()


@pytest.mark.asyncio
async def test_default_hil_queue_filters_suppressed_but_retrievable():
    router = FindingRouter()
    suppressed = {
        "suppression_recommendation": "suppress_from_default_hil_view",
        "novelty_score": 0.2,
        "duplicate_likelihood_score": 0.9,
    }
    visible = {
        "suppression_recommendation": "none",
        "novelty_score": 0.8,
        "duplicate_likelihood_score": 0.2,
    }
    first = await router.route_finding(
        target_domain="api.example.com",
        vulnerability_type="sql_injection",
        endpoint="/api/v1/users/1",
        cvss_score=8.5,
        severity="high",
        confidence_score=0.9,
        submission_candidate=True,
        novelty_dedupe=suppressed,
    )
    second = await router.route_finding(
        target_domain="api.example.com",
        vulnerability_type="business_logic",
        endpoint="/api/v9/internal/reconcile/workflow",
        cvss_score=8.1,
        severity="high",
        confidence_score=0.9,
        submission_candidate=True,
        novelty_dedupe=visible,
    )
    assert first.route == FindingRoute.HIL_VALIDATION
    assert second.route == FindingRoute.HIL_VALIDATION

    default_queue = router.get_findings_for_hil_validation()
    all_queue = router.get_findings_for_hil_validation(include_suppressed=True)

    assert len(default_queue) == 1
    assert default_queue[0].finding_id == second.finding_id
    assert len(all_queue) == 2


@pytest.mark.asyncio
async def test_novelty_dedupe_cannot_bypass_submission_candidate_gate():
    router = FindingRouter()
    routed = await router.route_finding(
        target_domain="api.example.com",
        vulnerability_type="sql_injection",
        endpoint="/api/v1/users/9",
        cvss_score=9.0,
        severity="high",
        confidence_score=0.95,
        submission_candidate=False,
        novelty_dedupe={
            "suppression_recommendation": "none",
            "novelty_score": 0.95,
            "duplicate_likelihood_score": 0.1,
        },
    )
    assert routed.route == FindingRoute.DISCARDED
    assert "qualification rejected" in routed.reasoning.lower()
