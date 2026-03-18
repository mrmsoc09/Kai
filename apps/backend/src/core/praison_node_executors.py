"""
K1 Mission Graph Node Executors (Phase 4 / 4.5)
==================================================
Typed node callable factories for each standard mission graph node.

Each executor wraps an agent callable with:
  - Event emission (node_entered, node_completed, node_failed)
  - Contract lifecycle (create, validate, activate, complete/violate)
  - Governance checks at sensitive boundaries
  - State update accumulation
  - Error handling and violation recording

Phase 4.5 additions:
  - Governance middleware wrapper (pre-execution validation for any node)
  - Strategy-aware execution (profile selection tracking)
  - Retry-aware execution with bounded retry policy

Node types:
  governance_admission   -- validates mission authorization
  mission_director       -- orchestrates phase sequencing
  phase_coordinator      -- delegates to specialist cluster
  specialist_cluster     -- bounded parallel specialist execution
  evidence_analysis      -- merge/synthesis of specialist outputs
  governance_review      -- approval gate for sensitive findings
  report_synthesis       -- final report generation
  handoff_liaison        -- mission completion and handoff

Simulation-ready:
  All executors read state["execution_mode"]. In "graph_only" mode,
  they return synthetic state updates without calling real agents.
  In "tool_mock" mode, they call agents with mocked tool results.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from apps.backend.src.core.praison_execution_events import (
    emit,
    node_entered_event,
    node_completed_event,
    node_failed_event,
    phase_transition_event,
    approval_requested_event,
    policy_decision_event,
    tool_profile_selected_event,
    prompt_profile_selected_event,
)
from apps.backend.src.core.praison_state import ACCUMULATIVE_FIELDS

logger = logging.getLogger(__name__)


# -- Accumulative state fields (canonical definition lives in praison_state) ----
# Re-exported here for backward compatibility with existing importers.
_ACCUMULATIVE_FIELDS = ACCUMULATIVE_FIELDS


# -- Node history entry builder ------------------------------------------------

def _history_entry(
    node_id: str,
    status: str,
    entered_at: str,
    duration_ms: float = 0.0,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "status": status,
        "entered_at": entered_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round(duration_ms, 2),
    }


# -- Base executor wrapper -----------------------------------------------------

def make_node_executor(
    node_id: str,
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    *,
    node_type: str = "agent",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap a raw agent callable into a LangGraph node function that emits
    events, tracks history, and handles errors.

    If agent_callable is None, the node returns a graph_only stub.
    """

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")
        phase = state.get("phase", "")
        execution_mode = state.get("execution_mode", "live")
        entered_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()

        # Emit node_entered
        emit(node_entered_event(
            mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
            node_id=node_id, phase=phase,
        ))

        # Graph-only simulation: return stub state update
        if execution_mode == "graph_only" or agent_callable is None:
            duration = (time.monotonic() - start) * 1000
            emit(node_completed_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                node_id=node_id, phase=phase,
            ))
            return {
                "active_node": node_id,
                "last_agent": node_id,
                "node_history": [_history_entry(node_id, "completed", entered_at, duration)],
                "events": [{"event_type": "node_completed", "node_id": node_id, "mode": execution_mode}],
            }

        # Real execution
        try:
            result = agent_callable(state)
            duration = (time.monotonic() - start) * 1000

            # Build state update from callable result
            update: dict[str, Any] = {
                "active_node": node_id,
                "last_agent": node_id,
                "node_history": [_history_entry(node_id, "completed", entered_at, duration)],
            }

            # Merge callable output into update (accumulative fields stay as lists)
            if isinstance(result, dict):
                for key, val in result.items():
                    if key in update:
                        continue  # don't override our tracking fields
                    update[key] = val

            # Collect artifact IDs
            artifact_ids = []
            for art in result.get("artifacts", []):
                if isinstance(art, dict) and "artifact_id" in art:
                    artifact_ids.append(art["artifact_id"])
            if artifact_ids:
                update["artifact_ids"] = artifact_ids

            emit(node_completed_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                node_id=node_id, phase=phase, artifact_ids=artifact_ids,
            ))
            return update

        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            error_msg = f"Node {node_id} failed: {exc}"
            logger.error(error_msg, exc_info=True)

            emit(node_failed_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                node_id=node_id, error=str(exc), phase=phase,
            ))
            return {
                "active_node": node_id,
                "last_agent": node_id,
                "error": error_msg,
                "errors": [{"node_id": node_id, "error": str(exc), "timestamp": entered_at}],
                "node_history": [_history_entry(node_id, "failed", entered_at, duration)],
            }

    executor.__name__ = f"node_{node_id}"
    executor.__qualname__ = f"node_{node_id}"
    return executor


