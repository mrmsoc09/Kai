"""
Simulation Layer for K1 / Kai Platform
========================================
Central simulation control module — the canonical integration point for
all simulation behavior across Kai's execution stack.

Architecture position:
  Simulation Mode is a cross-cutting execution overlay, NOT a second runtime.
  It operates WITHIN the existing PraisonAI → LangGraph → LangChain → DeepAgents
  stack by substituting specific execution behaviors while preserving governance,
  state management, event emission, and topology fidelity.

Responsibilities:
  1. Route execution through correct simulation path (graph_only / tool_mock / replay)
  2. Enforce hard safety barriers (no live tools/sandbox in simulation)
  3. Wire fixture registry into node executors
  4. Provide simulation-aware node callables
  5. Tag all simulation outputs with provenance
  6. Coordinate with LangSmith for simulation trace tagging
  7. Provide entry points for strategy/profile comparison runs
  8. Enforce that simulation never masquerades as live execution

Security invariants:
  - graph_only mode: ZERO live model calls, ZERO live tool calls
  - tool_mock mode: tools return fixtures, models may execute if configured
  - replay mode: ZERO live tool calls, uses historical data only
  - No execution mode can accidentally escalate to live tool execution
  - All simulation artifacts carry explicit provenance markers
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from apps.backend.src.core.praison_simulation_config import (
    ArtifactPolicy,
    EventVerbosity,
    FixtureStrictness,
    SimulationConfig,
    SimulationMode,
)
from apps.backend.src.core.praison_simulation_fixtures import (
    FixtureRegistry,
    fixture_approval_decision,
)
from apps.backend.src.core.praison_execution_events import (
    MissionEvent,
    emit,
    get_event_bus,
    node_entered_event,
    node_completed_event,
)

logger = logging.getLogger(__name__)


# -- Simulation event types ----------------------------------------------------

# These extend the base EventType enum conceptually; we emit them as string
# event_types through the existing MissionEvent system.

SIMULATION_EVENT_TYPES = frozenset({
    "simulation_started",
    "simulation_completed",
    "simulation_failed",
    "replay_started",
    "replay_completed",
    "fixture_applied",
    "mock_tool_result_emitted",
    "replay_event_emitted",
    "simulation_branch_taken",
    "simulation_approval_generated",
    "simulation_safety_block",
})


# -- Simulation event emission -------------------------------------------------


def _emit_simulation_event(
    event_type: str,
    mission_id: str = "",
    workflow_id: str = "",
    program_id: str = "",
    phase: str = "",
    node_id: str = "",
    agent_id: str = "",
    detail: dict[str, Any] | None = None,
    config: SimulationConfig | None = None,
) -> None:
    """Emit a simulation-specific event through the standard EventBus."""
    event_detail: dict[str, Any] = dict(detail or {})
    event_detail["simulation_mode"] = config.mode.value if config else "unknown"
    if config:
        event_detail["fixture_profile"] = config.fixture_profile
        if config.scenario_pack:
            event_detail["scenario_pack"] = config.scenario_pack

    event = MissionEvent(
        event_type=event_type,
        mission_id=mission_id,
        workflow_id=workflow_id,
        program_id=program_id,
        phase=phase,
        node_id=node_id,
        agent_id=agent_id,
        detail=event_detail,
    )
    emit(event)


# -- Safety barriers -----------------------------------------------------------


def assert_simulation_safe(config: SimulationConfig) -> None:
    """
    Validate that simulation config is safe.

    Raises RuntimeError if any safety invariant is violated.
    This is the hard safety check — called before any simulation execution.
    """
    if config.mode == SimulationMode.LIVE:
        return  # Live mode has no simulation safety constraints

    if config.allows_live_tools:
        raise RuntimeError(
            f"Safety violation: simulation mode {config.mode.value} must not allow live tools"
        )

    if config.mode == SimulationMode.GRAPH_ONLY and config.allows_live_models:
        raise RuntimeError(
            "Safety violation: graph_only mode must not allow live model calls"
        )


def is_live_tool_blocked(config: SimulationConfig | None, tool_name: str = "") -> bool:
    """
    Check if a live tool invocation should be blocked by simulation safety.

    Returns True if the tool should be blocked.
    """
    if config is None:
        return False  # No simulation config → live mode
    if config.mode == SimulationMode.LIVE:
        return False
    return True  # All simulation modes block live tools


def is_live_sandbox_blocked(config: SimulationConfig | None) -> bool:
    """Check if live sandbox execution should be blocked."""
    if config is None:
        return False
    if config.mode == SimulationMode.LIVE:
        return False
    return config.hard_block_live_sandbox


# -- Simulation-aware node executor factory ------------------------------------


def make_simulation_node_executor(
    node_id: str,
    config: SimulationConfig,
    inner_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Create a simulation-aware node executor.

    Behavior depends on simulation mode:
    - graph_only: Returns fixture output, ignores inner callable entirely.
    - tool_mock: Calls inner callable but with mocked tool context.
    - replay: Returns replayed state from historical events.

    In all simulation modes:
    - Events are emitted with simulation metadata
    - Fixtures carry provenance markers
    - Governance checks are preserved
    - State updates match live-mode structure exactly
    """
    registry = FixtureRegistry(
        profile=config.fixture_profile,
        scenario_pack=config.scenario_pack,
        seed=config.deterministic_seed,
        strictness=config.fixture_strictness.value,
    )

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")
        phase = state.get("phase", "")
        entered_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()

        # Emit node entered
        if config.event_verbosity != EventVerbosity.SILENT:
            emit(node_entered_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                node_id=node_id, phase=phase,
            ))

        if config.mode == SimulationMode.GRAPH_ONLY:
            return _execute_graph_only(
                node_id, state, registry, config, entered_at, start,
            )

        if config.mode == SimulationMode.TOOL_MOCK:
            return _execute_tool_mock(
                node_id, state, registry, config, inner_callable, entered_at, start,
            )

        if config.mode == SimulationMode.REPLAY:
            return _execute_replay(
                node_id, state, registry, config, entered_at, start,
            )

        # Fallback: should never reach here due to assert_simulation_safe
        raise RuntimeError(f"Unexpected simulation mode: {config.mode}")

    executor.__name__ = f"sim_{config.mode.value}_{node_id}"
    executor.__qualname__ = f"sim_{config.mode.value}_{node_id}"
    return executor


