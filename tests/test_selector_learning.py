from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apps.backend.src.core.kai_execution_selector import (
    ExecutionSubstrate,
    select_execution_substrate,
)
from apps.backend.src.core.kai_selector_learning import (
    build_adaptive_performance_profiles,
    build_selector_learning_recommendations,
    make_adaptive_profile_key,
    select_adaptive_profile_for_inputs,
)


def _record(
    *,
    substrate: str,
    success: bool,
    created_at: datetime,
    scenario_type: str = "general",
    stage_type: str = "mission",
    complexity: str = "medium",
    determinism: str = "standard",
    latency_ms: float = 100.0,
    retry_frequency: float = 0.0,
) -> dict[str, object]:
    return {
        "selected_substrate": substrate,
        "success": success,
        "retry_frequency": retry_frequency,
        "total_mission_ms": latency_ms,
        "scenario_type": scenario_type,
        "stage_type": stage_type,
        "workflow_complexity": complexity,
        "determinism_requirement": determinism,
        "adaptive_profile_key": make_adaptive_profile_key(
            scenario_type=scenario_type,
            stage_type=stage_type,
            workflow_complexity=complexity,
            determinism_requirement=determinism,
        ),
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
    }


def test_learning_profiles_require_min_samples() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        _record(
            substrate=ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
            success=True,
            created_at=now,
            scenario_type="multi_stage",
            stage_type="recon",
            complexity="high",
            determinism="high",
        ),
        _record(
            substrate=ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
            success=True,
            created_at=now,
            scenario_type="multi_stage",
            stage_type="recon",
            complexity="high",
            determinism="high",
        ),
    ]
    profiles = build_adaptive_performance_profiles(rows, min_samples=3, now=now)
    key = make_adaptive_profile_key(
        scenario_type="multi_stage",
        stage_type="recon",
        workflow_complexity="high",
        determinism_requirement="high",
    )
    assert profiles[key]["sample_count"] == 2
    assert profiles[key]["usable"] is False
    assert profiles[key]["recommended_substrate"] == ""


def test_learning_profiles_mark_stale() -> None:
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(days=30)
    rows = [
        _record(
            substrate=ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value,
            success=True,
            created_at=stale_time,
            scenario_type="simple",
            stage_type="mission",
            complexity="low",
            determinism="standard",
        )
        for _ in range(4)
    ]
    profiles = build_adaptive_performance_profiles(rows, min_samples=3, stale_after_days=7, now=now)
    key = make_adaptive_profile_key(
        scenario_type="simple",
        stage_type="mission",
        workflow_complexity="low",
        determinism_requirement="standard",
    )
    assert profiles[key]["stale"] is True
    assert profiles[key]["usable"] is False


def test_select_adaptive_profile_for_inputs_fallback_stage() -> None:
    key = make_adaptive_profile_key(
        scenario_type="general",
        stage_type="mission",
        workflow_complexity="medium",
        determinism_requirement="high",
    )
    profiles = {
        key: {
            "profile_key": key,
            "recommended_substrate": ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
            "confidence": 0.8,
            "sample_count": 5,
            "stale": False,
            "usable": True,
        }
    }
    selected = select_adaptive_profile_for_inputs(
        profiles,
        {
            "execution_mode": "live",
            "workflow_complexity": "medium",
            "needs_resume": True,
            "stage_id": "recon",
        },
    )
    assert selected["profile_key"] == key


def test_learning_recommendations_sorted_by_quality() -> None:
    adaptive_profiles = {
        "a": {"usable": False, "confidence": 0.2, "sample_count": 1, "recommended_substrate": ""},
        "b": {"usable": True, "confidence": 0.9, "sample_count": 6, "recommended_substrate": "LANGGRAPH_PRIMARY"},
    }
    recs = build_selector_learning_recommendations(adaptive_profiles)
    assert recs[0]["profile_key"] == "b"