# -- Governance admission node -------------------------------------------------

def make_governance_admission_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Mission entry gate. Validates mission authorization before any work begins.
    Sets governance_decision to "approved" or "blocked".
    """
    base = make_node_executor("governance_admission", agent_callable, node_type="governance")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Default to approved if no error and no explicit decision
        if not result.get("error") and not result.get("governance_decision"):
            result["governance_decision"] = "approved"
        elif result.get("error"):
            result["governance_decision"] = "blocked"
        result["phase"] = "governance"
        return result

    executor.__name__ = "governance_admission"
    return executor


# -- Mission director node -----------------------------------------------------

def make_mission_director_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Orchestrates phase sequencing. Sets phase and active_cluster_id.
    """
    base = make_node_executor("mission_director", agent_callable, node_type="director")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        if not result.get("error"):
            result.setdefault("phase", "recon")
            result["governance_decision"] = ""  # reset for next gate
            result["phase_complete"] = False
        return result

    executor.__name__ = "mission_director"
    return executor


# -- Phase coordinator node ----------------------------------------------------

def make_phase_coordinator_executor(
    phase_name: str,
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Coordinates specialists within a phase cluster."""
    node_id = f"phase_coordinator_{phase_name}"
    base = make_node_executor(node_id, agent_callable, node_type="coordinator")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")
        old_phase = state.get("phase", "")

        result = base(state)
        result["phase"] = phase_name

        if old_phase and old_phase != phase_name:
            emit(phase_transition_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                from_phase=old_phase, to_phase=phase_name,
            ))

        return result

    executor.__name__ = node_id
    return executor


# -- Specialist cluster node ---------------------------------------------------

def make_specialist_cluster_executor(
    cluster_name: str,
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    simulation_artifact_type: str = "",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Bounded specialist execution. Cluster node that delegates to specialists
    under DelegationContracts with TTL enforcement.

    simulation_artifact_type: artifact type to set in graph_only/tool_mock mode
      so that ON_ARTIFACT conditional edges can fire during topology validation.
    """
    node_id = f"specialist_cluster_{cluster_name}"
    base = make_node_executor(node_id, agent_callable, node_type="cluster")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Propagate cluster status
        cluster_status = dict(state.get("cluster_status", {}))
        cluster_status[cluster_name] = {
            "phase": state.get("phase", ""),
            "success": not result.get("error"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        result["cluster_status"] = cluster_status
        # In simulation modes, set artifact type so ON_ARTIFACT edges can fire
        execution_mode = state.get("execution_mode", "live")
        if simulation_artifact_type and execution_mode in ("graph_only", "tool_mock"):
            result["last_artifact_type"] = simulation_artifact_type
        return result

    executor.__name__ = node_id
    return executor


# -- Evidence analysis / merge node --------------------------------------------

def make_evidence_analysis_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Merges and synthesizes specialist outputs into findings."""
    base = make_node_executor("evidence_analysis", agent_callable, node_type="analyst")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Determine artifact type for routing
        findings = result.get("findings", [])
        has_significant = any(
            f.get("severity") in ("critical", "high", "medium") for f in findings
        )
        if has_significant:
            result["last_artifact_type"] = "vulnerability_signal"
        else:
            result["last_artifact_type"] = "recon_surface"
        return result

    executor.__name__ = "evidence_analysis"
    return executor


# -- Governance review node (approval gate) ------------------------------------

def make_governance_review_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Approval gate for sensitive findings. May request HIL review.
    Sets governance_decision to "approved" or "blocked".
    """
    base = make_node_executor("governance_review", agent_callable, node_type="governance")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")

        result = base(state)

        if not result.get("governance_decision"):
            result["governance_decision"] = "approved"

        # Emit approval events based on decision
        if result.get("governance_decision") == "approved":
            result["policy_events"] = [{
                "type": "governance_review_passed",
                "node_id": "governance_review",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
        else:
            import uuid
            approval_id = str(uuid.uuid4())
            emit(approval_requested_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                approval_id=approval_id, node_id="governance_review",
                reason=result.get("error", "Governance review required"),
            ))
            result["approvals_required"] = [{
                "approval_id": approval_id,
                "node_id": "governance_review",
                "reason": "Findings require governance approval",
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }]

        return result

    executor.__name__ = "governance_review"
    return executor


# -- Report synthesis node -----------------------------------------------------

def make_report_synthesis_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Generates the final mission report."""
    base = make_node_executor("report_synthesis", agent_callable, node_type="reporter")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Set final_report_id if report artifact was produced
        for art in result.get("artifacts", []):
            if isinstance(art, dict) and art.get("artifact_type") in ("report_draft", "final_report"):
                result["final_report_id"] = art.get("artifact_id", "")
                break
        return result

    executor.__name__ = "report_synthesis"
    return executor


# -- Handoff liaison node (mission completion) ---------------------------------

def make_handoff_liaison_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Mission completion and handoff. Sets completed=True."""
    base = make_node_executor("handoff_liaison", agent_callable, node_type="handoff")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        result["completed"] = True
        result["progress"] = 1.0
        return result

    executor.__name__ = "handoff_liaison"
    return executor


# -- Governance middleware wrapper (Phase 4.5) ---------------------------------

def make_governance_middleware(
    inner_executor: Callable[[dict[str, Any]], dict[str, Any]],
    node_id: str,
    *,
    validate_agent_spawn: Callable[..., None] | None = None,
    validate_tool_request: Callable[..., None] | None = None,
    risk_profile: str = "standard",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap any node executor with pre-execution governance validation.

    Calls governance checks (agent spawn, tool request) before executing
    the inner node. If governance blocks, the node returns a blocked state
    update without executing the inner callable.

    This is the integration point where LangGraph nodes call PraisonGovernor
    validation. Governance is called synchronously on the fast path.
    """

    def governed_executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")

        # Pre-execution governance check
        if validate_agent_spawn is not None:
            try:
                validate_agent_spawn(
                    agent_id=node_id,
                    workflow_id=workflow_id,
                    program_id=program_id,
                    risk_profile=risk_profile,
                )
            except Exception as exc:
                emit(policy_decision_event(
                    mission_id=mission_id,
                    workflow_id=workflow_id,
                    program_id=program_id,
                    decision="blocked",
                    reason=str(exc),
                    node_id=node_id,
                ))
                return {
                    "active_node": node_id,
                    "governance_decision": "blocked",
                    "error": f"Governance blocked node {node_id}: {exc}",
                    "policy_events": [{
                        "type": "governance_blocked",
                        "node_id": node_id,
                        "reason": str(exc),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                    "errors": [{
                        "node_id": node_id,
                        "error": f"Governance blocked: {exc}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                }

        # Execute inner node
        result = inner_executor(state)

        # Record governance pass
        if not result.get("error"):
            emit(policy_decision_event(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                decision="permitted",
                reason="governance_middleware_pass",
                node_id=node_id,
            ))

        return result

    governed_executor.__name__ = f"governed_{node_id}"
    governed_executor.__qualname__ = f"governed_{node_id}"
    return governed_executor


# -- Strategy-aware executor wrapper (Phase 4.5) -------------------------------

def make_strategy_aware_executor(
    inner_executor: Callable[[dict[str, Any]], dict[str, Any]],
    node_id: str,
    *,
    tool_profile_id: str = "",
    prompt_profile_id: str = "",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap a node executor with strategy profile tracking.

    Records which tool/prompt profiles were used for this node's execution.
    Emits profile selection events for telemetry.
    """

    def strategy_executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")

        # Emit profile selection events
        if tool_profile_id:
            emit(tool_profile_selected_event(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                agent_id=node_id,
                profile_id=tool_profile_id,
            ))
        if prompt_profile_id:
            emit(prompt_profile_selected_event(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                agent_id=node_id,
                profile_id=prompt_profile_id,
            ))

        # Execute inner node
        result = inner_executor(state)

        # Record profile usage in state
        if tool_profile_id or prompt_profile_id:
            profile_entry = {
                "node_id": node_id,
                "tool_profile_id": tool_profile_id,
                "prompt_profile_id": prompt_profile_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            result.setdefault("strategy_profiles_used", [])
            if isinstance(result["strategy_profiles_used"], list):
                result["strategy_profiles_used"].append(profile_entry)
            else:
                result["strategy_profiles_used"] = [profile_entry]

        return result

    strategy_executor.__name__ = f"strategy_{node_id}"
    strategy_executor.__qualname__ = f"strategy_{node_id}"
    return strategy_executor


# -- Retry-aware executor wrapper (Phase 4.5) ----------------------------------

def make_retry_executor(
    inner_executor: Callable[[dict[str, Any]], dict[str, Any]],
    node_id: str,
    *,
    max_retries: int = 0,
    backoff_seconds: float = 1.0,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap a node executor with bounded retry logic.

    Retries on failure up to max_retries times with fixed backoff.
    Retry parameters come from ExecutionStrategy.retry_policy.
    """

    def retry_executor(state: dict[str, Any]) -> dict[str, Any]:
        last_result = None
        for attempt in range(max_retries + 1):
            result = inner_executor(state)
            if not result.get("error"):
                return result
            last_result = result
            if attempt < max_retries:
                import time as _time
                _time.sleep(min(backoff_seconds * (attempt + 1), 60.0))
                logger.info(
                    "Node %s retry %d/%d after error: %s",
                    node_id, attempt + 1, max_retries, result.get("error", ""),
                )
        return last_result or {}

    retry_executor.__name__ = f"retry_{node_id}"
    retry_executor.__qualname__ = f"retry_{node_id}"
    return retry_executor


# -- Build standard node callables map -----------------------------------------

def build_standard_node_callables(
    agent_callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]] | None] | None = None,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """
    Build the standard set of LangGraph node callables for a K1 bug bounty mission.

    agent_callables: optional {node_id: raw_callable} for real agent execution.
    If None or missing for a node, that node runs in graph_only mode.

    Returns {node_id: wrapped_executor} ready for PraisonLangGraphBuilder.
    """
    ac = agent_callables or {}

    return {
        "GovernanceDirector": make_governance_admission_executor(ac.get("GovernanceDirector")),
        "MissionDirector": make_mission_director_executor(ac.get("MissionDirector")),
        "PhaseCoordinator": make_phase_coordinator_executor("recon", ac.get("PhaseCoordinator")),
        "SurfaceMapper": make_specialist_cluster_executor(
            "surface_scan", ac.get("SurfaceMapper"), simulation_artifact_type="recon_surface"
        ),
        "ReconSpecialist": make_specialist_cluster_executor(
            "active_recon", ac.get("ReconSpecialist"), simulation_artifact_type="pentest_evidence"
        ),
        "EvidenceAnalyst": make_evidence_analysis_executor(ac.get("EvidenceAnalyst")),
        "ReportSynthesisAgent": make_report_synthesis_executor(ac.get("ReportSynthesisAgent")),
        "HandoffLiaison": make_handoff_liaison_executor(ac.get("HandoffLiaison")),
    }