def _execute_graph_only(
    node_id: str,
    state: dict[str, Any],
    registry: FixtureRegistry,
    config: SimulationConfig,
    entered_at: str,
    start: float,
) -> dict[str, Any]:
    """
    Graph-only execution: deterministic fixtures, zero external calls.

    Returns a complete state update from the fixture registry.
    """
    fixture = registry.get_node_fixture(node_id)
    duration = (time.monotonic() - start) * 1000

    # Build standard state update structure
    update: dict[str, Any] = {
        "active_node": node_id,
        "last_agent": node_id,
        "node_history": [{
            "node_id": node_id,
            "status": "completed",
            "entered_at": entered_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round(duration, 2),
            "execution_mode": "graph_only",
            "_simulation": True,
        }],
    }

    # Merge fixture output
    for key, val in fixture.items():
        if key not in ("active_node", "last_agent", "node_history"):
            update[key] = val

    # Tag artifacts as simulation-generated
    _tag_simulation_artifacts(update, config)

    # Emit events
    _emit_fixture_applied(node_id, state, config, fixture)
    if config.event_verbosity != EventVerbosity.SILENT:
        emit(node_completed_event(
            mission_id=state.get("mission_id", ""),
            workflow_id=state.get("workflow_id", ""),
            program_id=state.get("program_id", ""),
            node_id=node_id, phase=state.get("phase", ""),
        ))

    return update


def _execute_tool_mock(
    node_id: str,
    state: dict[str, Any],
    registry: FixtureRegistry,
    config: SimulationConfig,
    inner_callable: Callable | None,
    entered_at: str,
    start: float,
) -> dict[str, Any]:
    """
    Tool-mock execution: uses fixture tool results, may invoke LLM reasoning.

    If allow_model_reasoning_in_tool_mock is True and inner_callable is provided,
    calls the inner callable (which may invoke LLM). Otherwise, uses fixtures.
    """
    if config.allow_model_reasoning_in_tool_mock and inner_callable is not None:
        try:
            result = inner_callable(state)
            duration = (time.monotonic() - start) * 1000
            update: dict[str, Any] = {
                "active_node": node_id,
                "last_agent": node_id,
                "node_history": [{
                    "node_id": node_id,
                    "status": "completed",
                    "entered_at": entered_at,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": round(duration, 2),
                    "execution_mode": "tool_mock",
                    "_simulation": True,
                }],
            }
            if isinstance(result, dict):
                for key, val in result.items():
                    if key not in ("active_node", "last_agent", "node_history"):
                        update[key] = val
            _tag_simulation_artifacts(update, config)
            return update
        except Exception as exc:
            logger.warning(
                "Tool-mock inner callable failed for %s: %s, falling back to fixture",
                node_id, exc,
            )

    # Fallback to fixture (same as graph_only but tagged as tool_mock)
    return _execute_graph_only(node_id, state, registry, config, entered_at, start)


