"""
DeepAgents Bridge Layer
========================
Canonical integration point between Kai's mission runtime and DeepAgent specialists.

Dual-path aware (Package Alignment, Phase 5):
  When the official ``deepagents`` PyPI package is installed, the bridge's
  ``execute_specialist()`` delegates to a DeepAgent backed by the real
  compiled graph. When not installed, execution uses Kai's native LLM invoke
  path. Both paths produce the same ``DeepAgentResult`` output type.

Maps:
  - AgentIdentity -> DeepAgentConfig
  - Kai execution context -> DeepAgents runtime context
  - DeepAgentResult -> K1GraphState update
  - DeepAgentResult -> Kai artifacts
  - DeepAgent subagent delegation -> DelegationContract
  - DeepAgent stream events -> Kai MissionEvent/EventBus

This bridge is the ONLY place where Kai-native types convert to/from
DeepAgent types. All other modules work with either Kai types or
DeepAgent types, never both.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from apps.backend.src.core.praison_agent import AgentIdentity
from apps.backend.src.core.praison_contracts import (
    DelegationContract,
    create_delegation_contract,
)
from apps.backend.src.core.praison_adapters.deepagents_adapter import (
    DeepAgent,
    DeepAgentResult,
    _DEEPAGENTS_AVAILABLE,
    create_deep_agent,
)
from apps.backend.src.core.praison_execution_events import (
    EventBus,
    MissionEvent,
    contract_created_event,
    emit,
    get_event_bus,
)
from apps.backend.src.core.praison_runtime_policy import (
    PraisonRuntimePolicy,
    get_runtime_policy,
)

logger = logging.getLogger(__name__)


# -- DeepAgentExecutionContext -------------------------------------------------


@dataclass(frozen=True)
class DeepAgentExecutionContext:
    """
    Full execution context for a DeepAgent specialist call.

    Carries all correlation IDs, input data, and parent context needed to
    configure and execute a DeepAgent. Created by LangGraph node executors
    before invoking the bridge.
    """

    mission_id: str
    workflow_id: str
    program_id: str
    phase: str
    node_id: str
    execution_mode: str  # "live" | "graph_only" | "tool_mock"
    parent_agent_id: str  # the LangGraph node that is invoking this specialist
    parent_contract: DelegationContract | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Defensive copies of mutable inputs."""
        if isinstance(self.artifacts, list):
            object.__setattr__(self, "artifacts", list(self.artifacts))
        if isinstance(self.findings, list):
            object.__setattr__(self, "findings", list(self.findings))
        if isinstance(self.state_snapshot, dict):
            object.__setattr__(self, "state_snapshot", dict(self.state_snapshot))


# -- DeepAgentsBridge ----------------------------------------------------------


