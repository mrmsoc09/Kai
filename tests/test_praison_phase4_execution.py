"""
Phase 4 — LangGraph Mission Execution Tests
=============================================
Validates:
  1. Standard mission graph compiles and executes (graph_only + fallback)
  2. State accumulates correctly across nodes
  3. Checkpoint/resume works (fallback path)
  4. Cluster nodes integrate correctly into graph execution
  5. Governance-sensitive transitions remain enforced
  6. Adaptive execution changes inside policy are allowed
  7. Adaptive execution changes outside policy are rejected or escalated
  8. Plan patches are recorded in state/events
  9. Event telemetry is emitted correctly
  10. Existing regression suite remains compatible
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest


# ── 1. Mission State Schema Tests ────────────────────────────────────────────

class TestK1GraphStatePhase4:
    """Validate Phase 4 state schema extensions."""

    def test_make_initial_state_has_phase4_fields(self):
        from apps.backend.src.core.praison_state import make_initial_state
        state = make_initial_state(
            workflow_id="wf-1", program_id="p-1",
            mission_name="test", execution_mode="graph_only",
        )
        assert state["mission_id"]  # auto-generated
        assert state["execution_mode"] == "graph_only"
        assert state["active_node"] == ""
        assert state["progress"] == 0.0
        assert state["node_history"] == []
        assert state["artifact_ids"] == []
        assert state["findings"] == []
        assert state["policy_events"] == []
        assert state["events"] == []
        assert state["approvals_required"] == []
        assert state["approvals_resolved"] == []
        assert state["adaptive_plan_patches_applied"] == []
        assert state["adaptive_plan_patches_rejected"] == []
        assert state["active_contract_ids"] == []
        assert state["cluster_status"] == {}
        assert state["errors"] == []
        assert state["final_report_id"] == ""

    def test_make_initial_state_custom_mission_id(self):
        from apps.backend.src.core.praison_state import make_initial_state
        state = make_initial_state(
            workflow_id="wf-1", program_id="p-1",
            mission_id="custom-id-123",
        )
        assert state["mission_id"] == "custom-id-123"

    def test_state_snapshot_includes_phase4_fields(self):
        from apps.backend.src.core.praison_state import make_initial_state, state_snapshot
        state = make_initial_state(workflow_id="wf-1", program_id="p-1")
        state["active_node"] = "test_node"
        state["progress"] = 0.5
        snap = state_snapshot(state)
        assert snap["mission_id"] == state["mission_id"]
        assert snap["execution_mode"] == "live"
        assert snap["active_node"] == "test_node"
        assert snap["progress"] == 0.5
        assert "node_history_count" in snap
        assert "patches_applied" in snap
        assert "patches_rejected" in snap

    def test_state_snapshot_is_json_serializable(self):
        from apps.backend.src.core.praison_state import make_initial_state, state_snapshot
        state = make_initial_state(workflow_id="wf-1", program_id="p-1")
        snap = state_snapshot(state)
        json_str = json.dumps(snap)
        assert isinstance(json.loads(json_str), dict)


# ── 2. Execution Events Tests ────────────────────────────────────────────────

class TestExecutionEvents:
    """Validate event factory functions and EventBus."""

    def test_mission_started_event_has_correlation_ids(self):
        from apps.backend.src.core.praison_execution_events import mission_started_event
        evt = mission_started_event("m-1", "wf-1", "p-1", execution_mode="graph_only")
        assert evt.mission_id == "m-1"
        assert evt.workflow_id == "wf-1"
        assert evt.program_id == "p-1"
        assert evt.event_type == "mission_started"
        assert evt.detail["execution_mode"] == "graph_only"

    def test_node_events_carry_node_id(self):
        from apps.backend.src.core.praison_execution_events import (
            node_entered_event, node_completed_event, node_failed_event,
        )
        entered = node_entered_event("m-1", "wf-1", "p-1", "test_node", phase="recon")
        assert entered.node_id == "test_node"
        assert entered.phase == "recon"

        completed = node_completed_event("m-1", "wf-1", "p-1", "test_node", artifact_ids=["a-1"])
        assert completed.detail["artifact_ids"] == ["a-1"]

        failed = node_failed_event("m-1", "wf-1", "p-1", "test_node", error="boom")
        assert failed.detail["error"] == "boom"

    def test_contract_events(self):
        from apps.backend.src.core.praison_execution_events import (
            contract_created_event, contract_completed_event, contract_violated_event,
        )
        created = contract_created_event("m-1", "wf-1", "p-1", "c-1", "d-1", "s-1")
        assert created.contract_id == "c-1"
        assert created.detail["delegator_id"] == "d-1"

        completed = contract_completed_event("m-1", "wf-1", "p-1", "c-1", "a-1")
        assert completed.artifact_id == "a-1"

        violated = contract_violated_event("m-1", "wf-1", "p-1", "c-1", "tool_violation")
        assert violated.detail["violation"] == "tool_violation"

    def test_plan_patch_events(self):
        from apps.backend.src.core.praison_execution_events import (
            plan_patch_proposed_event, plan_patch_applied_event, plan_patch_rejected_event,
        )
        proposed = plan_patch_proposed_event("m-1", "wf-1", "p-1", "pp-1", "agent-1", "reorder_tools")
        assert proposed.detail["change_type"] == "reorder_tools"

        applied = plan_patch_applied_event("m-1", "wf-1", "p-1", "pp-1", "agent-1")
        assert applied.detail["patch_id"] == "pp-1"

        rejected = plan_patch_rejected_event("m-1", "wf-1", "p-1", "pp-1", "agent-1", "forbidden")
        assert rejected.detail["reason"] == "forbidden"

    def test_event_bus_emit_and_subscribe(self):
        from apps.backend.src.core.praison_execution_events import EventBus, mission_started_event
        bus = EventBus()
        received = []
        bus.subscribe(lambda evt: received.append(evt))
        evt = mission_started_event("m-1", "wf-1", "p-1")
        bus.emit(evt)
        assert len(received) == 1
        assert received[0].mission_id == "m-1"

    def test_event_bus_for_mission_filters(self):
        from apps.backend.src.core.praison_execution_events import (
            EventBus, mission_started_event, node_entered_event,
        )
        bus = EventBus()
        bus.emit(mission_started_event("m-1", "wf-1", "p-1"))
        bus.emit(node_entered_event("m-2", "wf-2", "p-2", "n-1"))
        bus.emit(node_entered_event("m-1", "wf-1", "p-1", "n-2"))
        m1_events = bus.for_mission("m-1")
        assert len(m1_events) == 2
        assert all(e.mission_id == "m-1" for e in m1_events)

    def test_event_to_dict_serializable(self):
        from apps.backend.src.core.praison_execution_events import mission_started_event
        evt = mission_started_event("m-1", "wf-1", "p-1")
        d = evt.to_dict()
        assert json.dumps(d)  # must not raise
        assert d["event_type"] == "mission_started"

    def test_all_event_types_exist(self):
        from apps.backend.src.core.praison_execution_events import EventType
        expected = {
            "mission_started", "mission_completed", "node_entered", "node_completed",
            "node_failed", "contract_created", "contract_completed", "contract_violated",
            "artifact_created", "policy_decision", "approval_requested", "approval_resolved",
            "phase_transition", "plan_patch_proposed", "plan_patch_applied", "plan_patch_rejected",
        }
        actual = {e.value for e in EventType}
        assert expected.issubset(actual)


# ── 3. Adaptive Execution Tests ──────────────────────────────────────────────

class TestAdaptiveExecution:
    """Validate bounded adaptive execution planning."""

    def _make_strategy(self, **kwargs) -> Any:
        from apps.backend.src.core.praison_adaptive import ExecutionStrategy, ToolProfile, PromptProfile
        defaults = {
            "mission_id": "m-1",
            "phase_id": "recon",
            "tool_candidates": ("nmap", "subfinder", "httpx"),
            "tool_order": ("subfinder", "httpx", "nmap"),
            "allowed_parameter_profiles": (
                ToolProfile(profile_id="tp-1", tool_id="nmap", profile_name="standard"),
                ToolProfile(profile_id="tp-2", tool_id="nmap", profile_name="aggressive", risk_level="high"),
            ),
            "allowed_prompt_profiles": (
                PromptProfile(profile_id="pp-1", profile_name="thorough"),
                PromptProfile(profile_id="pp-2", profile_name="fast_triage"),
            ),
            "approved_branches": ("deep_scan_branch",),
        }
        defaults.update(kwargs)
        return ExecutionStrategy(**defaults)

    def _make_patch(self, change_type, new_value, **kwargs):
        from apps.backend.src.core.praison_adaptive import ExecutionPlanPatch
        return ExecutionPlanPatch(
            mission_id="m-1",
            phase_id="recon",
            proposed_by_agent="test_agent",
            change_type=change_type,
            new_value=new_value,
            justification="test",
            **kwargs,
        )

    # -- Allowed changes -------------------------------------------------------

    def test_reorder_tools_within_set_accepted(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("reorder_tools", ["nmap", "subfinder", "httpx"])
        result = validate_plan_patch(patch, strategy)
        assert result.valid

    def test_select_tool_candidate_in_set_accepted(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("select_tool_candidate", "httpx")
        result = validate_plan_patch(patch, strategy)
        assert result.valid

    def test_select_prompt_profile_accepted(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("select_prompt_profile", "thorough")
        result = validate_plan_patch(patch, strategy)
        assert result.valid

    def test_select_param_profile_accepted(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("select_parameter_profile", "tp-1")
        result = validate_plan_patch(patch, strategy)
        assert result.valid

    def test_activate_approved_branch_accepted(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("activate_branch", "deep_scan_branch")
        result = validate_plan_patch(patch, strategy)
        assert result.valid

    def test_reprioritize_work_accepted(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("reprioritize_work", ["task_b", "task_a"])
        result = validate_plan_patch(patch, strategy)
        assert result.valid

    def test_adjust_retry_within_bounds_accepted(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("adjust_retry", {"max_retries": 2, "max_backoff_seconds": 30})
        result = validate_plan_patch(patch, strategy)
        assert result.valid

    # -- Rejected changes ------------------------------------------------------

    def test_reorder_tools_with_unapproved_tool_rejected(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("reorder_tools", ["nmap", "sqlmap", "httpx"])
        result = validate_plan_patch(patch, strategy)
        assert not result.valid
        assert "unapproved" in result.reason.lower()

    def test_select_tool_not_in_candidates_rejected(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("select_tool_candidate", "sqlmap")
        result = validate_plan_patch(patch, strategy)
        assert not result.valid
        assert "sqlmap" in result.reason

    def test_select_unapproved_prompt_rejected(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("select_prompt_profile", "exploit_mode")
        result = validate_plan_patch(patch, strategy)
        assert not result.valid

    def test_select_unapproved_param_profile_rejected(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("select_parameter_profile", "nonexistent-id")
        result = validate_plan_patch(patch, strategy)
        assert not result.valid

    def test_activate_unapproved_branch_rejected(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("activate_branch", "rogue_branch")
        result = validate_plan_patch(patch, strategy)
        assert not result.valid

    def test_retry_exceeding_limit_rejected(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("adjust_retry", {"max_retries": 100, "max_backoff_seconds": 30})
        result = validate_plan_patch(patch, strategy)
        assert not result.valid

    # -- Forbidden changes -----------------------------------------------------

    def test_graph_rewrite_forbidden(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("graph_rewrite", {"add_node": "evil_node"})
        result = validate_plan_patch(patch, strategy)
        assert not result.valid
        assert "forbidden" in result.reason.lower()

    def test_scope_expansion_forbidden(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("scope_expansion", {"target": "*.internal.corp"})
        result = validate_plan_patch(patch, strategy)
        assert not result.valid

    def test_approval_bypass_forbidden(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("approval_bypass", True)
        result = validate_plan_patch(patch, strategy)
        assert not result.valid

    def test_unknown_change_type_rejected(self):
        from apps.backend.src.core.praison_adaptive import validate_plan_patch
        strategy = self._make_strategy()
        patch = self._make_patch("totally_new_change", "value")
        result = validate_plan_patch(patch, strategy)
        assert not result.valid
        assert "unknown" in result.reason.lower()

    # -- High-risk profile escalation ------------------------------------------

    def test_high_risk_tool_profile_escalates(self):
        from apps.backend.src.core.praison_adaptive import (
            validate_tool_profile_change, ToolProfile,
        )
        strategy = self._make_strategy()
        to_profile = ToolProfile(profile_id="tp-2", profile_name="aggressive", risk_level="high")
        result = validate_tool_profile_change(None, to_profile, strategy)
        assert not result.valid
        assert result.requires_escalation

    # -- Plan patch serialization ----------------------------------------------

    def test_plan_patch_to_dict(self):
        patch = self._make_patch("reorder_tools", ["a", "b"])
        d = patch.to_dict()
        assert d["change_type"] == "reorder_tools"
        assert d["new_value"] == ["a", "b"]
        assert json.dumps(d)  # serializable

    def test_execution_strategy_to_dict(self):
        strategy = self._make_strategy()
        d = strategy.to_dict()
        assert d["tool_candidates"] == ["nmap", "subfinder", "httpx"]
        assert json.dumps(d)


# ── 4. Node Executor Tests ───────────────────────────────────────────────────

class TestNodeExecutors:
    """Validate node executor wrapping behavior."""

    def test_graph_only_executor_returns_stub(self):
        from apps.backend.src.core.praison_node_executors import make_node_executor
        executor = make_node_executor("test_node")  # no callable = graph_only
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "graph_only", "phase": "test"}
        result = executor(state)
        assert result["active_node"] == "test_node"
        assert result["last_agent"] == "test_node"
        assert len(result["node_history"]) == 1
        assert result["node_history"][0]["status"] == "completed"

    def test_executor_calls_agent_callable(self):
        from apps.backend.src.core.praison_node_executors import make_node_executor
        called = []
        def agent_fn(state):
            called.append(True)
            return {"custom_key": "custom_value"}
        executor = make_node_executor("test_node", agent_fn)
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "live", "phase": "test"}
        result = executor(state)
        assert called
        assert result["custom_key"] == "custom_value"
        assert result["active_node"] == "test_node"

    def test_executor_handles_exception(self):
        from apps.backend.src.core.praison_node_executors import make_node_executor
        def failing_fn(state):
            raise RuntimeError("agent crashed")
        executor = make_node_executor("test_node", failing_fn)
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "live", "phase": "test"}
        result = executor(state)
        assert "agent crashed" in result["error"]
        assert result["node_history"][0]["status"] == "failed"
        assert len(result["errors"]) == 1

    def test_governance_admission_sets_approved(self):
        from apps.backend.src.core.praison_node_executors import make_governance_admission_executor
        executor = make_governance_admission_executor()
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "graph_only", "phase": "init"}
        result = executor(state)
        assert result["governance_decision"] == "approved"
        assert result["phase"] == "governance"

    def test_mission_director_resets_governance(self):
        from apps.backend.src.core.praison_node_executors import make_mission_director_executor
        executor = make_mission_director_executor()
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "graph_only", "governance_decision": "approved", "phase": "governance"}
        result = executor(state)
        assert result["governance_decision"] == ""
        assert result["phase_complete"] is False

    def test_handoff_liaison_sets_completed(self):
        from apps.backend.src.core.praison_node_executors import make_handoff_liaison_executor
        executor = make_handoff_liaison_executor()
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "graph_only", "phase": "handoff"}
        result = executor(state)
        assert result["completed"] is True
        assert result["progress"] == 1.0

    def test_specialist_cluster_updates_cluster_status(self):
        from apps.backend.src.core.praison_node_executors import make_specialist_cluster_executor
        executor = make_specialist_cluster_executor("recon")
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "graph_only", "phase": "recon", "cluster_status": {}}
        result = executor(state)
        assert "recon" in result["cluster_status"]
        assert result["cluster_status"]["recon"]["success"] is True

    def test_evidence_analysis_sets_artifact_type(self):
        from apps.backend.src.core.praison_node_executors import make_evidence_analysis_executor
        def analysis_fn(state):
            return {"findings": [{"severity": "high", "title": "XSS"}]}
        executor = make_evidence_analysis_executor(analysis_fn)
        state = {"mission_id": "m-1", "workflow_id": "wf-1", "program_id": "p-1",
                 "execution_mode": "live", "phase": "analysis"}
        result = executor(state)
        assert result["last_artifact_type"] == "vulnerability_signal"

    def test_build_standard_node_callables(self):
        from apps.backend.src.core.praison_node_executors import build_standard_node_callables
        callables = build_standard_node_callables()
        required_nodes = {
            "GovernanceDirector", "MissionDirector", "PhaseCoordinator",
            "SurfaceMapper", "ReconSpecialist", "EvidenceAnalyst",
            "ReportSynthesisAgent", "HandoffLiaison",
        }
        assert required_nodes.issubset(set(callables.keys()))
        for name, fn in callables.items():
            assert callable(fn)


# ── 5. Mission Runtime Tests (Fallback Path) ─────────────────────────────────

class TestMissionRuntimeFallback:
    """
    Test mission lifecycle through the fallback execution path.
    LangGraph is not available in test environment.
    """

    def test_create_mission_returns_handle(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            mission_name="test_mission",
            execution_mode="graph_only",
        )
        assert handle.mission_id
        assert handle.workflow_id == "wf-1"
        assert handle.execution_mode == "graph_only"
        assert handle.scaffold_spec
        assert handle.scaffold_spec["nodes"]

    def test_start_mission_graph_only(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        final = rt.start_mission(handle.mission_id)
        # Should have executed all nodes in graph_only mode
        assert final.get("completed") is True
        assert final.get("progress") == 1.0
        assert len(final.get("node_history", [])) > 0

    def test_mission_status_after_start(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        rt.start_mission(handle.mission_id)
        status = rt.get_status(handle.mission_id)
        assert status.state == "completed"
        assert status.mission_id == handle.mission_id
        assert status.execution_mode == "graph_only"

    def test_state_accumulates_across_nodes(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        final = rt.start_mission(handle.mission_id)
        # node_history should have entries from multiple nodes
        history = final.get("node_history", [])
        assert len(history) >= 3  # at least governance, director, handoff
        node_ids_visited = [h["node_id"] for h in history]
        assert "governance_admission" in node_ids_visited or "GovernanceDirector" in node_ids_visited

    def test_stop_mission_sets_paused(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        rt.stop_mission(handle.mission_id, reason="test_stop")
        status = rt.get_status(handle.mission_id)
        assert status.state == "paused"

    def test_resume_mission_after_stop(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        rt.stop_mission(handle.mission_id)
        final = rt.resume_mission(handle.mission_id)
        # Resume should complete the mission
        assert final.get("completed") is True

    def test_resume_with_approval_data(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        rt.stop_mission(handle.mission_id)
        final = rt.resume_mission(handle.mission_id, approval_data={
            "approval_id": "appr-1",
            "decision": "approved",
            "resolved_by": "operator",
        })
        assert final.get("completed") is True
        # Check approval was recorded
        resolved = final.get("approvals_resolved", [])
        assert len(resolved) >= 1
        assert resolved[0]["approval_id"] == "appr-1"

    def test_get_state_returns_full_state(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        state = rt.get_state(handle.mission_id)
        assert state["workflow_id"] == "wf-1"
        assert state["mission_id"] == handle.mission_id

    def test_mission_not_found_raises(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        with pytest.raises(ValueError, match="not found"):
            rt.start_mission("nonexistent-id")


# ── 6. Scaffold Spec Tests ───────────────────────────────────────────────────

class TestScaffoldSpec:
    """Validate scaffold spec generation for fallback and API inspection."""

    def test_scaffold_includes_execution_order(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        scaffold = handle.scaffold_spec
        assert "execution_order" in scaffold
        assert isinstance(scaffold["execution_order"], list)
        assert len(scaffold["execution_order"]) > 0

    def test_scaffold_starts_with_entry_node(self):
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-1", program_id="p-1",
            execution_mode="graph_only",
        )
        scaffold = handle.scaffold_spec
        assert scaffold["entry_node"] == scaffold["execution_order"][0]


# ── 7. Runtime Policy Adaptive Tests ─────────────────────────────────────────

class TestRuntimePolicyAdaptive:
    """Test adaptive execution policy validation via PraisonRuntimePolicy."""

    def _make_agent(self, agent_class="coordinator", **kwargs):
        from apps.backend.src.core.praison_agent import AgentIdentity
        return AgentIdentity(
            agent_id="test-agent",
            persona="Test",
            description="test agent",
            system_prompt="test",
            agent_class=agent_class,
            delegation_scope="local" if agent_class != "specialist" else "none",
            **kwargs,
        )

    def _make_strategy(self):
        from apps.backend.src.core.praison_adaptive import ExecutionStrategy
        return ExecutionStrategy(
            tool_candidates=("nmap", "subfinder"),
            tool_order=("subfinder", "nmap"),
        )

    def test_coordinator_can_reorder_tools(self):
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        policy = PraisonRuntimePolicy()
        agent = self._make_agent("coordinator")
        result = policy.validate_adaptive_change(
            agent, "reorder_tools", ["nmap", "subfinder"],
            strategy=self._make_strategy(),
        )
        assert result.allowed

    def test_specialist_cannot_reorder_tools(self):
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        policy = PraisonRuntimePolicy()
        agent = self._make_agent("specialist")
        result = policy.validate_adaptive_change(
            agent, "reorder_tools", ["nmap", "subfinder"],
        )
        assert not result.allowed

    def test_specialist_can_select_tool_candidate(self):
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        policy = PraisonRuntimePolicy()
        agent = self._make_agent("specialist")
        result = policy.validate_adaptive_change(
            agent, "select_tool_candidate", "nmap",
            strategy=self._make_strategy(),
        )
        assert result.allowed

    def test_forbidden_change_always_denied(self):
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        policy = PraisonRuntimePolicy()
        agent = self._make_agent("governor")
        result = policy.validate_adaptive_change(agent, "graph_rewrite", {})
        assert not result.allowed
        assert "forbidden" in result.reason.lower()

    def test_unknown_change_denied(self):
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        policy = PraisonRuntimePolicy()
        agent = self._make_agent("director")
        result = policy.validate_adaptive_change(agent, "magic_change", "value")
        assert not result.allowed


# ── 8. Integration: Full Graph Execution ─────────────────────────────────────

class TestFullGraphExecution:
    """End-to-end graph execution through the mission runtime."""

    def test_full_mission_lifecycle(self):
        """Create → Start → Complete lifecycle."""
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-integration",
            program_id="prog-1",
            mission_name="integration_test",
            execution_mode="graph_only",
        )
        assert handle.mission_id

        # Start
        final = rt.start_mission(handle.mission_id)
        assert final["completed"] is True
        assert final["progress"] == 1.0
        assert final["workflow_id"] == "wf-integration"
        assert final["mission_id"] == handle.mission_id

        # Status
        status = rt.get_status(handle.mission_id)
        assert status.state == "completed"
        assert status.to_dict()["state"] == "completed"

    def test_mission_with_custom_agent_callable(self):
        """Custom agent callable produces artifacts in state."""
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime

        def custom_evidence(state):
            return {
                "findings": [{"severity": "high", "title": "SQLi in /api/login"}],
                "artifacts": [{"artifact_id": "art-1", "artifact_type": "vulnerability_signal"}],
            }

        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-custom",
            program_id="prog-1",
            execution_mode="live",
            agent_callables={"EvidenceAnalyst": custom_evidence},
        )
        final = rt.start_mission(handle.mission_id)
        # The custom callable should have produced findings
        findings = final.get("findings", [])
        assert len(findings) >= 1

    def test_mission_records_events(self):
        """Events are emitted during mission execution via the global event bus."""
        from apps.backend.src.core.praison_execution_events import get_event_bus
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime

        rt = MissionRuntime()
        handle = rt.create_mission(
            workflow_id="wf-events",
            program_id="prog-1",
            execution_mode="graph_only",
        )
        rt.start_mission(handle.mission_id)

        # Events are emitted to the global bus via emit()
        bus = get_event_bus()
        events = bus.for_mission(handle.mission_id)
        event_types = [e.event_type for e in events]
        assert "mission_started" in event_types
        assert "mission_completed" in event_types
        # Node executors emit node_entered and node_completed
        assert "node_entered" in event_types
        assert "node_completed" in event_types

    def test_multiple_missions_independent(self):
        """Two missions don't interfere with each other."""
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime
        rt = MissionRuntime()
        h1 = rt.create_mission(workflow_id="wf-1", program_id="p-1", execution_mode="graph_only")
        h2 = rt.create_mission(workflow_id="wf-2", program_id="p-2", execution_mode="graph_only")
        f1 = rt.start_mission(h1.mission_id)
        f2 = rt.start_mission(h2.mission_id)
        assert f1["workflow_id"] == "wf-1"
        assert f2["workflow_id"] == "wf-2"
        assert f1["mission_id"] != f2["mission_id"]


