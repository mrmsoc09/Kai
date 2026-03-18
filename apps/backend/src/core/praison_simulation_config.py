"""
Simulation Configuration Model for K1 / Kai Platform
======================================================
Typed, explicit configuration for all simulation modes.

Simulation modes:
  - graph_only  : Zero LLM/tool calls. Deterministic fixture-driven topology walk.
  - tool_mock   : LLM reasoning may execute; tools return governed mock results.
  - replay      : Historical execution playback from persisted events/checkpoints.

No implicit mode detection. All simulation behavior is explicitly configured here.

Environment:
  K1_SIMULATION_FAIL_ON_MISSING_FIXTURE — "true" raises on missing fixture (default: "false")
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# -- Simulation mode enum ------------------------------------------------------


class SimulationMode(str, Enum):
    """Explicit simulation mode type."""

    LIVE = "live"
    GRAPH_ONLY = "graph_only"
    TOOL_MOCK = "tool_mock"
    REPLAY = "replay"

    @property
    def is_simulation(self) -> bool:
        """True for any non-live mode."""
        return self != SimulationMode.LIVE

    @property
    def allows_live_tools(self) -> bool:
        """True only in live mode. Hard safety barrier."""
        return self == SimulationMode.LIVE

    @property
    def allows_live_models(self) -> bool:
        """True for live and tool_mock. Graph-only and replay never call LLMs."""
        return self in (SimulationMode.LIVE, SimulationMode.TOOL_MOCK)

    @property
    def uses_fixtures(self) -> bool:
        """True for graph_only and tool_mock (tool fixtures)."""
        return self in (SimulationMode.GRAPH_ONLY, SimulationMode.TOOL_MOCK)

    @property
    def uses_replay_source(self) -> bool:
        """True only for replay mode."""
        return self == SimulationMode.REPLAY


# -- Fixture strictness --------------------------------------------------------


class FixtureStrictness(str, Enum):
    """Controls behavior when a required fixture is missing."""

    STRICT = "strict"  # Raise error on missing fixture
    LENIENT = "lenient"  # Use default/empty fixture
    WARN = "warn"  # Log warning, use default


# -- Artifact generation policy ------------------------------------------------


class ArtifactPolicy(str, Enum):
    """Controls how artifacts are generated in simulation."""

    FULL = "full"  # Generate realistic fixture artifacts
    MINIMAL = "minimal"  # Generate stub artifacts (ID + type only)
    NONE = "none"  # Skip artifact generation entirely


# -- Event verbosity -----------------------------------------------------------


class EventVerbosity(str, Enum):
    """Controls event emission volume in simulation."""

    FULL = "full"  # Emit all events as in live mode
    SUMMARY = "summary"  # Emit key lifecycle events only
    SILENT = "silent"  # Emit no events (testing only)


# -- Simulation configuration -------------------------------------------------


@dataclass(frozen=True)
class SimulationConfig:
    """
    Immutable simulation configuration.

    Every simulation run gets one SimulationConfig. This is the single source
    of truth for how the simulation behaves — no mode detection, no
    environment sniffing at runtime.
    """

    # Core mode
    mode: SimulationMode = SimulationMode.LIVE

    # Fixture control
    fixture_profile: str = "default"  # Named fixture set (e.g., "passive_recon", "high_signal")
    fixture_strictness: FixtureStrictness = FixtureStrictness.LENIENT
    deterministic_seed: int | None = None  # For repeatable random selections

    # Tool mock behavior
    allow_model_reasoning_in_tool_mock: bool = True  # LLM calls in tool_mock mode

    # Replay
    replay_mission_id: str = ""  # Source mission ID for replay
    replay_from_events: bool = True  # Replay from EventBus records
    replay_from_checkpoints: bool = False  # Replay from LangGraph checkpoints

    # Event / telemetry
    event_verbosity: EventVerbosity = EventVerbosity.FULL
    artifact_policy: ArtifactPolicy = ArtifactPolicy.FULL

    # Strategy comparison support
    strategy_comparison_mode: bool = False  # Tag outputs for later A/B comparison
    comparison_label: str = ""  # Label for this comparison arm (e.g., "baseline", "variant_a")

    # Scenario pack
    scenario_pack: str = ""  # Named scenario (e.g., "approval_heavy", "noisy_false_positive")

    # Safety
    hard_block_live_tools: bool = True  # Extra safety: block live tools even if mode is misconfigured
    hard_block_live_sandbox: bool = True  # Block live sandbox execution in simulation

    # Tags for tracing
    simulation_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if self.mode == SimulationMode.REPLAY and not self.replay_mission_id:
            if self.fixture_strictness == FixtureStrictness.STRICT:
                raise ValueError(
                    "Replay mode requires replay_mission_id when fixture_strictness is strict"
                )

    @property
    def is_simulation(self) -> bool:
        return self.mode.is_simulation

    @property
    def allows_live_tools(self) -> bool:
        if self.hard_block_live_tools and self.mode != SimulationMode.LIVE:
            return False
        return self.mode.allows_live_tools

    @property
    def allows_live_models(self) -> bool:
        return self.mode.allows_live_models

    def to_metadata(self) -> dict[str, Any]:
        """Build metadata dict for LangSmith traces and event annotations."""
        meta: dict[str, Any] = {
            "simulation_mode": self.mode.value,
            "fixture_profile": self.fixture_profile,
            "fixture_strictness": self.fixture_strictness.value,
            "artifact_policy": self.artifact_policy.value,
            "event_verbosity": self.event_verbosity.value,
            "is_simulation": self.is_simulation,
        }
        if self.deterministic_seed is not None:
            meta["deterministic_seed"] = self.deterministic_seed
        if self.strategy_comparison_mode:
            meta["strategy_comparison"] = True
            meta["comparison_label"] = self.comparison_label
        if self.scenario_pack:
            meta["scenario_pack"] = self.scenario_pack
        if self.replay_mission_id:
            meta["replay_source_mission_id"] = self.replay_mission_id
        if self.simulation_tags:
            meta["simulation_tags"] = list(self.simulation_tags)
        return meta

    def to_state_fields(self) -> dict[str, Any]:
        """
        Return fields to inject into K1GraphState at mission creation.

        These are carried in the state so that every node executor has
        access to simulation config without needing a global reference.
        """
        return {
            "execution_mode": self.mode.value,
            "_simulation_config": self.to_metadata(),
        }


# -- Factory helpers -----------------------------------------------------------


def make_graph_only_config(
    fixture_profile: str = "default",
    deterministic_seed: int | None = None,
    scenario_pack: str = "",
    **kwargs: Any,
) -> SimulationConfig:
    """Create a graph_only simulation config."""
    return SimulationConfig(
        mode=SimulationMode.GRAPH_ONLY,
        fixture_profile=fixture_profile,
        deterministic_seed=deterministic_seed,
        scenario_pack=scenario_pack,
        **kwargs,
    )


def make_tool_mock_config(
    fixture_profile: str = "default",
    allow_model_reasoning: bool = True,
    scenario_pack: str = "",
    **kwargs: Any,
) -> SimulationConfig:
    """Create a tool_mock simulation config."""
    return SimulationConfig(
        mode=SimulationMode.TOOL_MOCK,
        fixture_profile=fixture_profile,
        allow_model_reasoning_in_tool_mock=allow_model_reasoning,
        scenario_pack=scenario_pack,
        **kwargs,
    )


def make_replay_config(
    replay_mission_id: str,
    replay_from_events: bool = True,
    replay_from_checkpoints: bool = False,
    **kwargs: Any,
) -> SimulationConfig:
    """Create a replay simulation config."""
    return SimulationConfig(
        mode=SimulationMode.REPLAY,
        replay_mission_id=replay_mission_id,
        replay_from_events=replay_from_events,
        replay_from_checkpoints=replay_from_checkpoints,
        **kwargs,
    )


def load_simulation_config_from_env() -> SimulationConfig:
    """
    Load simulation config from environment.

    In production, this returns LIVE config unless explicit env vars are set.
    """
    mode_str = os.getenv("K1_SIMULATION_MODE", "live").lower()
    try:
        mode = SimulationMode(mode_str)
    except ValueError:
        logger.warning("Invalid K1_SIMULATION_MODE '%s', defaulting to live", mode_str)
        mode = SimulationMode.LIVE

    fail_on_missing = os.getenv("K1_SIMULATION_FAIL_ON_MISSING_FIXTURE", "false").lower() == "true"

    return SimulationConfig(
        mode=mode,
        fixture_profile=os.getenv("K1_SIMULATION_FIXTURE_PROFILE", "default"),
        fixture_strictness=(
            FixtureStrictness.STRICT if fail_on_missing else FixtureStrictness.LENIENT
        ),
        replay_mission_id=os.getenv("K1_SIMULATION_REPLAY_MISSION_ID", ""),
        scenario_pack=os.getenv("K1_SIMULATION_SCENARIO_PACK", ""),
    )