class DeepAgentsBridge:
    """
    Bridge between Kai mission runtime and DeepAgent specialists.

    Usage from a LangGraph node executor::

        bridge = get_deepagents_bridge()
        result = await bridge.execute_specialist(
            identity=agent_identity,
            specialist_type="evidence_analyst",
            task="Analyze artifacts for critical vulnerabilities",
            context=execution_context,
            response_format=EvidenceSummary,
        )
        state_update = bridge.result_to_state_update(result)
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        runtime_policy: PraisonRuntimePolicy | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._policy = runtime_policy

    # -- Specialist execution --------------------------------------------------

    async def execute_specialist(
        self,
        identity: AgentIdentity,
        specialist_type: str,
        task: str,
        context: DeepAgentExecutionContext,
        *,
        response_format: type | None = None,
        max_iterations: int | None = None,
        max_subagents: int | None = None,
        sandbox_enabled: bool = False,
    ) -> DeepAgentResult:
        """
        Execute a DeepAgent specialist with full governance.

        Steps:
        1. Validates identity against runtime policy
        2. Creates DeepAgent via create_deep_agent()
        3. Executes task
        4. Emits all events to EventBus
        5. Returns DeepAgentResult

        Args:
            identity: AgentIdentity for the specialist.
            specialist_type: Specialist category (e.g. "evidence_analyst").
            task: Natural language task description.
            context: Full execution context from the mission runtime.
            response_format: Optional Pydantic schema for structured output.
            max_iterations: Override max reasoning iterations.
            max_subagents: Override max subagent concurrency.
            sandbox_enabled: Whether code execution sandbox is available.

        Returns:
            DeepAgentResult with output, artifacts, events, and error state.
        """
        # Step 1: Validate identity against runtime policy
        if self._policy is not None:
            errors = self._policy.validate_identity(identity)
            if errors:
                error_msg = f"Identity validation failed: {errors}"
                logger.warning(
                    "DeepAgentsBridge: identity validation failed for %s: %s",
                    identity.agent_id,
                    errors,
                )
                return DeepAgentResult(
                    agent_id=identity.agent_id,
                    specialist_type=specialist_type,
                    success=False,
                    output={"text": error_msg},
                    error=error_msg,
                )

        # Step 2: Create DeepAgent
        _backend_label = "deepagents" if _DEEPAGENTS_AVAILABLE else "kai_native"
        logger.info(
            "DeepAgentsBridge: executing specialist %s type=%s via %s backend",
            identity.agent_id,
            specialist_type,
            _backend_label,
        )

        agent = create_deep_agent(
            identity,
            specialist_type=specialist_type,
            phase=context.phase,
            execution_mode=context.execution_mode,
            mission_id=context.mission_id,
            workflow_id=context.workflow_id,
            program_id=context.program_id,
            response_format=response_format,
            contract=context.parent_contract,
            max_iterations=max_iterations,
            max_subagents=max_subagents,
            sandbox_enabled=sandbox_enabled,
        )

        # Step 3: Build context dict for DeepAgent
        agent_context: dict[str, Any] = {
            "artifacts": context.artifacts,
            "findings": context.findings,
            "phase": context.phase,
            "node_id": context.node_id,
            "state_snapshot": context.state_snapshot,
        }

        # Step 4: Execute
        if response_format is not None:
            result = await agent.execute_structured(task, response_format, agent_context)
        else:
            result = await agent.execute(task, agent_context)

        # Step 5: Emit events
        self.emit_result_events(result, context)

        return result

    # -- Execution summary -----------------------------------------------------

    def build_execution_summary(self, result: DeepAgentResult) -> dict[str, Any]:
        """Build a summary dict suitable for logging and audit."""
        return {
            "agent_id": result.agent_id,
            "specialist_type": result.specialist_type,
            "success": result.success,
            "iterations_used": result.iterations_used,
            "tokens_used": result.tokens_used,
            "latency_ms": result.latency_ms,
            "artifacts_count": len(result.artifacts_produced),
            "error": result.error,
            "backend": "deepagents" if _DEEPAGENTS_AVAILABLE else "kai_native",
        }

    # -- Result conversion -----------------------------------------------------

    def result_to_state_update(self, result: DeepAgentResult) -> dict[str, Any]:
        """
        Convert DeepAgentResult to K1GraphState-compatible dict.

        Delegates to DeepAgentResult.to_state_update() which is the
        authoritative conversion. This method exists for bridge API
        consistency.
        """
        return result.to_state_update()

    def result_to_artifacts(
        self, result: DeepAgentResult
    ) -> list[dict[str, Any]]:
        """
        Extract artifact dicts from result with provenance metadata.

        Adds bridge-level provenance fields to each artifact dict so that
        downstream consumers can trace the origin.
        """
        artifacts: list[dict[str, Any]] = []
        for artifact in result.artifacts_produced:
            enriched = dict(artifact)
            enriched.setdefault("provenance", {})
            enriched["provenance"].update({
                "bridge": "deepagents",
                "specialist_type": result.specialist_type,
                "agent_id": result.agent_id,
                "success": result.success,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            })
            artifacts.append(enriched)

        # Also extract artifacts from subagent results
        for sub_result in result.subagent_results:
            for artifact in sub_result.artifacts_produced:
                enriched = dict(artifact)
                enriched.setdefault("provenance", {})
                enriched["provenance"].update({
                    "bridge": "deepagents",
                    "specialist_type": sub_result.specialist_type,
                    "agent_id": sub_result.agent_id,
                    "parent_agent_id": result.agent_id,
                    "success": sub_result.success,
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                })
                artifacts.append(enriched)

        return artifacts

    # -- Subagent contract creation --------------------------------------------

    async def create_subagent_contract(
        self,
        parent: AgentIdentity,
        child_agent_id: str,
        child_class: str,
        *,
        objective: str,
        phase: str,
        allowed_tools: list[str] | None = None,
        max_duration_seconds: int = 1800,
    ) -> DelegationContract:
        """
        Create a DelegationContract for DeepAgent subagent delegation.

        Validates:
        - Parent can delegate to child class
        - Parent has delegation_scope != "none"
        - Tools are subset of parent's allowed tools
        - Emits contract_created_event

        Args:
            parent: AgentIdentity of the delegating agent.
            child_agent_id: Unique ID for the child agent.
            child_class: Agent class of the child ("specialist", etc.).
            objective: Natural language objective for the subagent.
            phase: Mission phase for the contract.
            allowed_tools: Tool IDs the subagent may use (subset of parent's).
            max_duration_seconds: TTL for the contract.

        Returns:
            DelegationContract in PENDING state.

        Raises:
            ContractValidationError: If delegation authority or tool subset
                checks fail.
        """
        # Build a minimal child AgentIdentity for contract creation
        child_identity = AgentIdentity(
            agent_id=child_agent_id,
            persona=f"Subagent of {parent.agent_id}",
            description=objective[:100],
            system_prompt="",
            allowed_tools=tuple(allowed_tools) if allowed_tools else parent.allowed_tools,
            agent_class=child_class,
            delegation_scope="none",  # subagents of DeepAgents cannot sub-delegate by default
            workflow_id=parent.workflow_id,
            program_id=parent.program_id,
            parent_agent=parent.agent_id,
        )

        contract = create_delegation_contract(
            delegator=parent,
            delegate=child_identity,
            objective=objective,
            phase=phase,
            allowed_tools=allowed_tools,
            max_duration_seconds=max_duration_seconds,
            can_sub_delegate=False,
        )

        # Emit contract creation event
        event = contract_created_event(
            mission_id=parent.workflow_id,
            workflow_id=parent.workflow_id,
            program_id=parent.program_id,
            contract_id=contract.contract_id,
            delegator_id=parent.agent_id,
            delegate_id=child_agent_id,
            phase=phase,
        )
        self._emit(event)

        logger.debug(
            "Subagent contract created: parent=%s child=%s contract=%s",
            parent.agent_id,
            child_agent_id,
            contract.contract_id,
        )

        return contract

    # -- Event emission --------------------------------------------------------

    def emit_result_events(
        self,
        result: DeepAgentResult,
        context: DeepAgentExecutionContext,
    ) -> None:
        """
        Emit all DeepAgentResult events to Kai EventBus with correlation IDs.

        Each raw event dict from the DeepAgentResult is converted to a
        MissionEvent with full correlation context and emitted through the
        module-level EventBus singleton (or the bridge's explicit event_bus).
        """
        bus = self._event_bus or get_event_bus()

        for raw_event in result.events:
            mission_event = MissionEvent(
                event_type=raw_event.get("event_type", "deep_agent_event"),
                mission_id=context.mission_id,
                workflow_id=context.workflow_id,
                program_id=context.program_id,
                node_id=context.node_id,
                agent_id=result.agent_id,
                phase=context.phase,
                detail=raw_event.get("detail", raw_event),
            )
            bus.emit(mission_event)

    # -- Internal helpers ------------------------------------------------------

    def _emit(self, event: MissionEvent) -> None:
        """Emit a single MissionEvent through the configured bus."""
        bus = self._event_bus or get_event_bus()
        bus.emit(event)


# -- Module singleton ----------------------------------------------------------

_bridge: DeepAgentsBridge | None = None


def get_deepagents_bridge() -> DeepAgentsBridge:
    """
    Return the module-level DeepAgentsBridge singleton.

    Auto-initializes with default event_bus and runtime_policy on first call.
    For explicit configuration, call initialize_deepagents_bridge() first.
    """
    global _bridge
    if _bridge is None:
        _bridge = DeepAgentsBridge(
            event_bus=get_event_bus(),
            runtime_policy=get_runtime_policy(),
        )
    return _bridge


def initialize_deepagents_bridge(
    event_bus: EventBus | None = None,
    runtime_policy: PraisonRuntimePolicy | None = None,
) -> DeepAgentsBridge:
    """
    Create (or replace) the module-level DeepAgentsBridge singleton.

    Should be called once during application startup, typically inside the
    FastAPI lifespan manager after the event bus is initialized.

    Args:
        event_bus: Optional EventBus instance for telemetry.
        runtime_policy: Optional PraisonRuntimePolicy for governance checks.

    Returns:
        The newly created DeepAgentsBridge singleton.
    """
    global _bridge
    _bridge = DeepAgentsBridge(
        event_bus=event_bus or get_event_bus(),
        runtime_policy=runtime_policy or get_runtime_policy(),
    )
    logger.info(
        "DeepAgentsBridge initialized (event_bus=%s, policy=%s)",
        _bridge._event_bus is not None,
        _bridge._policy is not None,
    )
    return _bridge
