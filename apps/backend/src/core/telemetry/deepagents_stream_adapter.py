"""
DeepAgents Stream Adapter
==========================
Maps DeepAgent execution events into Kai's MissionEvent/EventBus taxonomy.

Responsibilities:
  - Parse DeepAgent execution chunks (planning, tool calls, reasoning steps)
  - Preserve namespace attribution (coordinator vs subagent)
  - Map to Kai MissionEvent with full correlation IDs
  - Support future GUI timeline visualization
  - Handle streaming-safe error and cancellation

Stream event types:
  - deep_agent_started: specialist begins execution
  - deep_agent_step: reasoning iteration (with step number, content preview)
  - deep_agent_tool_call: tool invocation from specialist
  - deep_agent_tool_result: tool result received
  - deep_agent_subagent_started: subagent delegation begins
  - deep_agent_subagent_completed: subagent finishes
  - deep_agent_planning: specialist planning/todo update
  - deep_agent_completed: specialist finishes
  - deep_agent_error: specialist error
  - deep_agent_cancelled: specialist cancelled
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from apps.backend.src.core.praison_execution_events import (
    MissionEvent,
    emit as _emit_event,
    get_event_bus,
)

logger = logging.getLogger(__name__)


# -- Constants ----------------------------------------------------------------

_CONTENT_PREVIEW_MAX: int = 500

_VALID_EVENT_TYPES: frozenset[str] = frozenset({
    "deep_agent_started",
    "deep_agent_step",
    "deep_agent_tool_call",
    "deep_agent_tool_result",
    "deep_agent_subagent_started",
    "deep_agent_subagent_completed",
    "deep_agent_planning",
    "deep_agent_completed",
    "deep_agent_error",
    "deep_agent_cancelled",
})


# -- StreamEvent dataclass ----------------------------------------------------


@dataclass(frozen=True)
class StreamEvent:
    """Normalized DeepAgent stream event."""

    event_type: str  # one of the deep_agent_* types above
    timestamp: str
    agent_id: str
    specialist_type: str
    namespace: str  # "main" for coordinator, "subagent:{id}" for subagents
    mission_id: str
    workflow_id: str
    program_id: str
    node_id: str
    phase: str
    contract_id: str
    step_number: int  # iteration/step counter
    content_preview: str  # truncated content (max 500 chars)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_mission_event(self) -> MissionEvent:
        """Convert to Kai MissionEvent for EventBus emission."""
        return MissionEvent(
            event_type=self.event_type,
            mission_id=self.mission_id,
            workflow_id=self.workflow_id,
            program_id=self.program_id,
            node_id=self.node_id,
            agent_id=self.agent_id,
            contract_id=self.contract_id,
            phase=self.phase,
            detail={
                "specialist_type": self.specialist_type,
                "namespace": self.namespace,
                "step_number": self.step_number,
                "content_preview": self.content_preview,
                **self.detail,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "specialist_type": self.specialist_type,
            "namespace": self.namespace,
            "mission_id": self.mission_id,
            "workflow_id": self.workflow_id,
            "program_id": self.program_id,
            "node_id": self.node_id,
            "phase": self.phase,
            "contract_id": self.contract_id,
            "step_number": self.step_number,
            "content_preview": self.content_preview,
            "detail": self.detail,
        }


# -- DeepAgentStreamAdapter ---------------------------------------------------


class DeepAgentStreamAdapter:
    """
    Processes DeepAgent execution events and maps them to Kai telemetry.

    Usage:
        adapter = DeepAgentStreamAdapter(
            mission_id="m1", workflow_id="w1", program_id="p1",
            node_id="evidence_analysis", agent_id="EvidenceAnalyst",
        )

        # During execution, record events:
        adapter.record_start(specialist_type="evidence_analyst")
        adapter.record_step(step=1, content="Analyzing artifact bundle...")
        adapter.record_tool_call(tool_id="nmap", target="example.com")
        adapter.record_tool_result(tool_id="nmap", success=True)
        adapter.record_completed(success=True, output_preview="Found 3 vulnerabilities")

        # Get all events:
        events = adapter.get_events()

        # Emit to EventBus:
        adapter.flush_to_event_bus()

    Thread-safe: all record_* methods and get_events() are protected by a lock.
    """

    def __init__(
        self,
        mission_id: str,
        workflow_id: str,
        program_id: str,
        node_id: str = "",
        agent_id: str = "",
        phase: str = "",
        specialist_type: str = "",
        event_bus: Any | None = None,
    ) -> None:
        self._mission_id = mission_id
        self._workflow_id = workflow_id
        self._program_id = program_id
        self._node_id = node_id
        self._agent_id = agent_id
        self._phase = phase
        self._specialist_type = specialist_type
        self._event_bus = event_bus
        self._events: list[StreamEvent] = []
        self._step_counter: int = 0
        self._has_errors: bool = False
        self._lock = threading.Lock()

    # -- Record methods --------------------------------------------------------

    def record_start(
        self, specialist_type: str = "", contract_id: str = ""
    ) -> StreamEvent:
        """Record that a specialist has started execution."""
        resolved_type = specialist_type or self._specialist_type
        event = self._make_event(
            event_type="deep_agent_started",
            namespace="main",
            contract_id=contract_id,
            content_preview=f"Specialist {resolved_type} started",
            detail={
                "specialist_type": resolved_type,
                "contract_id": contract_id,
            },
        )
        # Update specialist type if provided
        if specialist_type:
            self._specialist_type = specialist_type
        return event

    def record_step(
        self, step: int, content: str = "", namespace: str = "main"
    ) -> StreamEvent:
        """Record a reasoning iteration/step."""
        with self._lock:
            self._step_counter = max(self._step_counter, step)
        return self._make_event(
            event_type="deep_agent_step",
            namespace=namespace,
            step_number=step,
            content_preview=content,
            detail={"step": step},
        )

    def record_tool_call(
        self, tool_id: str, target: str = "", namespace: str = "main"
    ) -> StreamEvent:
        """Record a tool invocation from the specialist."""
        return self._make_event(
            event_type="deep_agent_tool_call",
            namespace=namespace,
            content_preview=f"Tool call: {tool_id}" + (f" -> {target}" if target else ""),
            detail={"tool_id": tool_id, "target": target},
        )

    def record_tool_result(
        self,
        tool_id: str,
        success: bool,
        output_preview: str = "",
        namespace: str = "main",
    ) -> StreamEvent:
        """Record a tool result received by the specialist."""
        return self._make_event(
            event_type="deep_agent_tool_result",
            namespace=namespace,
            content_preview=output_preview or f"Tool {tool_id}: {'success' if success else 'failed'}",
            detail={
                "tool_id": tool_id,
                "success": success,
                "output_preview": _truncate(output_preview, _CONTENT_PREVIEW_MAX),
            },
        )

    def record_subagent_started(
        self, subagent_id: str, objective: str = "", contract_id: str = ""
    ) -> StreamEvent:
        """Record that a subagent delegation has started."""
        return self._make_event(
            event_type="deep_agent_subagent_started",
            namespace=f"subagent:{subagent_id}",
            contract_id=contract_id,
            content_preview=objective or f"Subagent {subagent_id} started",
            detail={
                "subagent_id": subagent_id,
                "objective": _truncate(objective, _CONTENT_PREVIEW_MAX),
                "contract_id": contract_id,
            },
        )

    def record_subagent_completed(
        self, subagent_id: str, success: bool, output_preview: str = ""
    ) -> StreamEvent:
        """Record that a subagent has completed execution."""
        return self._make_event(
            event_type="deep_agent_subagent_completed",
            namespace=f"subagent:{subagent_id}",
            content_preview=output_preview or f"Subagent {subagent_id}: {'success' if success else 'failed'}",
            detail={
                "subagent_id": subagent_id,
                "success": success,
                "output_preview": _truncate(output_preview, _CONTENT_PREVIEW_MAX),
            },
        )

    def record_planning(
        self,
        plan_summary: str = "",
        todos: list[str] | None = None,
        namespace: str = "main",
    ) -> StreamEvent:
        """Record a planning/todo update from the specialist."""
        resolved_todos = todos or []
        return self._make_event(
            event_type="deep_agent_planning",
            namespace=namespace,
            content_preview=plan_summary or "Planning update",
            detail={
                "plan_summary": _truncate(plan_summary, _CONTENT_PREVIEW_MAX),
                "todos": resolved_todos[:20],  # cap at 20 items
                "todo_count": len(resolved_todos),
            },
        )

    def record_completed(
        self, success: bool, output_preview: str = "", tokens_used: int = 0
    ) -> StreamEvent:
        """Record that the specialist has completed execution."""
        return self._make_event(
            event_type="deep_agent_completed",
            namespace="main",
            content_preview=output_preview or ("Completed successfully" if success else "Completed with failure"),
            detail={
                "success": success,
                "tokens_used": tokens_used,
                "total_steps": self._step_counter,
                "output_preview": _truncate(output_preview, _CONTENT_PREVIEW_MAX),
            },
        )

    def record_error(self, error: str, namespace: str = "main") -> StreamEvent:
        """Record a specialist execution error."""
        with self._lock:
            self._has_errors = True
        return self._make_event(
            event_type="deep_agent_error",
            namespace=namespace,
            content_preview=error,
            detail={"error": error},
        )

    def record_cancelled(self, reason: str = "") -> StreamEvent:
        """Record that the specialist execution was cancelled."""
        return self._make_event(
            event_type="deep_agent_cancelled",
            namespace="main",
            content_preview=reason or "Execution cancelled",
            detail={"reason": reason},
        )

    # -- Query methods ---------------------------------------------------------

    def get_events(self) -> list[StreamEvent]:
        """Return a copy of all recorded events."""
        with self._lock:
            return list(self._events)

    def get_events_as_dicts(self) -> list[dict[str, Any]]:
        """Return all recorded events serialized as dicts."""
        with self._lock:
            return [e.to_dict() for e in self._events]

    def flush_to_event_bus(self) -> int:
        """
        Emit all recorded events to Kai EventBus.

        Returns:
            Count of events successfully emitted.
        """
        with self._lock:
            events_snapshot = list(self._events)

        emitted = 0
        for event in events_snapshot:
            try:
                mission_event = event.to_mission_event()
                if self._event_bus is not None and hasattr(self._event_bus, "emit"):
                    self._event_bus.emit(mission_event)
                else:
                    _emit_event(mission_event)
                emitted += 1
            except Exception as exc:
                logger.warning(
                    "Failed to emit stream event %s for agent %s: %s",
                    event.event_type,
                    event.agent_id,
                    exc,
                )
        return emitted

    @property
    def step_count(self) -> int:
        """Return the highest step number recorded."""
        with self._lock:
            return self._step_counter

    @property
    def has_errors(self) -> bool:
        """True if any error events have been recorded."""
        with self._lock:
            return self._has_errors

    # -- Internal helpers ------------------------------------------------------

    def _make_event(
        self,
        event_type: str,
        namespace: str = "main",
        step_number: int = 0,
        content_preview: str = "",
        contract_id: str = "",
        detail: dict[str, Any] | None = None,
    ) -> StreamEvent:
        """
        Create a StreamEvent, append to the internal list, and return it.

        Thread-safe: appends under self._lock.
        """
        event = StreamEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=self._agent_id,
            specialist_type=self._specialist_type,
            namespace=namespace,
            mission_id=self._mission_id,
            workflow_id=self._workflow_id,
            program_id=self._program_id,
            node_id=self._node_id,
            phase=self._phase,
            contract_id=contract_id,
            step_number=step_number,
            content_preview=_truncate(content_preview, _CONTENT_PREVIEW_MAX),
            detail=detail or {},
        )
        with self._lock:
            self._events.append(event)
        return event


# -- StreamEventFilter --------------------------------------------------------


class StreamEventFilter:
    """
    Filter stream events for display or analysis.

    Supports filtering by:
    - event_type
    - namespace (coordinator vs subagent)
    - time range
    - agent_id

    All methods are static and operate on immutable StreamEvent lists.
    """

    @staticmethod
    def by_namespace(events: list[StreamEvent], namespace: str) -> list[StreamEvent]:
        """Return events matching the specified namespace."""
        return [e for e in events if e.namespace == namespace]

    @staticmethod
    def by_type(events: list[StreamEvent], event_type: str) -> list[StreamEvent]:
        """Return events matching the specified event type."""
        return [e for e in events if e.event_type == event_type]

    @staticmethod
    def main_agent_only(events: list[StreamEvent]) -> list[StreamEvent]:
        """Return only coordinator/main agent events."""
        return [e for e in events if e.namespace == "main"]

    @staticmethod
    def subagent_only(events: list[StreamEvent]) -> list[StreamEvent]:
        """Return only subagent events (namespace starts with 'subagent:')."""
        return [e for e in events if e.namespace.startswith("subagent:")]

    @staticmethod
    def planning_events(events: list[StreamEvent]) -> list[StreamEvent]:
        """Return only planning/todo events."""
        return [e for e in events if e.event_type == "deep_agent_planning"]

    @staticmethod
    def to_timeline(events: list[StreamEvent]) -> list[dict[str, Any]]:
        """
        Convert to timeline-friendly format for future GUI.

        Returns a list of dicts with fields optimized for rendering
        as a chronological event timeline.
        """
        return [
            {
                "timestamp": event.timestamp,
                "type": event.event_type,
                "agent": event.agent_id,
                "namespace": event.namespace,
                "step": event.step_number,
                "preview": event.content_preview,
                "contract_id": event.contract_id,
            }
            for event in events
        ]


# -- Utility ------------------------------------------------------------------


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max_length characters with ellipsis indicator."""
    if not text:
        return text
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
