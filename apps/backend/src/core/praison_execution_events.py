"""
K1 Mission Execution Events (Phase 4)
=======================================
Backend event foundation for mission telemetry and later GUI/simulation support.

Emits structured events at every execution boundary:
  mission_started, node_entered, node_completed, node_failed,
  contract_created, contract_completed, contract_violated,
  artifact_created, policy_decision, approval_requested, approval_resolved,
  phase_transition, plan_patch_proposed, plan_patch_applied,
  plan_patch_rejected, mission_completed

Every event carries mission/workflow/program correlation identifiers.

Design for simulation:
  EventBus is protocol-based -- simulation can swap in a recording bus
  or a replay bus without changing the emission callsites.

Design for GUI:
  Events are serializable dicts suitable for WebSocket push, log aggregation,
  or JSONL telemetry files.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


# -- Event types ---------------------------------------------------------------

class EventType(str, Enum):
    MISSION_STARTED      = "mission_started"
    MISSION_COMPLETED    = "mission_completed"
    NODE_ENTERED         = "node_entered"
    NODE_COMPLETED       = "node_completed"
    NODE_FAILED          = "node_failed"
    CONTRACT_CREATED     = "contract_created"
    CONTRACT_COMPLETED   = "contract_completed"
    CONTRACT_VIOLATED    = "contract_violated"
    ARTIFACT_CREATED     = "artifact_created"
    POLICY_DECISION      = "policy_decision"
    APPROVAL_REQUESTED   = "approval_requested"
    APPROVAL_RESOLVED    = "approval_resolved"
    PHASE_TRANSITION     = "phase_transition"
    PLAN_PATCH_PROPOSED  = "plan_patch_proposed"
    PLAN_PATCH_APPLIED   = "plan_patch_applied"
    PLAN_PATCH_REJECTED  = "plan_patch_rejected"
    # Learning system events (Phase 4.5)
    STRATEGY_SELECTED    = "strategy_selected"
    TOOL_PROFILE_SELECTED = "tool_profile_selected"
    PROMPT_PROFILE_SELECTED = "prompt_profile_selected"
    PHASE_OUTCOME_SCORED = "phase_outcome_scored"
    KNOWLEDGE_LESSON_CREATED  = "knowledge_lesson_created"
    KNOWLEDGE_LESSON_REJECTED = "knowledge_lesson_rejected"
    PROFILE_SCORE_UPDATED = "profile_score_updated"


# -- MissionEvent dataclass ----------------------------------------------------

@dataclass(frozen=True)
class MissionEvent:
    """
    Structured execution event with full correlation context.

    Frozen -- events are immutable records once created.
    """
    event_id: str           = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str         = ""
    timestamp: str          = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Correlation identifiers (present on every event)
    mission_id: str         = ""
    workflow_id: str        = ""
    program_id: str         = ""

    # Context
    node_id: str            = ""
    agent_id: str           = ""
    contract_id: str        = ""
    artifact_id: str        = ""
    phase: str              = ""

    # Payload (event-specific data)
    detail: dict[str, Any]  = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id":     self.event_id,
            "event_type":   self.event_type,
            "timestamp":    self.timestamp,
            "mission_id":   self.mission_id,
            "workflow_id":  self.workflow_id,
            "program_id":   self.program_id,
            "node_id":      self.node_id,
            "agent_id":     self.agent_id,
            "contract_id":  self.contract_id,
            "artifact_id":  self.artifact_id,
            "phase":        self.phase,
            "detail":       self.detail,
        }


# -- Event factory helpers -----------------------------------------------------

def _make_event(
    event_type: EventType,
    *,
    mission_id: str = "",
    workflow_id: str = "",
    program_id: str = "",
    node_id: str = "",
    agent_id: str = "",
    contract_id: str = "",
    artifact_id: str = "",
    phase: str = "",
    detail: dict[str, Any] | None = None,
) -> MissionEvent:
    return MissionEvent(
        event_type=event_type.value,
        mission_id=mission_id,
        workflow_id=workflow_id,
        program_id=program_id,
        node_id=node_id,
        agent_id=agent_id,
        contract_id=contract_id,
        artifact_id=artifact_id,
        phase=phase,
        detail=detail or {},
    )


def mission_started_event(
    mission_id: str, workflow_id: str, program_id: str,
    execution_mode: str = "live", mission_name: str = "",
    correlation: dict[str, Any] | None = None,
) -> MissionEvent:
    detail = {"execution_mode": execution_mode, "mission_name": mission_name}
    if correlation:
        detail.update(correlation)
    return _make_event(
        EventType.MISSION_STARTED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        detail=detail,
    )


def mission_completed_event(
    mission_id: str, workflow_id: str, program_id: str,
    success: bool = True, final_report_id: str = "",
    metrics: dict[str, Any] | None = None,
) -> MissionEvent:
    detail = {"success": success, "final_report_id": final_report_id}
    if metrics:
        detail["runtime_metrics_summary"] = metrics
    return _make_event(
        EventType.MISSION_COMPLETED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        detail=detail,
    )


def node_entered_event(
    mission_id: str, workflow_id: str, program_id: str,
    node_id: str, agent_id: str = "", phase: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.NODE_ENTERED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        node_id=node_id, agent_id=agent_id, phase=phase,
    )


def node_completed_event(
    mission_id: str, workflow_id: str, program_id: str,
    node_id: str, agent_id: str = "", phase: str = "",
    artifact_ids: list[str] | None = None,
) -> MissionEvent:
    return _make_event(
        EventType.NODE_COMPLETED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        node_id=node_id, agent_id=agent_id, phase=phase,
        detail={"artifact_ids": artifact_ids or []},
    )


def node_failed_event(
    mission_id: str, workflow_id: str, program_id: str,
    node_id: str, error: str, agent_id: str = "", phase: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.NODE_FAILED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        node_id=node_id, agent_id=agent_id, phase=phase,
        detail={"error": error},
    )


def contract_created_event(
    mission_id: str, workflow_id: str, program_id: str,
    contract_id: str, delegator_id: str, delegate_id: str, phase: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.CONTRACT_CREATED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        contract_id=contract_id, phase=phase,
        detail={"delegator_id": delegator_id, "delegate_id": delegate_id},
    )


def contract_completed_event(
    mission_id: str, workflow_id: str, program_id: str,
    contract_id: str, artifact_id: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.CONTRACT_COMPLETED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        contract_id=contract_id, artifact_id=artifact_id,
    )


def contract_violated_event(
    mission_id: str, workflow_id: str, program_id: str,
    contract_id: str, violation: str, detail: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.CONTRACT_VIOLATED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        contract_id=contract_id,
        detail={"violation": violation, "detail": detail},
    )


def artifact_created_event(
    mission_id: str, workflow_id: str, program_id: str,
    artifact_id: str, artifact_type: str, producer_id: str, phase: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.ARTIFACT_CREATED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        artifact_id=artifact_id, agent_id=producer_id, phase=phase,
        detail={"artifact_type": artifact_type},
    )


def policy_decision_event(
    mission_id: str, workflow_id: str, program_id: str,
    decision: str, reason: str, node_id: str = "", agent_id: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.POLICY_DECISION,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        node_id=node_id, agent_id=agent_id,
        detail={"decision": decision, "reason": reason},
    )


def approval_requested_event(
    mission_id: str, workflow_id: str, program_id: str,
    approval_id: str, node_id: str, reason: str,
) -> MissionEvent:
    return _make_event(
        EventType.APPROVAL_REQUESTED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        node_id=node_id,
        detail={"approval_id": approval_id, "reason": reason},
    )


def approval_resolved_event(
    mission_id: str, workflow_id: str, program_id: str,
    approval_id: str, decision: str, resolved_by: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.APPROVAL_RESOLVED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        detail={"approval_id": approval_id, "decision": decision, "resolved_by": resolved_by},
    )


def phase_transition_event(
    mission_id: str, workflow_id: str, program_id: str,
    from_phase: str, to_phase: str,
) -> MissionEvent:
    return _make_event(
        EventType.PHASE_TRANSITION,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        phase=to_phase,
        detail={"from_phase": from_phase, "to_phase": to_phase},
    )


def plan_patch_proposed_event(
    mission_id: str, workflow_id: str, program_id: str,
    patch_id: str, agent_id: str, change_type: str,
) -> MissionEvent:
    return _make_event(
        EventType.PLAN_PATCH_PROPOSED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id,
        detail={"patch_id": patch_id, "change_type": change_type},
    )


def plan_patch_applied_event(
    mission_id: str, workflow_id: str, program_id: str,
    patch_id: str, agent_id: str,
) -> MissionEvent:
    return _make_event(
        EventType.PLAN_PATCH_APPLIED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id,
        detail={"patch_id": patch_id},
    )


def plan_patch_rejected_event(
    mission_id: str, workflow_id: str, program_id: str,
    patch_id: str, agent_id: str, reason: str,
) -> MissionEvent:
    return _make_event(
        EventType.PLAN_PATCH_REJECTED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id,
        detail={"patch_id": patch_id, "reason": reason},
    )


# -- Learning system event factories (Phase 4.5) ------------------------------


def strategy_selected_event(
    mission_id: str, workflow_id: str, program_id: str,
    agent_id: str, strategy_id: str, phase: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.STRATEGY_SELECTED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id, phase=phase,
        detail={"strategy_id": strategy_id},
    )


def tool_profile_selected_event(
    mission_id: str, workflow_id: str, program_id: str,
    agent_id: str, profile_id: str, profile_name: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.TOOL_PROFILE_SELECTED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id,
        detail={"profile_id": profile_id, "profile_name": profile_name},
    )


def prompt_profile_selected_event(
    mission_id: str, workflow_id: str, program_id: str,
    agent_id: str, profile_id: str, profile_name: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.PROMPT_PROFILE_SELECTED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id,
        detail={"profile_id": profile_id, "profile_name": profile_name},
    )


def phase_outcome_scored_event(
    mission_id: str, workflow_id: str, program_id: str,
    phase: str, score: float, detail: dict[str, Any] | None = None,
) -> MissionEvent:
    return _make_event(
        EventType.PHASE_OUTCOME_SCORED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        phase=phase,
        detail={"score": score, **(detail or {})},
    )


def knowledge_lesson_created_event(
    mission_id: str, workflow_id: str, program_id: str,
    lesson_id: str, lesson_type: str, agent_id: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.KNOWLEDGE_LESSON_CREATED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id,
        detail={"lesson_id": lesson_id, "lesson_type": lesson_type},
    )


def knowledge_lesson_rejected_event(
    mission_id: str, workflow_id: str, program_id: str,
    lesson_id: str, reason: str, agent_id: str = "",
) -> MissionEvent:
    return _make_event(
        EventType.KNOWLEDGE_LESSON_REJECTED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        agent_id=agent_id,
        detail={"lesson_id": lesson_id, "reason": reason},
    )


def profile_score_updated_event(
    mission_id: str, workflow_id: str, program_id: str,
    profile_id: str, profile_type: str, new_score: float,
) -> MissionEvent:
    return _make_event(
        EventType.PROFILE_SCORE_UPDATED,
        mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
        detail={"profile_id": profile_id, "profile_type": profile_type, "new_score": new_score},
    )


# -- EventBus ------------------------------------------------------------------

EventSubscriber = Callable[[MissionEvent], None]


class EventBus:
    """
    Thread-safe event bus for mission execution telemetry.

    Subscribers receive every event. Events are also persisted to JSONL
    for offline analysis and replay simulation.

    Simulation-ready:
      - Swap EventBus for a RecordingBus or ReplayBus without changing callsites
      - All emission goes through emit() -- single instrumentation point
    """

    def __init__(self) -> None:
        self._subscribers: list[EventSubscriber] = []
        self._lock = threading.Lock()
        self._file_lock = threading.Lock()
        self._events: list[MissionEvent] = []

    def subscribe(self, callback: EventSubscriber) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def emit(self, event: MissionEvent) -> None:
        """Emit event to all subscribers and persist to disk."""
        # Visual Synthesis Throttling: Check SILENT_MODE
        from ..executive.executive_manager import ExecutiveManager
        is_silent = ExecutiveManager().silent_mode
        
        # High-intensity visual events to skip in silent mode
        visual_event_types = {"tool_execution", "phase_transition", "node_entered", "node_completed"}
        
        with self._lock:
            self._events.append(event)
            subscribers = list(self._subscribers)

        for sub in subscribers:
            try:
                # If silent mode is on, skip broadcasting visual-only telemetry
                if is_silent and event.event_type in visual_event_types:
                    continue
                sub(event)
            except Exception as exc:
                logger.warning("Event subscriber error for %s: %s", event.event_type, exc)

        self._persist(event)

    def recent(self, limit: int = 50) -> list[MissionEvent]:
        with self._lock:
            return list(self._events[-limit:])

    def for_mission(self, mission_id: str) -> list[MissionEvent]:
        with self._lock:
            return [e for e in self._events if e.mission_id == mission_id]

    def _persist(self, event: MissionEvent) -> None:
        root = Path(os.getenv("K1_ARTIFACTS_ROOT", "artifacts"))
        path = root / "telemetry" / "mission_events.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._file_lock:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event.to_dict()) + "\n")
        except Exception as exc:
            logger.warning("Failed to persist event %s: %s", event.event_id, exc)


# -- Module singleton ----------------------------------------------------------

_BUS = EventBus()


def get_event_bus() -> EventBus:
    return _BUS


def reset_event_bus() -> EventBus:
    """Reset the module-level EventBus singleton. For test isolation only."""
    global _BUS
    _BUS = EventBus()
    return _BUS


def emit(event: MissionEvent) -> None:
    """Convenience: emit through the module singleton."""
    _BUS.emit(event)
