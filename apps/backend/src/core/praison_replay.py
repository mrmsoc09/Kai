"""
Mission Replay Layer for K1 / Kai Platform
=============================================
Replays historical mission executions from persisted events, checkpoints,
and artifacts.

Replay sources (in priority order):
  1. EventBus JSONL records (always available)
  2. LangGraph checkpoint data (when PostgreSQL checkpointer is available)
  3. Artifact lineage from artifacts directory
  4. LangSmith trace data (when LangSmith is available)

Replay guarantees:
  - Never re-executes live tools
  - Never re-invokes live models
  - Preserves original mission lineage and correlation IDs
  - Clearly marks all replayed outputs with _replay=True
  - Preserves historical timestamps for debugging
  - New timestamps on replay metadata (replay_started_at, etc.)

Architecture:
  The replay module reconstructs execution context from persisted data.
  It does NOT re-run the mission through LangGraph. Instead, it builds
  a timeline of events and state transitions that can be:
  - Inspected programmatically
  - Fed into the simulation layer as fixture data
  - Visualized by a future frontend
  - Compared against new simulation runs
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# -- Replay timeline entry -----------------------------------------------------


@dataclass
class ReplayTimelineEntry:
    """Single entry in a replayed mission timeline."""

    timestamp: str
    event_type: str
    node_id: str = ""
    agent_id: str = ""
    phase: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    original_event_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "phase": self.phase,
            "detail": self.detail,
            "original_event_id": self.original_event_id,
        }


# -- Replay result -------------------------------------------------------------


@dataclass
class ReplayResult:
    """Result of a mission replay."""

    replay_id: str
    source_mission_id: str
    timeline: list[ReplayTimelineEntry] = field(default_factory=list)
    node_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    final_state: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    replay_started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    replay_completed_at: str = ""
    source_type: str = ""  # "events" | "checkpoints" | "artifacts"
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and len(self.timeline) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "source_mission_id": self.source_mission_id,
            "timeline_length": len(self.timeline),
            "node_count": len(self.node_states),
            "artifact_count": len(self.artifacts),
            "replay_started_at": self.replay_started_at,
            "replay_completed_at": self.replay_completed_at,
            "source_type": self.source_type,
            "success": self.success,
            "error": self.error,
        }


# -- Replay engine -------------------------------------------------------------


class ReplayEngine:
    """
    Reconstructs mission execution from persisted data.

    Thread-safe for reads. Does not modify any persisted state.
    """

    def __init__(self, artifacts_root: str | None = None) -> None:
        self._artifacts_root = Path(
            artifacts_root or os.getenv("K1_ARTIFACTS_ROOT", "artifacts")
        )

    def replay_mission(
        self,
        mission_id: str,
        *,
        from_events: bool = True,
        from_checkpoints: bool = False,
    ) -> ReplayResult:
        """
        Replay a mission from persisted data.

        Args:
            mission_id: Source mission ID to replay.
            from_events: Load from EventBus JSONL records.
            from_checkpoints: Load from LangGraph checkpoints (not yet implemented).

        Returns:
            ReplayResult with timeline, node states, and artifacts.
        """
        import uuid

        replay_id = f"replay-{uuid.uuid4().hex[:12]}"
        result = ReplayResult(
            replay_id=replay_id,
            source_mission_id=mission_id,
        )

        if from_events:
            events = self._load_events_for_mission(mission_id)
            if events:
                result.source_type = "events"
                result.timeline = self._build_timeline(events)
                result.node_states = self._extract_node_states(events)
                result.final_state = self._reconstruct_final_state(events, mission_id)

        # Load artifacts
        result.artifacts = self._load_artifacts_for_mission(mission_id)

        result.replay_completed_at = datetime.now(timezone.utc).isoformat()

        if not result.timeline:
            result.error = f"No replay data found for mission {mission_id}"

        return result

    def get_replay_node_state(
        self, mission_id: str, node_id: str
    ) -> dict[str, Any] | None:
        """
        Load the historical state produced by a specific node in a past mission.

        Returns the node's state output dict, or None if not found.
        """
        events = self._load_events_for_mission(mission_id)
        node_states = self._extract_node_states(events)
        return node_states.get(node_id)

    # -- Event loading ---------------------------------------------------------

    def _load_events_for_mission(
        self, mission_id: str
    ) -> list[dict[str, Any]]:
        """Load events for a mission from JSONL telemetry file."""
        events_path = self._artifacts_root / "telemetry" / "mission_events.jsonl"
        if not events_path.exists():
            return []

        mission_events: list[dict[str, Any]] = []
        try:
            with events_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("mission_id") == mission_id:
                            mission_events.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            logger.warning("Failed to load events for mission %s: %s", mission_id, exc)

        return mission_events

    # -- Timeline building -----------------------------------------------------

    def _build_timeline(
        self, events: list[dict[str, Any]]
    ) -> list[ReplayTimelineEntry]:
        """Build a replay timeline from raw events."""
        timeline: list[ReplayTimelineEntry] = []
        for event in events:
            entry = ReplayTimelineEntry(
                timestamp=event.get("timestamp", ""),
                event_type=event.get("event_type", ""),
                node_id=event.get("node_id", ""),
                agent_id=event.get("agent_id", ""),
                phase=event.get("phase", ""),
                detail=event.get("detail", {}),
                original_event_id=event.get("event_id", ""),
            )
            timeline.append(entry)

        # Sort by timestamp
        timeline.sort(key=lambda e: e.timestamp)
        return timeline

    # -- Node state extraction -------------------------------------------------

    def _extract_node_states(
        self, events: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Extract per-node state from events.

        Looks for node_completed events and uses their detail as the
        node's output state approximation.
        """
        node_states: dict[str, dict[str, Any]] = {}

        for event in events:
            event_type = event.get("event_type", "")
            node_id = event.get("node_id", "")

            if event_type == "node_completed" and node_id:
                node_states[node_id] = {
                    "active_node": node_id,
                    "last_agent": node_id,
                    "phase": event.get("phase", ""),
                    "timestamp": event.get("timestamp", ""),
                    "_replay": True,
                    "_replay_source_event_id": event.get("event_id", ""),
                    **event.get("detail", {}),
                }

        return node_states

    # -- Final state reconstruction --------------------------------------------

    def _reconstruct_final_state(
        self,
        events: list[dict[str, Any]],
        mission_id: str,
    ) -> dict[str, Any]:
        """Reconstruct approximate final state from events."""
        state: dict[str, Any] = {
            "mission_id": mission_id,
            "_replay": True,
        }

        for event in events:
            event_type = event.get("event_type", "")
            detail = event.get("detail", {})

            if event_type == "mission_started":
                state["execution_mode"] = detail.get("execution_mode", "")
                state["workflow_id"] = event.get("workflow_id", "")
                state["program_id"] = event.get("program_id", "")

            elif event_type == "node_completed":
                state["active_node"] = event.get("node_id", "")
                state["phase"] = event.get("phase", "")

            elif event_type == "phase_transition":
                state["phase"] = detail.get("to_phase", "")

            elif event_type == "mission_completed":
                state["completed"] = detail.get("success", False)
                state["final_report_id"] = detail.get("final_report_id", "")

        return state

    # -- Artifact loading ------------------------------------------------------

    def _load_artifacts_for_mission(
        self, mission_id: str
    ) -> list[dict[str, Any]]:
        """Load artifacts from the artifacts directory if they reference this mission."""
        # This is a basic implementation that checks the telemetry for artifact events
        events = self._load_events_for_mission(mission_id)
        artifacts: list[dict[str, Any]] = []
        for event in events:
            if event.get("event_type") == "artifact_created":
                artifacts.append({
                    "artifact_id": event.get("artifact_id", ""),
                    "artifact_type": event.get("detail", {}).get("artifact_type", ""),
                    "producer_id": event.get("agent_id", ""),
                    "timestamp": event.get("timestamp", ""),
                    "_replay": True,
                })
        return artifacts


# -- Module-level convenience --------------------------------------------------


_ENGINE: ReplayEngine | None = None


def get_replay_engine() -> ReplayEngine:
    """Return the module-level ReplayEngine singleton."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ReplayEngine()
    return _ENGINE


def load_replay_node_state(
    mission_id: str,
    node_id: str,
) -> dict[str, Any] | None:
    """
    Load historical node state for replay.

    This is the entry point called by the simulation layer's replay path.
    """
    engine = get_replay_engine()
    return engine.get_replay_node_state(mission_id, node_id)


def replay_mission(
    mission_id: str,
    *,
    from_events: bool = True,
    from_checkpoints: bool = False,
) -> ReplayResult:
    """
    Replay a mission. Module-level convenience function.

    Returns ReplayResult with timeline, node states, artifacts.
    """
    engine = get_replay_engine()
    return engine.replay_mission(
        mission_id,
        from_events=from_events,
        from_checkpoints=from_checkpoints,
    )