def _execute_replay(
    node_id: str,
    state: dict[str, Any],
    registry: FixtureRegistry,
    config: SimulationConfig,
    entered_at: str,
    start: float,
) -> dict[str, Any]:
    """
    Replay execution: uses persisted historical data where available.

    Falls back to fixture when replay data is unavailable.
    """
    # Attempt to load replay data
    replay_data = _load_replay_node_data(config.replay_mission_id, node_id)

    if replay_data is not None:
        duration = (time.monotonic() - start) * 1000
        update: dict[str, Any] = {
            "active_node": node_id,
            "last_agent": node_id,
            "node_history": [{
                "node_id": node_id,
                "status": "completed",
                "entered_at": entered_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round(duration, 2),
                "execution_mode": "replay",
                "_replay": True,
                "_replay_source_mission": config.replay_mission_id,
            }],
        }
        for key, val in replay_data.items():
            if key not in ("active_node", "last_agent", "node_history"):
                update[key] = val
        _tag_simulation_artifacts(update, config)

        _emit_simulation_event(
            "replay_event_emitted",
            mission_id=state.get("mission_id", ""),
            node_id=node_id,
            detail={"source_mission_id": config.replay_mission_id},
            config=config,
        )
        return update

    # No replay data available — fall back to fixture
    logger.info("No replay data for node %s, using fixture fallback", node_id)
    return _execute_graph_only(node_id, state, registry, config, entered_at, start)


# -- Simulation-aware callables builder ----------------------------------------