def test_selector_applies_adaptive_recommendation_with_audit() -> None:
    decision = select_execution_substrate(
        {
            "workflow_complexity": "medium",
            "needs_resume": False,
            "adaptive_profile": {
                "profile_key": "general|mission|medium|standard",
                "recommended_substrate": ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value,
                "confidence": 0.9,
                "sample_count": 8,
                "stale": False,
                "usable": True,
                "recommendation_rationale": "low latency and high reliability",
            },
        }
    )
    assert decision["selected_substrate"] == ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value
    adaptive_change = decision["adaptive_change"]
    assert adaptive_change["applied"] is True
    assert adaptive_change["previous_selected_substrate"] == ExecutionSubstrate.LANGGRAPH_PRIMARY.value
    assert "selector:adaptive_recommendation_applied" in decision["audit_tags"]


def test_selector_ignores_low_confidence_adaptive_recommendation() -> None:
    decision = select_execution_substrate(
        {
            "workflow_complexity": "medium",
            "needs_resume": False,
            "adaptive_profile": {
                "profile_key": "general|mission|medium|standard",
                "recommended_substrate": ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value,
                "confidence": 0.4,
                "sample_count": 2,
                "stale": False,
                "usable": True,
            },
        }
    )
    assert decision["selected_substrate"] == ExecutionSubstrate.LANGGRAPH_PRIMARY.value
    assert decision["adaptive_change"]["applied"] is False


def test_selector_ignores_stale_adaptive_recommendation() -> None:
    decision = select_execution_substrate(
        {
            "workflow_complexity": "medium",
            "needs_resume": False,
            "adaptive_profile": {
                "profile_key": "general|mission|medium|standard",
                "recommended_substrate": ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value,
                "confidence": 0.9,
                "sample_count": 20,
                "stale": True,
                "usable": True,
            },
        }
    )
    assert decision["selected_substrate"] == ExecutionSubstrate.LANGGRAPH_PRIMARY.value
    assert decision["adaptive_change"]["applied"] is False


def test_selector_is_deterministic_for_identical_inputs() -> None:
    inputs = {
        "risk_band": 1,
        "workflow_complexity": "high",
        "needs_resume": False,
        "tool_privilege_level": "read",
        "adaptive_profile": {
            "profile_key": "multi_stage|recon|high|standard",
            "recommended_substrate": ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value,
            "confidence": 0.60,
            "sample_count": 2,
            "stale": False,
            "usable": True,
        },
    }
    first = select_execution_substrate(inputs)
    second = select_execution_substrate(inputs)
    for key in (
        "selected_substrate",
        "fallback_substrate",
        "policy_justification",
        "required_guards",
        "audit_tags",
        "inputs",
        "adaptive_change",
        "denied",
    ):
        assert first[key] == second[key]


def test_selector_rejected_adaptive_change_has_explainability_fields() -> None:
    decision = select_execution_substrate(
        {
            "workflow_complexity": "medium",
            "needs_resume": False,
            "adaptive_profile": {
                "profile_key": "general|mission|medium|standard",
                "recommended_substrate": ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value,
                "confidence": 0.4,
                "sample_count": 2,
                "stale": False,
                "usable": True,
                "recommendation_rationale": "candidate from sparse data",
            },
        }
    )
    adaptive_change = decision["adaptive_change"]
    assert adaptive_change["considered"] is True
    assert adaptive_change["accepted"] is False
    assert adaptive_change["rejected"] is True
    assert "minimum_samples_met" in adaptive_change["failed_guardrails"]
    assert "minimum_confidence_met" in adaptive_change["failed_guardrails"]
    assert "collect_more_runs" in adaptive_change["additional_data_needed"]
    assert "improve_profile_confidence" in adaptive_change["additional_data_needed"]
    assert adaptive_change["decision_reason"] == "adaptive_recommendation_not_applied"


def test_selector_exposes_compatibility_guardrail_failures() -> None:
    decision = select_execution_substrate(
        {
            "requires_protocol_bridge": True,
            "needs_resume": False,
            "adaptive_profile": {
                "profile_key": "interop|mission|medium|standard",
                "recommended_substrate": ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
                "confidence": 0.9,
                "sample_count": 8,
                "stale": False,
                "usable": True,
            },
        }
    )
    adaptive_change = decision["adaptive_change"]
    assert adaptive_change["considered"] is True
    assert adaptive_change["applied"] is False
    assert "compatibility_passed" in adaptive_change["failed_guardrails"]
    assert "provide_compatible_substrate_recommendation" in adaptive_change["additional_data_needed"]
