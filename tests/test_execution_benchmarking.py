from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from apps.backend.src.core.kai_execution_benchmarks import (
    build_benchmark_intelligence_report,
    build_selector_performance_profile,
    discover_benchmark_history_files,
    load_benchmark_payload,
    mission_benchmark_record_from_state,
    persist_benchmark_run,
    query_benchmark_records,
    run_parallel_execution_benchmark_scenario,
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
    assert "adaptive_performance_profiles" in payload
    assert "selector_learning_recommendations" in payload


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


def test_adaptive_profiles_emitted_after_rolling_records(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmarks" / "latest.json"
    now = "2026-04-05T00:00:00+00:00"
    for substrate, success, latency in [
        ("LANGGRAPH_PRIMARY", True, 200),
        ("LANGGRAPH_PRIMARY", True, 190),
        ("LANGGRAPH_PRIMARY", False, 260),
        ("MISSIONRUNTIME_CUSTOM", True, 120),
    ]:
        persist_benchmark_run(
            {
                "selected_substrate": substrate,
                "success": success,
                "total_mission_ms": latency,
                "retry_frequency": 0.0 if success else 0.2,
                "tool_failure_rate": 0.0 if success else 0.3,
                "stage_count": 3,
                "tool_invocations": 2,
                "scenario_type": "multi_stage",
                "stage_type": "recon",
                "workflow_complexity": "high",
                "determinism_requirement": "high",
                "adaptive_profile_key": "multi_stage|recon|high|high",
                "created_at": now,
            },
            path=output_path,
        )
    payload = load_benchmark_payload(output_path)
    profiles = payload.get("adaptive_performance_profiles", {})
    assert "multi_stage|recon|high|high" in profiles
    assert isinstance(payload.get("selector_learning_recommendations", []), list)


def test_mission_record_contains_learning_context_fields() -> None:
    state = {
        "phase": "recon",
        "runtime_metrics": {
            "stage_count": 2,
            "tool_invocations": 1,
            "total_mission_ms": 150.0,
        },
        "selector_policy_artifacts": [
            {
                "selected_substrate": "DEEPAGENTS_SPECIALIST",
                "fallback_substrate": "LANGGRAPH_PRIMARY",
                "selector_inputs": {
                    "workflow_complexity": "high",
                    "needs_resume": True,
                    "requires_specialist_decomposition": True,
                    "requires_protocol_bridge": False,
                    "telemetry_required": "strict",
                },
            }
        ],
    }
    record = mission_benchmark_record_from_state(
        mission_id="m-test",
        workflow_id="wf-test",
        program_id="prog-test",
        execution_mode="live",
        terminal_status="completed",
        state=state,
    )
    assert record["scenario_type"] == "specialist"
    assert record["determinism_requirement"] == "high"
    assert record["adaptive_profile_key"] == "specialist|recon|high|high"


def test_mission_record_prefers_selector_policy_over_resolution_artifact() -> None:
    state = {
        "phase": "recon",
        "runtime_metrics": {
            "stage_count": 1,
            "tool_invocations": 0,
            "total_mission_ms": 90.0,
            "actual_substrate": "LANGGRAPH_PRIMARY",
        },
        "selector_policy_artifacts": [
            {
                "type": "execution_selector_policy",
                "selected_substrate": "DEEPAGENTS_SPECIALIST",
                "fallback_substrate": "LANGGRAPH_PRIMARY",
                "selector_inputs": {
                    "workflow_complexity": "high",
                    "needs_resume": False,
                    "requires_specialist_decomposition": True,
                },
            },
            {
                "type": "execution_substrate_resolution",
                "requested_substrate": "DEEPAGENTS_SPECIALIST",
                "actual_substrate": "LANGGRAPH_PRIMARY",
                "reason": "deepagents_backend_unavailable",
            },
        ],
        "policy_events": [
            {
                "type": "execution_substrate_divergence",
                "requested_substrate": "DEEPAGENTS_SPECIALIST",
                "actual_substrate": "LANGGRAPH_PRIMARY",
                "reason": "deepagents_backend_unavailable",
            }
        ],
    }
    record = mission_benchmark_record_from_state(
        mission_id="m-div",
        workflow_id="wf-div",
        program_id="prog-div",
        execution_mode="live",
        terminal_status="completed",
        state=state,
    )
    assert record["selected_substrate"] == "DEEPAGENTS_SPECIALIST"
    assert record["actual_substrate"] == "LANGGRAPH_PRIMARY"
    assert record["substrate_divergence_snapshot"]["diverged"] is True
    assert record["substrate_divergence_snapshot"]["reason"] == "deepagents_backend_unavailable"


def test_runtime_deepagents_missing_backend_emits_explicit_divergence(monkeypatch) -> None:
    runtime = MissionRuntime()
    monkeypatch.setattr(runtime, "_refresh_selector_performance_profile", lambda: None)
    runtime._selector_performance_profile = {}
    runtime._adaptive_selector_profiles = {}
    captured: list[dict] = []
    monkeypatch.setattr(
        "apps.backend.src.core.praison_mission_runtime.persist_benchmark_run",
        lambda record: captured.append(record) or {"ok": True},
    )

    handle = runtime.create_mission(
        workflow_id="wf-specialist",
        program_id="prog-specialist",
        tenant_id=uuid.uuid4(),
        execution_mode="live",
        agent_specs=_minimal_specs(),
        selector_inputs={"requires_specialist_decomposition": True, "risk_band": 1},
    )
    final = runtime.start_mission(handle.mission_id)
    policy_events = final.get("policy_events", [])
    divergences = [
        row for row in policy_events
        if isinstance(row, dict) and row.get("type") == "execution_substrate_divergence"
    ]
    assert divergences
    assert divergences[0]["requested_substrate"] == "DEEPAGENTS_SPECIALIST"
    assert divergences[0]["actual_substrate"] == "LANGGRAPH_PRIMARY"
    assert divergences[0]["reason"] == "deepagents_backend_unavailable"
    assert divergences[0]["contract_status"] == "deferred_structural_capability"
    assert divergences[0]["capability_owner"] == "kai_runtime"
    assert divergences[0]["irreversible"] is True
    assert captured
    assert captured[-1]["selected_substrate"] == "DEEPAGENTS_SPECIALIST"
    assert captured[-1]["actual_substrate"] == "LANGGRAPH_PRIMARY"
    assert captured[-1]["substrate_divergence_snapshot"]["diverged"] is True


def test_parallel_benchmark_scenario_persists_real_parallel_record(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmarks" / "latest.json"
    result = asyncio.run(
        run_parallel_execution_benchmark_scenario(
            mission_id="mission-parallel-1",
            workflow_id="wf-parallel",
            program_id="prog-parallel",
            path=output_path,
        )
    )
    payload = load_benchmark_payload(output_path)
    assert payload["records"]
    latest = payload["records"][-1]
    assert latest["execution_mode"] == "parallel"
    assert latest["stage_type"] == "benchmark_parallel_stage"
    assert latest["tool_invocations"] == 3
    assert latest["aggregation_timing_ms"] >= 0.0
    assert isinstance(latest.get("aggregation_summary", {}).get("hashes", []), list)
    assert payload["summary"]["scenarios"]["parallel"]["runs"] >= 1
    assert result["record"]["adaptive_profile_key"] == "parallel|benchmark_parallel_stage|high|standard"


def test_benchmark_intelligence_report_exposes_operator_visibility(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmarks" / "latest.json"
    persist_benchmark_run(
        {
            "selected_substrate": "LANGGRAPH_PRIMARY",
            "actual_substrate": "LANGGRAPH_PRIMARY",
            "success": True,
            "total_mission_ms": 140.0,
            "retry_frequency": 0.0,
            "tool_failure_rate": 0.0,
            "stage_count": 3,
            "tool_invocations": 2,
            "adaptive_decision_snapshot": {"considered": True, "applied": False},
            "substrate_divergence_snapshot": {"diverged": False},
        },
        path=output_path,
    )
    report = build_benchmark_intelligence_report(path=output_path, include_recent=5)
    assert report["total_runs"] >= 1
    assert "latency_distribution" in report
    assert "substrate_performance" in report
    assert "failure_retry_patterns" in report
    assert "adaptive_selector_influence" in report
    assert report["data_integrity"]["records_with_adaptive_snapshot"] >= 1


def test_benchmark_history_query_filters_records(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmarks" / "latest.json"
    persist_benchmark_run(
        {
            "mission_id": "m1",
            "workflow_id": "wf",
            "program_id": "p",
            "selected_substrate": "LANGGRAPH_PRIMARY",
            "scenario_type": "multi_stage",
            "success": True,
            "created_at": "2026-04-05T00:00:00+00:00",
            "total_mission_ms": 100.0,
            "retry_frequency": 0.0,
            "tool_failure_rate": 0.0,
            "stage_count": 2,
            "tool_invocations": 1,
        },
        path=output_path,
    )
    persist_benchmark_run(
        {
            "mission_id": "m2",
            "workflow_id": "wf",
            "program_id": "p",
            "selected_substrate": "MISSIONRUNTIME_CUSTOM",
            "scenario_type": "parallel",
            "success": False,
            "created_at": "2026-04-06T00:00:00+00:00",
            "total_mission_ms": 200.0,
            "retry_frequency": 0.4,
            "tool_failure_rate": 0.3,
            "stage_count": 3,
            "tool_invocations": 2,
        },
        path=output_path,
    )
    rows = query_benchmark_records(
        path=output_path,
        include_latest=True,
        include_history=True,
        substrate="MISSIONRUNTIME_CUSTOM",
        scenario_type="parallel",
        success=False,
        limit=10,
    )
    assert rows
    assert rows[0]["mission_id"] == "m2"
    assert rows[0]["selected_substrate"] == "MISSIONRUNTIME_CUSTOM"


def test_history_retention_prunes_old_files(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmarks" / "latest.json"
    history_dir = output_path.parent / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(5):
        (history_dir / f"2026-03-0{idx + 1}.jsonl").write_text("{}", encoding="utf-8")
    persist_benchmark_run(
        {
            "selected_substrate": "LANGGRAPH_PRIMARY",
            "success": True,
            "total_mission_ms": 100.0,
            "retry_frequency": 0.0,
            "tool_failure_rate": 0.0,
            "stage_count": 1,
            "tool_invocations": 1,
            "created_at": "2026-04-05T12:00:00+00:00",
        },
        path=output_path,
        max_history_files=3,
    )
    files = discover_benchmark_history_files(path=output_path, max_files=0)
    assert len(files) <= 3