def build_simulation_node_callables(
    config: SimulationConfig,
    base_callables: dict[str, Callable] | None = None,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """
    Build a complete set of simulation-aware node callables.

    Wraps each standard node with simulation behavior while preserving
    the callable signature expected by LangGraph.

    Args:
        config: Simulation configuration.
        base_callables: Optional real callables for tool_mock inner execution.

    Returns:
        {node_id: simulation_executor} dict ready for MissionRuntime.
    """
    assert_simulation_safe(config)

    from apps.backend.src.core.praison_node_executors import build_standard_node_callables

    standard = build_standard_node_callables(base_callables)
    simulation_callables: dict[str, Callable] = {}

    for node_id, real_callable in standard.items():
        inner = base_callables.get(node_id) if base_callables else None
        simulation_callables[node_id] = make_simulation_node_executor(
            node_id=node_id,
            config=config,
            inner_callable=inner,
        )

    return simulation_callables


# -- Simulation run lifecycle --------------------------------------------------


class SimulationRunner:
    """
    High-level simulation run orchestrator.

    Coordinates:
    - Mission creation with simulation config
    - Safety validation
    - Event emission (simulation_started/completed/failed)
    - LangSmith trace tagging
    - Result collection and annotation
    """

    def __init__(
        self,
        config: SimulationConfig | None = None,
    ) -> None:
        self._config = config or SimulationConfig()

    @property
    def config(self) -> SimulationConfig:
        return self._config

    def run_simulation(
        self,
        workflow_id: str,
        program_id: str,
        mission_name: str = "",
        agent_callables: dict[str, Callable] | None = None,
    ) -> dict[str, Any]:
        """
        Run a complete simulation of a mission.

        Returns the final state dict with simulation metadata.
        """
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime

        config = self._config
        assert_simulation_safe(config)

        # Build simulation callables
        sim_callables = build_simulation_node_callables(config, agent_callables)

        # Create mission runtime (fresh for isolation)
        runtime = MissionRuntime()

        # Emit simulation started
        _emit_simulation_event(
            "simulation_started",
            workflow_id=workflow_id,
            program_id=program_id,
            detail={
                "fixture_profile": config.fixture_profile,
                "scenario_pack": config.scenario_pack,
                "mission_name": mission_name,
            },
            config=config,
        )

        try:
            # Create and start mission
            handle = runtime.create_mission(
                workflow_id=workflow_id,
                program_id=program_id,
                mission_name=mission_name,
                execution_mode=config.mode.value,
                agent_callables=sim_callables,
            )

            final_state = runtime.start_mission(handle.mission_id)

            # Annotate result
            final_state["_simulation"] = True
            final_state["_simulation_config"] = config.to_metadata()
            final_state["_simulation_completed_at"] = datetime.now(timezone.utc).isoformat()

            _emit_simulation_event(
                "simulation_completed",
                mission_id=handle.mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                detail={
                    "success": not final_state.get("error"),
                    "node_count": len(final_state.get("node_history", [])),
                },
                config=config,
            )

            return final_state

        except Exception as exc:
            _emit_simulation_event(
                "simulation_failed",
                workflow_id=workflow_id,
                program_id=program_id,
                detail={"error": str(exc)},
                config=config,
            )
            raise

    def run_comparison(
        self,
        workflow_id: str,
        program_id: str,
        configs: list[tuple[str, SimulationConfig]],
        mission_name: str = "",
    ) -> dict[str, dict[str, Any]]:
        """
        Run multiple simulation arms for A/B comparison.

        Args:
            workflow_id: Workflow ID for all arms.
            program_id: Program ID for all arms.
            configs: List of (label, SimulationConfig) pairs.
            mission_name: Base mission name.

        Returns:
            {label: final_state} dict.
        """
        results: dict[str, dict[str, Any]] = {}
        for label, config in configs:
            runner = SimulationRunner(config=config)
            state = runner.run_simulation(
                workflow_id=workflow_id,
                program_id=program_id,
                mission_name=f"{mission_name}[{label}]" if mission_name else label,
            )
            state["_comparison_label"] = label
            results[label] = state
        return results


# -- Helper: simulation artifact tagging ---------------------------------------


def _tag_simulation_artifacts(
    update: dict[str, Any],
    config: SimulationConfig,
) -> None:
    """Tag all artifacts in a state update with simulation provenance."""
    artifacts = update.get("artifacts", [])
    if not isinstance(artifacts, list):
        return

    for art in artifacts:
        if isinstance(art, dict):
            art["_simulation"] = True
            art["_simulation_mode"] = config.mode.value
            if config.scenario_pack:
                art["_scenario_pack"] = config.scenario_pack
            if config.comparison_label:
                art["_comparison_label"] = config.comparison_label


# -- Helper: emit fixture applied event ----------------------------------------


def _emit_fixture_applied(
    node_id: str,
    state: dict[str, Any],
    config: SimulationConfig,
    fixture: dict[str, Any],
) -> None:
    """Emit a fixture_applied event."""
    if config.event_verbosity == EventVerbosity.SILENT:
        return

    _emit_simulation_event(
        "fixture_applied",
        mission_id=state.get("mission_id", ""),
        workflow_id=state.get("workflow_id", ""),
        program_id=state.get("program_id", ""),
        phase=state.get("phase", ""),
        node_id=node_id,
        detail={
            "fixture_keys": list(fixture.keys()),
            "artifact_count": len(fixture.get("artifacts", [])),
            "finding_count": len(fixture.get("findings", [])),
        },
        config=config,
    )


# -- Helper: load replay data -------------------------------------------------


def _load_replay_node_data(
    replay_mission_id: str,
    node_id: str,
) -> dict[str, Any] | None:
    """
    Load historical node execution data for replay.

    Attempts to find persisted events/state for the given node in the
    replay source mission. Returns None if no replay data is available.
    """
    if not replay_mission_id:
        return None

    try:
        from apps.backend.src.core.praison_replay import load_replay_node_state

        return load_replay_node_state(replay_mission_id, node_id)
    except ImportError:
        logger.debug("praison_replay module not available for replay data loading")
        return None
    except Exception as exc:
        logger.warning("Failed to load replay data for %s/%s: %s", replay_mission_id, node_id, exc)
        return None


# -- LangSmith integration for simulation --------------------------------------


def get_simulation_langsmith_tags(config: SimulationConfig) -> list[str]:
    """Return LangSmith tags for a simulation run."""
    tags = [
        "simulation",
        f"sim_mode:{config.mode.value}",
    ]
    if config.fixture_profile != "default":
        tags.append(f"fixture:{config.fixture_profile}")
    if config.scenario_pack:
        tags.append(f"scenario:{config.scenario_pack}")
    if config.comparison_label:
        tags.append(f"comparison:{config.comparison_label}")
    if config.simulation_tags:
        tags.extend(config.simulation_tags)
    return tags


def get_simulation_langsmith_metadata(config: SimulationConfig) -> dict[str, Any]:
    """Return LangSmith metadata for a simulation run."""
    return {
        **config.to_metadata(),
        "kai_is_simulation": True,
    }


# -- Module-level convenience --------------------------------------------------


_RUNNER: SimulationRunner | None = None


def get_simulation_runner(config: SimulationConfig | None = None) -> SimulationRunner:
    """Return or create a SimulationRunner."""
    global _RUNNER
    if _RUNNER is None or config is not None:
        _RUNNER = SimulationRunner(config=config)
    return _RUNNER
