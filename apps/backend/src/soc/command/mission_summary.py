from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict

from ..core.praison_execution_events import MissionEvent, get_event_bus
from ..core.attack_surface_graph import AttackSurfaceGraph
from ..core.experience_engine import ExperienceEngine

logger = logging.getLogger(__name__)

class MissionSummaryAgent:
    """
    Aggregates mission telemetry every 15 minutes for the V-RAD 'War Room'.
    """
    def __init__(self, graph: AttackSurfaceGraph, engine: ExperienceEngine):
        self.graph = graph
        self.engine = engine

    def generate_summary(self) -> Dict[str, Any]:
        # Gather metrics
        active_chains = self.graph.calculate_golden_path("root") # Simplified
        reward_velocity = self.engine.exploit_efficiency_ratio()
        
        # Emit MISSION_PULSE if any chain reaches critical phase
        if len(active_chains) > 0:
            self._emit_vrad_pulse("MISSION_PULSE", {"color": "AMBER_GLOW", "phase": "exploitation"})

        return {
            "active_chains": len(active_chains),
            "reward_velocity": reward_velocity,
            "waf_adaptation_rate": 0.85 # Placeholder logic
        }

    def _emit_vrad_pulse(self, event_type: str, detail: Dict[str, Any]):
        try:
            get_event_bus().emit(
                MissionEvent(event_type=event_type, phase="mission_command", detail=detail)
            )
        except Exception:
            pass
