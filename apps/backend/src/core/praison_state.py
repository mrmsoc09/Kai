"""
K1 LangGraph State Schema (Phase 4 / 4.5)
============================================
Typed state definition for the K1 mission execution graph.

Phase 3.5 established K1GraphState with basic reducer annotations.
Phase 4 extends it with full mission execution fields:
  - mission_id, execution_mode, active_node, node_history
  - findings, policy_events, approvals_required/resolved
  - cluster_status, progress, final_report_id
  - adaptive_plan_patches_applied/rejected

Phase 4.5 adds learning system fields:
  - strategy_profiles_used: tool/prompt profiles selected per node
  - knowledge_lessons_generated: lessons produced during execution
  - runtime_metrics: performance counters (duration, tool invocations, etc.)

All accumulative fields use Annotated[list, operator.add] reducers.
All scalar fields use last-write-wins (default LangGraph behavior).

Simulation-ready design:
  execution_mode controls whether the graph runs in "live", "graph_only",
  "tool_mock", or "replay" mode. Node executors read this field to decide
  whether to make real tool calls or use mock/replay data.
"""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any, TypedDict


class K1GraphState(TypedDict, total=False):
    """
    Typed state schema for the K1 LangGraph mission execution graph.

    Fields with Annotated[list, operator.add] are ACCUMULATIVE -- each node's
    output list is APPENDED to the existing list (not replaced).

    Fields without annotation are last-write-wins scalars.

    total=False means all fields are optional -- nodes only need to return
    the fields they actually update.
    """

    # -- Mission identity ---------------------------------------------------------
    mission_id: str         # unique execution ID for this mission run
    tenant_id: str
    workflow_id: str
    program_id: str
    mission_name: str

    # -- Execution mode (simulation-ready) ----------------------------------------
    # "live" = real execution, "graph_only" = topology validation only,
    # "tool_mock" = agents run with mock tool results, "replay" = checkpoint replay
    execution_mode: str

    # -- Execution state ----------------------------------------------------------
    phase: str               # current execution phase (e.g. "governance", "recon")
    active_cluster_id: str   # cluster currently executing
    active_node: str         # node_id of the currently executing node
    progress: float          # 0.0 to 1.0 estimated mission progress

    # -- Accumulated collections (reducer = operator.add) -------------------------
    messages: Annotated[list[dict[str, Any]], operator.add]
    artifacts: Annotated[list[dict[str, Any]], operator.add]
    contract_ids: Annotated[list[str], operator.add]
    escalations: Annotated[list[str], operator.add]
    violations: Annotated[list[dict[str, Any]], operator.add]
    node_history: Annotated[list[dict[str, Any]], operator.add]   # {node_id, entered_at, completed_at, status}
    artifact_ids: Annotated[list[str], operator.add]              # artifact_id references
    findings: Annotated[list[dict[str, Any]], operator.add]       # structured finding dicts
    policy_events: Annotated[list[dict[str, Any]], operator.add]  # policy decision records
    events: Annotated[list[dict[str, Any]], operator.add]         # execution events for telemetry
    approvals_required: Annotated[list[dict[str, Any]], operator.add]  # {approval_id, node_id, reason, ...}
    approvals_resolved: Annotated[list[dict[str, Any]], operator.add]  # {approval_id, decision, resolved_by, ...}
    adaptive_plan_patches_applied: Annotated[list[dict[str, Any]], operator.add]
    adaptive_plan_patches_rejected: Annotated[list[dict[str, Any]], operator.add]

    # -- Active state (last-write-wins) -------------------------------------------
    active_contract_ids: list[str]  # currently active contract IDs (replaced on update)

    # -- Routing signals ----------------------------------------------------------
    last_agent: str           # agent_id of most recently completed node
    last_artifact_type: str   # artifact type produced -- drives conditional edge routing
    governance_decision: str  # "approved" | "blocked" | "" -- set by governance nodes

    # -- Cluster status -----------------------------------------------------------
    cluster_status: dict[str, Any]  # {cluster_id: {phase, success, ...}} -- replaced on update

    # -- Pending review -----------------------------------------------------------
    pending_approvals: list[str]  # artifact_ids awaiting HIL review

    # -- Completion signals -------------------------------------------------------
    phase_complete: bool     # coordinator signals phase cluster done
    completed: bool          # HandoffLiaison signals mission end

    # -- Error state --------------------------------------------------------------
    error: str               # non-empty on node failure; drives ON_FAILURE edges
    errors: Annotated[list[dict[str, Any]], operator.add]  # accumulated error records

    # -- Final outputs ------------------------------------------------------------
    final_report_id: str     # artifact_id of the final mission report

    # -- Learning system (Phase 4.5) ---------------------------------------------
    # Strategy profiles selected during execution — {node_id, tool_profile_id, prompt_profile_id}
    strategy_profiles_used: Annotated[list[dict[str, Any]], operator.add]
    # Knowledge lessons produced during this mission — {lesson_id, lesson_type, confidence}
    knowledge_lessons_generated: Annotated[list[dict[str, Any]], operator.add]
    # Runtime performance counters (last-write-wins, aggregated at mission level)
    runtime_metrics: dict[str, Any]