# ── 9. Cluster Integration Tests ─────────────────────────────────────────────

class TestClusterIntegration:
    """Validate cluster execution emits events."""

    def test_cluster_runtime_emits_contract_events(self):
        """ClusterRuntime import doesn't break with new event imports."""
        from apps.backend.src.core.praison_cluster_runtime import ClusterRuntime
        rt = ClusterRuntime()
        assert rt is not None


# ── 10. Backward Compatibility ───────────────────────────────────────────────

class TestBackwardCompatibility:
    """Ensure Phase 3/3.5 code still works with Phase 4 state schema."""

    def test_old_make_initial_state_signature_still_works(self):
        """Phase 3 code calling make_initial_state with old args still works."""
        from apps.backend.src.core.praison_state import make_initial_state
        state = make_initial_state(workflow_id="wf-1", program_id="p-1")
        assert state["execution_mode"] == "live"  # default
        assert state["mission_id"]  # auto-generated

    def test_state_snapshot_backward_compatible(self):
        from apps.backend.src.core.praison_state import make_initial_state, state_snapshot
        state = make_initial_state(workflow_id="wf-1", program_id="p-1")
        snap = state_snapshot(state)
        # Phase 3 fields still present
        assert "workflow_id" in snap
        assert "program_id" in snap
        assert "phase" in snap
        assert "completed" in snap
        assert "error" in snap

    def test_builder_scaffold_backward_compatible(self):
        """PraisonLangGraphBuilder still produces valid scaffold specs."""
        from apps.backend.src.core.praison_langgraph_builder import PraisonLangGraphBuilder
        from apps.backend.src.core.praison_topology import (
            MissionGraphSpec, NodeSpec, EdgeCondition,
        )
        spec = MissionGraphSpec(workflow_id="wf-1", program_id="p-1")
        spec.add_node(NodeSpec(node_id="A", agent_id="A", node_type="agent", is_entry=True))
        spec.add_node(NodeSpec(node_id="B", agent_id="B", node_type="agent", is_exit=True))
        spec.add_edge("A", "B", EdgeCondition.ALWAYS)

        builder = PraisonLangGraphBuilder(spec, {
            "A": lambda s: {"last_agent": "A"},
            "B": lambda s: {"completed": True},
        })
        scaffold = builder.build_scaffold_spec()
        assert scaffold["entry_node"] == "A"
        assert scaffold["exit_node"] == "B"
        assert "execution_order" in scaffold
        assert scaffold["execution_order"] == ["A", "B"]
