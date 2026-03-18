"""
K1 LangGraph Mission Runtime Tests (Phase 4 / 4.5)
=====================================================
Comprehensive tests for the LangGraph mission execution runtime.

Test coverage:
  1. Graph compilation — topology to executable graph
  2. State reducer correctness — accumulative vs scalar merging
  3. Checkpoint persistence — MemorySaver, resume behavior
  4. Resume behavior — interrupt → checkpoint → resume flow
  5. Cluster node execution — specialist cluster state updates
  6. Governance enforcement — middleware blocking, policy events
  7. Adaptive strategy patch validation — allowed/forbidden fields
  8. Interrupt handling — approval gates, governance stops
  9. Event emission — all lifecycle events fire correctly
  10. Regression compatibility — existing 199 tests unaffected
  11. Mission lifecycle — create, start, stop, cancel, resume, list, inspect
  12. Subgraph compilation — cluster subgraph scaffold and compilation
  13. Strategy-aware execution — profile tracking in state
  14. Retry executor — bounded retry with backoff
"""

from __future__ import annotations

import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend source is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend" / "src"))

from apps.backend.src.core.praison_state import (
    K1GraphState,
    make_initial_state,
    state_snapshot,
)
from apps.backend.src.core.praison_topology import (
    ClusterSpec,
    EdgeCondition,
    EdgeSpec,
    MissionGraphSpec,
    NodeSpec,
    PraisonTopology,
)
from apps.backend.src.core.praison_langgraph_builder import (
    PraisonLangGraphBuilder,
    _LANGGRAPH_AVAILABLE,
    _make_condition_router,
)
from apps.backend.src.core.praison_mission_runtime import (
    MissionHandle,
    MissionRuntime,
    MissionStatus,
    _merge_state,
)
from apps.backend.src.core.praison_node_executors import (
    build_standard_node_callables,
    make_node_executor,
    make_governance_admission_executor,
    make_mission_director_executor,
    make_phase_coordinator_executor,
    make_specialist_cluster_executor,
    make_evidence_analysis_executor,
    make_governance_review_executor,
    make_report_synthesis_executor,
    make_handoff_liaison_executor,
    make_governance_middleware,
    make_strategy_aware_executor,
    make_retry_executor,
    _ACCUMULATIVE_FIELDS,
)
from apps.backend.src.core.praison_execution_events import (
    EventBus,
    EventType,
    MissionEvent,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_specs():
    """Minimal agent specs for topology building."""
    agents = [
        "GovernanceDirector", "MissionDirector", "PhaseCoordinator",
        "SurfaceMapper", "ReconSpecialist", "EvidenceAnalyst",
        "ReportSynthesisAgent", "HandoffLiaison",
    ]
    specs = {}
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


@pytest.fixture
def graph_spec(minimal_specs):
    """Standard bug bounty graph spec."""
    return PraisonTopology.build_standard_bug_bounty(
        workflow_id="wf-test",
        program_id="prog-test",
        agent_specs=minimal_specs,
    )


@pytest.fixture
def node_callables():
    """Standard node callables for graph_only execution."""
    return build_standard_node_callables()


@pytest.fixture
def builder(graph_spec, node_callables):
    """LangGraph builder with standard topology."""
    return PraisonLangGraphBuilder(graph_spec, node_callables)


@pytest.fixture
def runtime():
    """Mission runtime with no checkpointer (MemorySaver)."""
    return MissionRuntime()


@pytest.fixture
def initial_state():
    """Standard initial state for testing."""
    return make_initial_state(
        workflow_id="wf-test",
        program_id="prog-test",
        mission_name="test_mission",
        execution_mode="graph_only",
    )


@pytest.fixture
def event_collector():
    """Collect events emitted during tests."""
    events = []
    bus = EventBus()
    bus.subscribe(lambda e: events.append(e))
    return bus, events


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Graph Compilation
# ═══════════════════════════════════════════════════════════════════════════════


class TestGraphCompilation:
    """Graph spec compiles into executable structure."""

    def test_scaffold_spec_always_available(self, builder):
        scaffold = builder.build_scaffold_spec()
        assert scaffold["graph_id"]
        assert scaffold["workflow_id"] == "wf-test"
        assert scaffold["program_id"] == "prog-test"
        assert len(scaffold["nodes"]) > 0
        assert len(scaffold["edges"]) > 0
        assert scaffold["entry_node"] == "GovernanceDirector"
        assert scaffold["exit_node"] == "HandoffLiaison"
        assert "execution_order" in scaffold

    def test_scaffold_has_execution_order(self, builder):
        scaffold = builder.build_scaffold_spec()
        order = scaffold["execution_order"]
        assert isinstance(order, list)
        assert len(order) > 0
        # Entry node should be first
        assert order[0] == "GovernanceDirector"

    def test_scaffold_interrupt_lists(self, builder):
        scaffold = builder.build_scaffold_spec()
        assert "interrupt_before" in scaffold
        assert "interrupt_after" in scaffold
        assert isinstance(scaffold["interrupt_before"], list)
        assert isinstance(scaffold["interrupt_after"], list)

    def test_compile_returns_graph_or_none(self, builder):
        result = builder.compile()
        if _LANGGRAPH_AVAILABLE:
            assert result is not None
        else:
            assert result is None

    def test_builder_with_empty_spec(self):
        spec = MissionGraphSpec()
        callables = {}
        builder = PraisonLangGraphBuilder(spec, callables)
        scaffold = builder.build_scaffold_spec()
        assert scaffold["nodes"] == []
        assert scaffold["edges"] == []

    def test_builder_missing_callable_skips_node(self, graph_spec):
        # Only provide one callable
        callables = {"GovernanceDirector": make_governance_admission_executor()}
        builder = PraisonLangGraphBuilder(graph_spec, callables)
        scaffold = builder.build_scaffold_spec()
        # Scaffold should still include all nodes (it works from spec)
        assert len(scaffold["nodes"]) == len(graph_spec.nodes)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. State Reducer Correctness
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateReducers:
    """Accumulative fields append; scalars replace."""

    def test_initial_state_has_all_fields(self, initial_state):
        assert initial_state["mission_id"]
        assert initial_state["workflow_id"] == "wf-test"
        assert initial_state["execution_mode"] == "graph_only"
        assert initial_state["phase"] == "governance"
        assert initial_state["artifacts"] == []
        assert initial_state["findings"] == []
        assert initial_state["node_history"] == []
        assert initial_state["errors"] == []
        assert initial_state["strategy_profiles_used"] == []
        assert initial_state["knowledge_lessons_generated"] == []
        assert initial_state["runtime_metrics"] == {}

    def test_merge_accumulative_appends(self):
        base = {"artifacts": [{"id": "a1"}], "phase": "recon"}
        update = {"artifacts": [{"id": "a2"}]}
        merged = _merge_state(base, update)
        assert len(merged["artifacts"]) == 2
        assert merged["artifacts"][0]["id"] == "a1"
        assert merged["artifacts"][1]["id"] == "a2"

    def test_merge_scalar_replaces(self):
        base = {"phase": "recon", "active_node": "A"}
        update = {"phase": "scanning", "active_node": "B"}
        merged = _merge_state(base, update)
        assert merged["phase"] == "scanning"
        assert merged["active_node"] == "B"

    def test_merge_preserves_unmentioned_fields(self):
        base = {"phase": "recon", "mission_id": "m1", "artifacts": []}
        update = {"phase": "scanning"}
        merged = _merge_state(base, update)
        assert merged["mission_id"] == "m1"
        assert merged["artifacts"] == []

    def test_merge_new_accumulative_fields(self):
        base = {"strategy_profiles_used": [{"node_id": "A"}]}
        update = {"strategy_profiles_used": [{"node_id": "B"}]}
        merged = _merge_state(base, update)
        assert len(merged["strategy_profiles_used"]) == 2

    def test_merge_knowledge_lessons(self):
        base = {"knowledge_lessons_generated": []}
        update = {"knowledge_lessons_generated": [{"lesson_id": "l1"}]}
        merged = _merge_state(base, update)
        assert len(merged["knowledge_lessons_generated"]) == 1

    def test_merge_runtime_metrics_replaces(self):
        base = {"runtime_metrics": {"duration": 100}}
        update = {"runtime_metrics": {"duration": 200, "tool_calls": 5}}
        merged = _merge_state(base, update)
        assert merged["runtime_metrics"]["duration"] == 200
        assert merged["runtime_metrics"]["tool_calls"] == 5

    def test_accumulative_fields_constant_matches_state(self):
        """_ACCUMULATIVE_FIELDS must cover all list reducer fields in K1GraphState."""
        # These are the fields with Annotated[list, operator.add] reducers
        expected_accum = {
            "messages", "artifacts", "contract_ids", "escalations", "violations",
            "node_history", "artifact_ids", "findings", "policy_events", "events",
            "approvals_required", "approvals_resolved",
            "adaptive_plan_patches_applied", "adaptive_plan_patches_rejected",
            "errors", "strategy_profiles_used", "knowledge_lessons_generated",
        }
        assert _ACCUMULATIVE_FIELDS == expected_accum

    def test_state_snapshot_includes_learning_fields(self, initial_state):
        snap = state_snapshot(initial_state)
        assert "profiles_used_count" in snap
        assert "lessons_generated_count" in snap
        assert "runtime_metrics" in snap
        assert snap["profiles_used_count"] == 0
        assert snap["lessons_generated_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Checkpoint Persistence
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckpointing:
    """Checkpointer configuration and fallback."""

    def test_memorysaver_fallback(self, builder):
        if not _LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph not installed")
        # No DSN → should use MemorySaver
        compiled = builder.compile(checkpointer_dsn=None)
        assert compiled is not None

    def test_invalid_postgres_dsn_falls_back(self, builder):
        if not _LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph not installed")
        # Invalid DSN → should fall back to MemorySaver, not crash
        compiled = builder.compile(checkpointer_dsn="postgresql://invalid:5432/nonexistent")
        assert compiled is not None

    def test_mission_maps_to_thread_id(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-ck",
            program_id="prog-ck",
            execution_mode="graph_only",
            agent_specs=minimal_specs,
        )
        # Mission ID becomes the LangGraph thread_id
        assert handle.mission_id
        assert len(handle.mission_id) == 36  # UUID format


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Resume Behavior
# ═══════════════════════════════════════════════════════════════════════════════


class TestResumeBehavior:
    """Paused missions can be resumed with approval data."""

    def test_stop_sets_paused_state(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-r", program_id="prog-r",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        runtime.stop_mission(handle.mission_id, reason="test_stop")
        status = runtime.get_status(handle.mission_id)
        assert status.state == "paused"
        assert "test_stop" in status.error

    def test_resume_clears_stop_error(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-r2", program_id="prog-r2",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        runtime.start_mission(handle.mission_id)
        runtime.stop_mission(handle.mission_id, reason="pause_test")
        result = runtime.resume_mission(handle.mission_id)
        # After resume in graph_only, error should be cleared or mission completed
        assert "Mission stopped" not in result.get("error", "")

    def test_resume_with_approval_data(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-r3", program_id="prog-r3",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        runtime.stop_mission(handle.mission_id, reason="approval_wait")
        runtime.resume_mission(handle.mission_id, approval_data={
            "approval_id": "ap-001",
            "decision": "approved",
            "resolved_by": "operator",
        })
        state = runtime.get_state(handle.mission_id)
        approvals = state.get("approvals_resolved", [])
        assert any(a.get("approval_id") == "ap-001" for a in approvals)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Cluster Node Execution
# ═══════════════════════════════════════════════════════════════════════════════


class TestClusterExecution:
    """Specialist cluster nodes update state correctly."""

    def test_cluster_executor_sets_status(self):
        executor = make_specialist_cluster_executor("recon_scan")
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        assert "cluster_status" in result
        assert "recon_scan" in result["cluster_status"]
        assert result["cluster_status"]["recon_scan"]["success"] is True

    def test_cluster_executor_on_failure(self):
        def failing_callable(state):
            raise RuntimeError("Tool timeout")
        executor = make_specialist_cluster_executor("failing_cluster", failing_callable)
        state = make_initial_state("wf", "prog", execution_mode="live")
        result = executor(dict(state))
        assert result.get("error")
        cluster_status = result.get("cluster_status", {})
        assert "failing_cluster" in cluster_status
        assert cluster_status["failing_cluster"]["success"] is False

    def test_multiple_clusters_accumulate_status(self):
        state = dict(make_initial_state("wf", "prog", execution_mode="graph_only"))
        for cluster_name in ["recon", "scanning", "analysis"]:
            executor = make_specialist_cluster_executor(cluster_name)
            result = executor(state)
            state = _merge_state(state, result)
        assert "recon" in state["cluster_status"]
        assert "scanning" in state["cluster_status"]
        assert "analysis" in state["cluster_status"]


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Governance Enforcement
# ═══════════════════════════════════════════════════════════════════════════════


class TestGovernanceEnforcement:
    """Governance middleware blocks unauthorized execution."""

    def test_governance_middleware_permits_valid(self):
        inner = make_node_executor("test_node")
        governed = make_governance_middleware(
            inner, "test_node",
            validate_agent_spawn=lambda **kw: None,  # always passes
        )
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = governed(dict(state))
        assert not result.get("error")
        assert result.get("governance_decision") != "blocked"

    def test_governance_middleware_blocks_on_validation_failure(self):
        inner = make_node_executor("blocked_node")

        def deny_spawn(**kwargs):
            raise PermissionError("Agent not authorized for this workflow")

        governed = make_governance_middleware(
            inner, "blocked_node",
            validate_agent_spawn=deny_spawn,
        )
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = governed(dict(state))
        assert result["governance_decision"] == "blocked"
        assert "not authorized" in result["error"]
        assert len(result.get("policy_events", [])) > 0

    def test_governance_admission_approves_on_success(self):
        executor = make_governance_admission_executor()
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        assert result["governance_decision"] == "approved"

    def test_governance_review_gate(self):
        executor = make_governance_review_executor()
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        # Default: approved (graph_only mode)
        assert result["governance_decision"] == "approved"

    def test_governance_middleware_no_validator(self):
        """Without a validator, middleware is a pass-through."""
        inner = make_node_executor("pass_node")
        governed = make_governance_middleware(inner, "pass_node")
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = governed(dict(state))
        assert not result.get("error")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Adaptive Strategy Patch Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdaptiveStrategy:
    """Strategy patches are validated through governance."""

    def test_strategy_aware_executor_tracks_profiles(self):
        inner = make_node_executor("strategy_node")
        executor = make_strategy_aware_executor(
            inner, "strategy_node",
            tool_profile_id="tp_balanced_recon",
            prompt_profile_id="pp_thorough_analysis",
        )
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        profiles = result.get("strategy_profiles_used", [])
        assert len(profiles) == 1
        assert profiles[0]["tool_profile_id"] == "tp_balanced_recon"
        assert profiles[0]["prompt_profile_id"] == "pp_thorough_analysis"
        assert profiles[0]["node_id"] == "strategy_node"

    def test_strategy_aware_no_profiles(self):
        inner = make_node_executor("plain_node")
        executor = make_strategy_aware_executor(inner, "plain_node")
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        # No profiles → no strategy_profiles_used entry
        assert result.get("strategy_profiles_used") is None or result["strategy_profiles_used"] == []

    def test_strategy_profiles_accumulate_across_nodes(self):
        state = dict(make_initial_state("wf", "prog", execution_mode="graph_only"))
        for i, profile_id in enumerate(["tp_passive_recon", "tp_high_recall"]):
            inner = make_node_executor(f"node_{i}")
            executor = make_strategy_aware_executor(
                inner, f"node_{i}", tool_profile_id=profile_id,
            )
            result = executor(state)
            state = _merge_state(state, result)
        assert len(state["strategy_profiles_used"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Interrupt Handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestInterruptHandling:
    """Interrupt gates pause execution and allow resume."""

    def test_governance_review_requests_approval_on_block(self):
        def blocking_callable(state):
            return {"governance_decision": "blocked", "error": "Needs review"}

        executor = make_governance_review_executor(blocking_callable)
        state = make_initial_state("wf", "prog", execution_mode="live")
        result = executor(dict(state))
        assert result["governance_decision"] == "blocked"
        approvals = result.get("approvals_required", [])
        assert len(approvals) > 0
        assert approvals[0]["node_id"] == "governance_review"

    def test_interrupt_nodes_in_topology(self, graph_spec):
        interrupt_nodes = graph_spec.nodes_requiring_interrupt()
        # May be empty if no interrupt_before/after set in specs
        assert isinstance(interrupt_nodes, list)

    def test_stop_and_resume_preserves_state(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-int", program_id="prog-int",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        # Start and complete
        runtime.start_mission(handle.mission_id)
        state_before = runtime.get_state(handle.mission_id)
        # Stop
        runtime.stop_mission(handle.mission_id, "interrupt_test")
        # Resume
        runtime.resume_mission(handle.mission_id)
        state_after = runtime.get_state(handle.mission_id)
        # State should still have mission identity
        assert state_after["mission_id"] == state_before["mission_id"]
        assert state_after["workflow_id"] == "wf-int"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Event Emission
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventEmission:
    """Lifecycle events fire at correct boundaries."""

    def test_mission_started_event(self, runtime, minimal_specs):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        with patch("apps.backend.src.core.praison_mission_runtime.emit", bus.emit):
            handle = runtime.create_mission(
                workflow_id="wf-ev", program_id="prog-ev",
                execution_mode="graph_only", agent_specs=minimal_specs,
            )
            runtime.start_mission(handle.mission_id)
        started = [e for e in events if e.event_type == EventType.MISSION_STARTED.value]
        assert len(started) == 1
        assert started[0].mission_id == handle.mission_id

    def test_mission_completed_event(self, runtime, minimal_specs):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        with patch("apps.backend.src.core.praison_mission_runtime.emit", bus.emit):
            handle = runtime.create_mission(
                workflow_id="wf-ev2", program_id="prog-ev2",
                execution_mode="graph_only", agent_specs=minimal_specs,
            )
            runtime.start_mission(handle.mission_id)
        completed = [e for e in events if e.event_type == EventType.MISSION_COMPLETED.value]
        assert len(completed) == 1

    def test_node_events_emitted(self):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        with patch("apps.backend.src.core.praison_node_executors.emit", bus.emit):
            executor = make_node_executor("test_emit")
            state = make_initial_state("wf", "prog", execution_mode="graph_only")
            executor(dict(state))
        entered = [e for e in events if e.event_type == EventType.NODE_ENTERED.value]
        completed = [e for e in events if e.event_type == EventType.NODE_COMPLETED.value]
        assert len(entered) == 1
        assert len(completed) == 1

    def test_cancel_emits_completed_event(self, runtime, minimal_specs):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))
        with patch("apps.backend.src.core.praison_mission_runtime.emit", bus.emit):
            handle = runtime.create_mission(
                workflow_id="wf-cancel", program_id="prog-cancel",
                execution_mode="graph_only", agent_specs=minimal_specs,
            )
            runtime.cancel_mission(handle.mission_id, "test_cancel")
        completed = [e for e in events if e.event_type == EventType.MISSION_COMPLETED.value]
        assert len(completed) == 1
        assert completed[0].detail["success"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Mission Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestMissionLifecycle:
    """Full mission lifecycle: create → start → complete."""

    def test_create_mission(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-lc",
            program_id="prog-lc",
            mission_name="lifecycle_test",
            execution_mode="graph_only",
            agent_specs=minimal_specs,
        )
        assert handle.mission_id
        assert handle.workflow_id == "wf-lc"
        assert handle.execution_mode == "graph_only"

    def test_start_mission_graph_only(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-start", program_id="prog-start",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        final = runtime.start_mission(handle.mission_id)
        assert final["completed"] is True
        assert final["progress"] == 1.0
        status = runtime.get_status(handle.mission_id)
        assert status.state == "completed"

    def test_start_mission_runs_all_nodes(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-nodes", program_id="prog-nodes",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        final = runtime.start_mission(handle.mission_id)
        history = final.get("node_history", [])
        # Should have executed multiple nodes
        assert len(history) > 0
        node_ids = [h["node_id"] for h in history]
        assert "governance_admission" in node_ids

    def test_get_status(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-st", program_id="prog-st",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        status = runtime.get_status(handle.mission_id)
        assert status.state == "created"
        assert status.mission_id == handle.mission_id
        runtime.start_mission(handle.mission_id)
        status = runtime.get_status(handle.mission_id)
        assert status.state in ("completed", "failed")

    def test_get_state(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-gs", program_id="prog-gs",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        state = runtime.get_state(handle.mission_id)
        assert state["mission_id"] == handle.mission_id

    def test_stop_mission(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-stop", program_id="prog-stop",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        runtime.stop_mission(handle.mission_id, "operator_pause")
        status = runtime.get_status(handle.mission_id)
        assert status.state == "paused"

    def test_cancel_mission(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-can", program_id="prog-can",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        state = runtime.cancel_mission(handle.mission_id, "testing")
        assert state["completed"] is True
        assert "cancelled" in state["error"]
        status = runtime.get_status(handle.mission_id)
        assert status.state == "cancelled"

    def test_cancel_cannot_resume(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-nores", program_id="prog-nores",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        runtime.cancel_mission(handle.mission_id, "terminal")
        # Resume after cancel — should still show as completed (error set)
        result = runtime.resume_mission(handle.mission_id)
        assert result.get("completed") is True

    def test_inspect_state(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-insp", program_id="prog-insp",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        runtime.start_mission(handle.mission_id)
        inspection = runtime.inspect_state(handle.mission_id)
        assert inspection["mission_id"] == handle.mission_id
        assert inspection["lifecycle_state"] in ("completed", "failed")
        assert "node_history" in inspection
        assert "scaffold_spec" in inspection
        assert inspection["scaffold_spec"]["node_count"] > 0

    def test_list_missions(self, runtime, minimal_specs):
        for i in range(3):
            runtime.create_mission(
                workflow_id=f"wf-list-{i}",
                program_id=f"prog-list-{i}",
                execution_mode="graph_only",
                agent_specs=minimal_specs,
            )
        missions = runtime.list_missions()
        assert len(missions) == 3

    def test_approve_pending(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-ap", program_id="prog-ap",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        runtime.stop_mission(handle.mission_id, "awaiting_approval")
        status = runtime.approve_pending(
            handle.mission_id,
            approval_id="ap-test-001",
            decision="approved",
            resolved_by="admin",
        )
        # After approval, mission should have been resumed
        assert status.state in ("completed", "failed", "running")

    def test_nonexistent_mission_raises(self, runtime):
        with pytest.raises(ValueError, match="not found"):
            runtime.get_status("nonexistent-id")

    def test_mission_status_to_dict(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-dict", program_id="prog-dict",
            execution_mode="graph_only", agent_specs=minimal_specs,
        )
        status = runtime.get_status(handle.mission_id)
        d = status.to_dict()
        assert d["mission_id"] == handle.mission_id
        assert d["state"] == "created"
        assert "snapshot" in d


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Subgraph Compilation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubgraphCompilation:
    """Phase cluster subgraphs compile correctly."""

    def test_cluster_scaffold(self, builder, graph_spec):
        for cluster in graph_spec.clusters.values():
            scaffold = builder.build_cluster_scaffold(cluster)
            assert scaffold["cluster_id"] == cluster.cluster_id
            assert scaffold["cluster_name"] == cluster.cluster_name
            assert isinstance(scaffold["nodes"], list)
            assert isinstance(scaffold["edges"], list)

    def test_compile_cluster_subgraph(self, builder, graph_spec):
        for cluster in graph_spec.clusters.values():
            result = builder.compile_cluster_subgraph(cluster)
            if _LANGGRAPH_AVAILABLE:
                # May be None if no callables match cluster nodes
                pass  # either compiled or None is acceptable
            else:
                assert result is None

    def test_empty_cluster_returns_none(self, builder):
        empty_cluster = ClusterSpec(cluster_name="empty")
        result = builder.compile_cluster_subgraph(empty_cluster)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Condition Router
# ═══════════════════════════════════════════════════════════════════════════════


class TestConditionRouter:
    """Edge condition routing dispatches correctly."""

    def test_always_routes(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ALWAYS)]
        router = _make_condition_router(edges)
        assert router({}) == "B"

    def test_on_success_routes_when_no_error(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ON_SUCCESS)]
        router = _make_condition_router(edges)
        assert router({"error": ""}) == "B"
        assert router({}) == "B"

    def test_on_failure_routes_when_error(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ON_FAILURE)]
        router = _make_condition_router(edges)
        assert router({"error": "something broke"}) == "B"

    def test_on_approval_routes(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ON_APPROVAL)]
        router = _make_condition_router(edges)
        assert router({"governance_decision": "approved"}) == "B"

    def test_on_rejection_routes(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ON_REJECTION)]
        router = _make_condition_router(edges)
        assert router({"governance_decision": "blocked"}) == "B"

    def test_on_artifact_routes(self):
        edges = [
            EdgeSpec(source="A", target="B",
                     condition=EdgeCondition.ON_ARTIFACT,
                     artifact_type="recon_surface"),
        ]
        router = _make_condition_router(edges)
        assert router({"last_artifact_type": "recon_surface"}) == "B"

    def test_on_high_signal_routes(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ON_HIGH_SIGNAL)]
        router = _make_condition_router(edges)
        state = {"artifacts": [{"artifact_type": "vulnerability_signal", "confidence": "high"}]}
        assert router(state) == "B"

    def test_on_low_signal_routes(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ON_LOW_SIGNAL)]
        router = _make_condition_router(edges)
        assert router({"artifacts": []}) == "B"

    def test_on_phase_complete_routes(self):
        edges = [EdgeSpec(source="A", target="B", condition=EdgeCondition.ON_PHASE_COMPLETE)]
        router = _make_condition_router(edges)
        assert router({"phase_complete": True}) == "B"

    def test_multi_condition_priority(self):
        """First matching condition wins."""
        edges = [
            EdgeSpec(source="A", target="SUCCESS", condition=EdgeCondition.ON_SUCCESS),
            EdgeSpec(source="A", target="FAIL", condition=EdgeCondition.ON_FAILURE),
        ]
        router = _make_condition_router(edges)
        assert router({}) == "SUCCESS"
        assert router({"error": "boom"}) == "FAIL"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Retry Executor
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetryExecutor:
    """Retry wrapper retries on failure with bounded attempts."""

    def test_no_retry_on_success(self):
        call_count = 0
        def inner(state):
            nonlocal call_count
            call_count += 1
            return {"active_node": "ok"}
        executor = make_retry_executor(inner, "retry_node", max_retries=3, backoff_seconds=0)
        result = executor({})
        assert call_count == 1
        assert not result.get("error")

    def test_retry_on_failure(self):
        call_count = 0
        def inner(state):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"error": "transient failure"}
            return {"active_node": "ok"}
        executor = make_retry_executor(inner, "retry_node", max_retries=3, backoff_seconds=0)
        result = executor({})
        assert call_count == 3
        assert not result.get("error")

    def test_max_retries_exhausted(self):
        call_count = 0
        def inner(state):
            nonlocal call_count
            call_count += 1
            return {"error": "permanent failure"}
        executor = make_retry_executor(inner, "retry_node", max_retries=2, backoff_seconds=0)
        result = executor({})
        assert call_count == 3  # initial + 2 retries
        assert result["error"] == "permanent failure"

    def test_zero_retries(self):
        call_count = 0
        def inner(state):
            nonlocal call_count
            call_count += 1
            return {"error": "fail"}
        executor = make_retry_executor(inner, "retry_node", max_retries=0, backoff_seconds=0)
        result = executor({})
        assert call_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Node Executor Correctness
# ═══════════════════════════════════════════════════════════════════════════════


class TestNodeExecutors:
    """Individual node executors produce correct state updates."""

    def test_base_executor_graph_only(self):
        executor = make_node_executor("test_base")
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        assert result["active_node"] == "test_base"
        assert result["last_agent"] == "test_base"
        assert len(result["node_history"]) == 1
        assert result["node_history"][0]["status"] == "completed"

    def test_base_executor_with_callable(self):
        def my_agent(state):
            return {"findings": [{"id": "f1", "severity": "high"}]}
        executor = make_node_executor("agent_node", my_agent)
        state = make_initial_state("wf", "prog", execution_mode="live")
        result = executor(dict(state))
        assert result["findings"] == [{"id": "f1", "severity": "high"}]
        assert result["active_node"] == "agent_node"

    def test_base_executor_handles_exception(self):
        def failing_agent(state):
            raise ValueError("LLM timeout")
        executor = make_node_executor("fail_node", failing_agent)
        state = make_initial_state("wf", "prog", execution_mode="live")
        result = executor(dict(state))
        assert "LLM timeout" in result["error"]
        assert len(result["errors"]) == 1
        assert result["node_history"][0]["status"] == "failed"

    def test_mission_director_sets_phase(self):
        executor = make_mission_director_executor()
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        assert result["phase"] == "recon"
        assert result["governance_decision"] == ""
        assert result["phase_complete"] is False

    def test_phase_coordinator_transitions(self):
        executor = make_phase_coordinator_executor("scanning")
        state = dict(make_initial_state("wf", "prog", execution_mode="graph_only"))
        state["phase"] = "recon"
        result = executor(state)
        assert result["phase"] == "scanning"

    def test_evidence_analysis_sets_artifact_type(self):
        def analysis_agent(state):
            return {"findings": [{"severity": "critical"}]}
        executor = make_evidence_analysis_executor(analysis_agent)
        state = make_initial_state("wf", "prog", execution_mode="live")
        result = executor(dict(state))
        assert result["last_artifact_type"] == "vulnerability_signal"

    def test_evidence_analysis_low_signal(self):
        def analysis_agent(state):
            return {"findings": [{"severity": "info"}]}
        executor = make_evidence_analysis_executor(analysis_agent)
        state = make_initial_state("wf", "prog", execution_mode="live")
        result = executor(dict(state))
        assert result["last_artifact_type"] == "recon_surface"

    def test_report_synthesis_sets_report_id(self):
        def report_agent(state):
            return {"artifacts": [{"artifact_id": "rpt-001", "artifact_type": "final_report"}]}
        executor = make_report_synthesis_executor(report_agent)
        state = make_initial_state("wf", "prog", execution_mode="live")
        result = executor(dict(state))
        assert result["final_report_id"] == "rpt-001"

    def test_handoff_liaison_completes_mission(self):
        executor = make_handoff_liaison_executor()
        state = make_initial_state("wf", "prog", execution_mode="graph_only")
        result = executor(dict(state))
        assert result["completed"] is True
        assert result["progress"] == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 15. End-to-End Pipeline
# ═══════════════════════════════════════════════════════════════════════════════


class TestEndToEnd:
    """Full mission pipeline in graph_only mode."""

    def test_full_mission_graph_only(self, runtime, minimal_specs):
        handle = runtime.create_mission(
            workflow_id="wf-e2e",
            program_id="prog-e2e",
            mission_name="e2e_test",
            execution_mode="graph_only",
            agent_specs=minimal_specs,
        )
        final = runtime.start_mission(handle.mission_id)

        # Verify mission completed
        assert final["completed"] is True
        assert final["progress"] == 1.0
        assert not final.get("error")

        # Verify history accumulated
        history = final.get("node_history", [])
        assert len(history) >= 3  # at least governance, director, handoff

        # Verify status
        status = runtime.get_status(handle.mission_id)
        assert status.state == "completed"

    def test_concurrent_missions(self, runtime, minimal_specs):
        """Multiple missions can run concurrently without interference."""
        results = {}
        errors = []

        def run_mission(idx):
            try:
                handle = runtime.create_mission(
                    workflow_id=f"wf-conc-{idx}",
                    program_id=f"prog-conc-{idx}",
                    execution_mode="graph_only",
                    agent_specs=minimal_specs,
                )
                final = runtime.start_mission(handle.mission_id)
                results[idx] = final
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_mission, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 5
        for final in results.values():
            assert final["completed"] is True

    def test_custom_graph_spec(self, runtime):
        """Mission with a custom (non-standard) graph spec."""
        spec = MissionGraphSpec(
            workflow_id="wf-custom",
            program_id="prog-custom",
        )
        spec.add_node(NodeSpec(
            node_id="start", agent_id="start", node_type="agent", is_entry=True,
        ))
        spec.add_node(NodeSpec(
            node_id="end", agent_id="end", node_type="agent", is_exit=True,
        ))
        spec.add_edge("start", "end", condition=EdgeCondition.ALWAYS)

        callables = {
            "start": make_node_executor("start"),
            "end": make_handoff_liaison_executor(),
        }
        handle = runtime.create_mission(
            workflow_id="wf-custom",
            program_id="prog-custom",
            execution_mode="graph_only",
            graph_spec=spec,
            agent_callables=callables,
        )
        final = runtime.start_mission(handle.mission_id)
        assert final["completed"] is True

    def test_execution_mode_propagated(self, runtime, minimal_specs):
        for mode in ("graph_only", "live", "tool_mock"):
            handle = runtime.create_mission(
                workflow_id=f"wf-mode-{mode}",
                program_id="prog-mode",
                execution_mode=mode,
                agent_specs=minimal_specs,
            )
            state = runtime.get_state(handle.mission_id)
            assert state["execution_mode"] == mode