def make_initial_state(
    tenant_id: UUID | str | None = None,
    workflow_id: str = "",
    program_id: str = "",
    mission_name: str = "",
    phase: str = "governance",
    execution_mode: str = "live",
    mission_id: str = "",
) -> K1GraphState:
    """
    Build the initial state dict for a new mission graph execution.
    All accumulative fields start as empty lists.
    All scalar routing fields start with safe defaults.
    """
    if not program_id and workflow_id and isinstance(tenant_id, str):
        legacy_workflow_id = tenant_id
        legacy_program_id = workflow_id
        workflow_id = legacy_workflow_id
        program_id = legacy_program_id
        tenant_id = None

    resolved_tenant = tenant_id if tenant_id is not None else uuid.uuid4()
    return K1GraphState(
        mission_id=mission_id or str(uuid.uuid4()),
        tenant_id=str(resolved_tenant),
        workflow_id=workflow_id,
        program_id=program_id,
        mission_name=mission_name,
        execution_mode=execution_mode,
        phase=phase,
        active_cluster_id="",
        active_node="",
        progress=0.0,
        messages=[],
        artifacts=[],
        contract_ids=[],
        escalations=[],
        violations=[],
        node_history=[],
        artifact_ids=[],
        findings=[],
        policy_events=[],
        events=[],
        approvals_required=[],
        approvals_resolved=[],
        adaptive_plan_patches_applied=[],
        adaptive_plan_patches_rejected=[],
        active_contract_ids=[],
        last_agent="",
        last_artifact_type="",
        governance_decision="",
        cluster_status={},
        pending_approvals=[],
        phase_complete=False,
        completed=False,
        error="",
        errors=[],
        final_report_id="",
        strategy_profiles_used=[],
        knowledge_lessons_generated=[],
        runtime_metrics={},
    )


# -- Accumulative field names (derived from K1GraphState Annotated reducers) ----
# Used by node executors and mission runtime for merge semantics.
# Any field in K1GraphState annotated with ``Annotated[list, operator.add]``
# should be listed here so that merge helpers extend rather than replace.
ACCUMULATIVE_FIELDS: frozenset[str] = frozenset({
    "messages", "artifacts", "contract_ids", "escalations", "violations",
    "node_history", "artifact_ids", "findings", "policy_events", "events",
    "approvals_required", "approvals_resolved",
    "adaptive_plan_patches_applied", "adaptive_plan_patches_rejected",
    "errors", "strategy_profiles_used", "knowledge_lessons_generated",
})


def merge_state(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """
    Merge a node's state update into the base state.

    Accumulative fields (lists) are extended; scalars are replaced.
    This is the canonical merge implementation shared by node executors
    and the mission runtime fallback execution path.
    """
    result = dict(base)
    for key, val in update.items():
        if key in ACCUMULATIVE_FIELDS and isinstance(val, list):
            existing = result.get(key, [])
            if isinstance(existing, list):
                result[key] = existing + val
            else:
                result[key] = val
        else:
            result[key] = val
    return result


def state_snapshot(state: K1GraphState) -> dict[str, Any]:
    """
    Return a serializable snapshot of the current state for audit/checkpointing.
    Truncates large collections to counts to avoid audit log bloat.
    """
    return {
        "mission_id":          state.get("mission_id", ""),
        "workflow_id":         state.get("workflow_id", ""),
        "program_id":          state.get("program_id", ""),
        "execution_mode":      state.get("execution_mode", "live"),
        "phase":               state.get("phase", ""),
        "active_node":         state.get("active_node", ""),
        "progress":            state.get("progress", 0.0),
        "last_agent":          state.get("last_agent", ""),
        "last_artifact_type":  state.get("last_artifact_type", ""),
        "governance_decision": state.get("governance_decision", ""),
        "message_count":       len(state.get("messages", [])),
        "artifact_count":      len(state.get("artifacts", [])),
        "finding_count":       len(state.get("findings", [])),
        "escalation_count":    len(state.get("escalations", [])),
        "violation_count":     len(state.get("violations", [])),
        "node_history_count":  len(state.get("node_history", [])),
        "patches_applied":     len(state.get("adaptive_plan_patches_applied", [])),
        "patches_rejected":    len(state.get("adaptive_plan_patches_rejected", [])),
        "pending_approvals":   state.get("pending_approvals", []),
        "cluster_status":      state.get("cluster_status", {}),
        "phase_complete":      state.get("phase_complete", False),
        "completed":           state.get("completed", False),
        "error":               state.get("error", ""),
        "final_report_id":     state.get("final_report_id", ""),
        "profiles_used_count": len(state.get("strategy_profiles_used", [])),
        "lessons_generated_count": len(state.get("knowledge_lessons_generated", [])),
        "runtime_metrics":     state.get("runtime_metrics", {}),
    }
