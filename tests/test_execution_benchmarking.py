from __future__ import annotations

import uuid
from pathlib import Path

from apps.backend.src.core.kai_execution_benchmarks import (
    build_selector_performance_profile,
    load_benchmark_payload,
    persist_benchmark_run,
    summarize_benchmark_records,
)
from apps.backend.src.core.praison_execution_events import MissionEvent
from apps.backend.src.core.praison_mission_runtime import MissionRuntime


def _minimal_specs() -> dict[str, dict[str, str]]:
    agents = [
        "GovernanceDirector",
        "MissionDirector",
        "PhaseCoordinator",
        "SurfaceMapper",
        "ReconSpecialist",
        "EvidenceAnalyst",
        "ReportSynthesisAgent",
        "HandoffLiaison",
    ]
    specs: dict[str, dict[str, str]] = {}
    for aid in agents:
        specs[aid] = {
            "node_id": aid,
            "node_type": "agent",
            "agent_class": "specialist",
            "risk_profile": "standard",
            "review_policy": "standard",
            "memory_scope": "session",
            "allowed_tools": [],
            "system_prompt": f"Agent {aid}",
        }
    specs["GovernanceDirector"]["node_type"] = "governance"
    specs["GovernanceDirector"]["agent_class"] = "governor"
    specs["MissionDirector"]["agent_class"] = "director"
    specs["PhaseCoordinator"]["agent_class"] = "coordinator"
    return specs


def test_benchmark_summary_and_selector_profile() -> None:
    records = [
        {
            "selected_substrate": "LANGGRAPH_PRIMARY",
            "total_mission_ms": 900,
            "success": True,
            "retry_frequency": 0.05,
            "tool_failure_rate": 0.0,
            "stage_count": 5,
            "total_tokens": 120,
            "estimated_cost_cents": 0.3,
            "execution_mode": "live",
            "tool_invocations": 3,
        },
        {
            "selected_substrate": "LANGGRAPH_PRIMARY",
            "total_mission_ms": 1100,
            "success": False,
            "retry_frequency": 0.2,
            "tool_failure_rate": 0.3,
            "stage_count": 4,
            "total_tokens": 80,
            "estimated_cost_cents": 0.2,
            "execution_mode": "live",
            "tool_invocations": 2,
        },
        {
            "selected_substrate": "MISSIONRUNTIME_CUSTOM",
            "total_mission_ms": 120,
            "success": True,
            "retry_frequency": 0.0,
            "tool_failure_rate": 0.0,
            "stage_count": 1,
            "total_tokens": 0,
            "estimated_cost_cents": 0.0,
            "execution_mode": "graph_only",
            "tool_invocations": 0,
        },
    ]

    summary = summarize_benchmark_records(records)
    assert summary["total_runs"] == 3
    assert summary["substrates"]["LANGGRAPH_PRIMARY"]["runs"] == 2
    assert summary["substrates"]["LANGGRAPH_PRIMARY"]["failure_rate"] == 0.5

    profile = build_selector_performance_profile(summary)
    assert profile["LANGGRAPH_PRIMARY"]["failure_rate"] == 0.5
    assert profile["MISSIONRUNTIME_CUSTOM"]["p95_latency_ms"] >= 0


def test_persist_and_load_benchmark_payload(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmarks" / "latest.json"
    persist_benchmark_run(
        {
            "selected_substrate": "LANGGRAPH_PRIMARY",
            "total_mission_ms": 100,
            "success": True,
            "retry_frequency": 0.0,
            "tool_failure_rate": 0.0,
            "stage_count": 2,
            "tool_invocations": 1,
            "total_tokens": 10,
            "estimated_cost_cents": 0.01,
        },
        path=output_path,
    )
    payload = load_benchmark_payload(output_path)
    assert payload["records"]
    assert payload["summary"]["total_runs"] == 1


def test_runtime_collects_metrics_and_stage_timings(monkeypatch) -> None:
    runtime = MissionRuntime()

    # Prevent test writes to shared artifacts path.
    monkeypatch.setattr(
        "apps.backend.src.core.praison_mission_runtime.persist_benchmark_run",
        lambda _record: {"ok": True},
    )

    handle = runtime.create_mission(
        workflow_id="wf-bench",
        program_id="prog-bench",
        tenant_id=uuid.uuid4(),
        execution_mode="graph_only",
        agent_specs=_minimal_specs(),
    )
    final = runtime.start_mission(handle.mission_id)
    metrics = final.get("runtime_metrics", {})
    assert metrics.get("total_mission_ms", 0.0) >= 0.0
    assert metrics.get("stage_count", 0) >= 1
    assert isinstance(metrics.get("stage_timings", []), list)


def test_runtime_event_capture_tracks_tool_and_llm_usage() -> None:
    runtime = MissionRuntime()
    mission_id = "mission-metrics-1"
    runtime._states[mission_id] = {"mission_id": mission_id, "runtime_metrics": {}}

    runtime._capture_runtime_metrics_event(
        MissionEvent(
            event_type="tool_invocation_completed",
            mission_id=mission_id,
            detail={
                "tool_id": "subfinder",
                "status": "failed",
                "duration_ms": 42.0,
                "estimated_tokens": 20,
                "estimated_cost_cents": 0.2,
                "retry_count": 1,
            },
        )
    )
    runtime._capture_runtime_metrics_event(
        MissionEvent(
            event_type="llm_invocation_completed",
            mission_id=mission_id,
            detail={"token_usage": {"input_tokens": 10, "output_tokens": 5}},
        )
    )

    metrics = runtime._states[mission_id]["runtime_metrics"]
    assert metrics["tool_invocations"] == 1
    assert metrics["tool_failures"] == 1
    assert metrics["tool_retry_count"] == 1
    assert metrics["model_calls"] == 1
    assert metrics["total_tokens"] >= 35
