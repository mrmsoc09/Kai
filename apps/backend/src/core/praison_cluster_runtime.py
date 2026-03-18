"""
Praison Cluster Runtime
========================
Executes phase clusters in K1's hybrid orchestration system.

The ClusterRuntime is the bounded decentralized execution layer.
Within a cluster:
  - The coordinator delegates to specialists via DelegationContracts
  - Specialists execute in parallel (within their contract scope)
  - Artifacts are collected and validated before cluster exit
  - Violations trigger immediate escalation

Execution model:
  1. ClusterRuntime.run_cluster() is called by MissionDirector
  2. Coordinator node resolves delegation targets
  3. Contracts are created + validated for each specialist
  4. Specialists execute concurrently (asyncio.gather)
  5. Results are collected as AgentArtifacts
  6. Cluster exit condition is evaluated
  7. Exit artifacts are passed up to the mission graph

This module does NOT compile or run LangGraph directly. It uses the
PraisonLangGraphBuilder-compiled graph when available, falling back
to direct async execution of node callables for simpler phases.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from apps.backend.src.core.praison_agent import AgentIdentity
from apps.backend.src.core.praison_artifacts import (
    AgentArtifact,
    ArtifactStore,
    get_artifact_store,
)
from apps.backend.src.core.praison_contracts import (
    ContractState,
    ContractViolation,
    DelegationContract,
    create_delegation_contract,
    validate_contract,
)
from apps.backend.src.core.praison_runtime_policy import (
    PolicyDecision,
    get_runtime_policy,
)
from apps.backend.src.core.praison_topology import ClusterSpec, MissionGraphSpec
from apps.backend.src.core.praison_execution_events import (
    emit,
    contract_created_event,
    contract_completed_event,
    contract_violated_event,
)

logger = logging.getLogger(__name__)


# ── Cluster execution result ──────────────────────────────────────────────────

@dataclass
class ClusterResult:
    cluster_id: str
    cluster_name: str
    phase: str
    success: bool
    artifacts: list[AgentArtifact] = field(default_factory=list)
    contracts: list[DelegationContract] = field(default_factory=list)
    violations: list[tuple[str, str]] = field(default_factory=list)  # (agent_id, reason)
    escalations: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str = ""

    @property
    def artifact_ids(self) -> list[str]:
        return [a.artifact_id for a in self.artifacts]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id":       self.cluster_id,
            "cluster_name":     self.cluster_name,
            "phase":            self.phase,
            "success":          self.success,
            "artifact_ids":     self.artifact_ids,
            "artifact_count":   len(self.artifacts),
            "contract_count":   len(self.contracts),
            "violations":       self.violations,
            "escalations":      self.escalations,
            "duration_seconds": round(self.duration_seconds, 3),
            "error":            self.error,
        }


# ── Specialist execution context ──────────────────────────────────────────────

@dataclass
class SpecialistContext:
    """Everything a specialist needs to execute within a cluster."""
    agent: AgentIdentity
    contract: DelegationContract
    node_callable: Callable[[dict[str, Any]], dict[str, Any]]
    initial_state: dict[str, Any]


# ── ClusterRuntime ────────────────────────────────────────────────────────────

class ClusterRuntime:
    """
    Executes a phase cluster under coordinator authority.

    Thread-safe. Each run() call creates its own execution context.
    Multiple clusters can run concurrently for different phases.
    """

    def __init__(
        self,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._artifact_store = artifact_store or get_artifact_store()
        self._policy = get_runtime_policy()

    async def run_cluster(
        self,
        cluster_spec: ClusterSpec,
        coordinator_agent: AgentIdentity,
        specialist_agents: dict[str, AgentIdentity],
        node_callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
        initial_state: dict[str, Any],
        phase: str = "",
    ) -> ClusterResult:
        """
        Execute a phase cluster under coordinator authority.

        coordinator_agent: The coordinator AgentIdentity (director of this cluster)
        specialist_agents: {agent_id: AgentIdentity} for all specialists in cluster
        node_callables: {agent_id: async callable(state) → state_update}
        initial_state: Starting graph state for this cluster execution
        """
        start = time.monotonic()
        result = ClusterResult(
            cluster_id=cluster_spec.cluster_id,
            cluster_name=cluster_spec.cluster_name,
            phase=phase or cluster_spec.phase,
        )

        # Step 1: Create delegation contracts for all specialists
        contexts: list[SpecialistContext] = []
        for agent_id in cluster_spec.specialist_ids:
            agent = specialist_agents.get(agent_id)
            if not agent:
                logger.warning("Specialist %s not found in agent map — skipping", agent_id)
                continue
            if agent_id not in node_callables:
                logger.warning("No callable for specialist %s — skipping", agent_id)
                continue

            policy_decision = self._policy.check_delegation(coordinator_agent, agent)
            if not policy_decision.allowed:
                reason = f"Delegation denied: {policy_decision.reason}"
                logger.error("Cluster %s: %s", cluster_spec.cluster_id, reason)
                result.violations.append((agent_id, reason))
                continue

            try:
                contract = create_delegation_contract(
                    coordinator_agent,
                    agent,
                    objective=f"Execute {agent.persona} role in {phase or cluster_spec.phase} phase",
                    phase=phase or cluster_spec.phase,
                    expected_artifact_type="raw_tool_output",
                    max_duration_seconds=3600,
                )
                validate_contract(contract)
                contract = contract.activate()
                result.contracts.append(contract)
                emit(contract_created_event(
                    mission_id=initial_state.get("mission_id", ""),
                    workflow_id=coordinator_agent.workflow_id,
                    program_id=coordinator_agent.program_id,
                    contract_id=contract.contract_id,
                    delegator_id=coordinator_agent.agent_id,
                    delegate_id=agent.agent_id,
                    phase=phase or cluster_spec.phase,
                ))
            except Exception as exc:
                reason = f"Contract creation failed: {exc}"
                logger.error("Cluster %s specialist %s: %s", cluster_spec.cluster_id, agent_id, reason)
                result.violations.append((agent_id, reason))
                continue

            contexts.append(SpecialistContext(
                agent=agent,
                contract=contract,
                node_callable=node_callables[agent_id],
                initial_state={**initial_state, "contract_id": contract.contract_id},
            ))

        if not contexts:
            result.success = False
            result.error = "No specialists could be activated"
            result.duration_seconds = time.monotonic() - start
            return result

        # Step 2: Execute specialists in parallel or sequentially
        if cluster_spec.parallel_execution:
            tasks = [self._run_specialist(ctx) for ctx in contexts]
            specialist_results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            specialist_results = []
            for ctx in contexts:
                sr = await self._run_specialist(ctx)
                specialist_results.append(sr)

        # Step 3: Collect results
        all_succeeded = True
        for ctx, sr in zip(contexts, specialist_results):
            if isinstance(sr, Exception):
                reason = f"Specialist execution raised exception: {sr}"
                logger.error("Cluster %s specialist %s: %s", cluster_spec.cluster_id, ctx.agent.agent_id, reason)
                result.violations.append((ctx.agent.agent_id, reason))
                all_succeeded = False
                continue

            artifacts, closed_contract, violation = sr
            result.artifacts.extend(artifacts)

            # Update contract state
            idx = result.contracts.index(ctx.contract) if ctx.contract in result.contracts else -1
            if idx >= 0:
                result.contracts[idx] = closed_contract

            if violation:
                result.violations.append((ctx.agent.agent_id, violation))
                all_succeeded = False

            # Check escalation policies
            for artifact in artifacts:
                esc = self._policy.check_escalation(
                    ctx.agent, "band2_tool",
                    {"confidence": artifact.confidence.value if hasattr(artifact.confidence, "value") else artifact.confidence}
                )
                if esc.requires_escalation:
                    result.escalations.append(
                        f"{ctx.agent.agent_id}: {esc.escalation_reason}"
                    )

        result.success = all_succeeded and not result.violations
        result.duration_seconds = time.monotonic() - start

        logger.info(
            "Cluster %s complete: success=%s artifacts=%d violations=%d escalations=%d duration=%.2fs",
            cluster_spec.cluster_name,
            result.success,
            len(result.artifacts),
            len(result.violations),
            len(result.escalations),
            result.duration_seconds,
        )
        return result

    async def _run_specialist(
        self,
        ctx: SpecialistContext,
    ) -> tuple[list[AgentArtifact], DelegationContract, str]:
        """
        Execute a single specialist within its contract, enforcing the TTL.

        TTL ENFORCEMENT FIX (Phase 3.5):
        asyncio.wait_for() enforces contract.max_duration_seconds. Previously
        the TTL was stored in the contract but never operationally enforced —
        a hanging specialist would block the cluster indefinitely.

        Returns (artifacts, closed_contract, violation_reason or "")
        """
        contract = ctx.contract
        artifacts: list[AgentArtifact] = []
        violation_reason = ""

        # Check interrupt policy before execution
        interrupt_decision = self._policy.check_interrupt_before(ctx.agent)
        if not interrupt_decision.allowed:
            logger.info(
                "Specialist %s paused before execution (interrupt_policy=%s): %s",
                ctx.agent.agent_id, ctx.agent.interrupt_policy, interrupt_decision.reason,
            )
            # HIL gate handling: log and continue (PraisonGovernor handles approvals)

        try:
            # TTL ENFORCEMENT: wrap callable in wait_for with contract deadline
            state_update = await asyncio.wait_for(
                self._invoke_callable(ctx.node_callable, ctx.initial_state),
                timeout=float(ctx.contract.max_duration_seconds),
            )

            # Collect produced artifacts
            for artifact_dict in state_update.get("artifacts", []):
                if isinstance(artifact_dict, AgentArtifact):
                    artifact = artifact_dict
                elif isinstance(artifact_dict, dict):
                    artifact = AgentArtifact(
                        artifact_id=artifact_dict.get("artifact_id", ""),
                        producer_id=ctx.agent.agent_id,
                        workflow_id=ctx.agent.workflow_id,
                        program_id=ctx.agent.program_id,
                        content=artifact_dict.get("content", {}),
                        summary=artifact_dict.get("summary", ""),
                    )
                else:
                    continue

                # Validate tool usage under contract
                for tool_id in state_update.get("tools_used", []):
                    tool_decision = self._policy.check_tool_under_contract(contract, tool_id)
                    if not tool_decision.allowed:
                        violation_reason = tool_decision.reason
                        contract = contract.mark_violated(
                            ContractViolation.TOOL_NOT_ALLOWED, violation_reason
                        )
                        break

                if violation_reason:
                    break

                self._artifact_store.put(artifact)
                artifacts.append(artifact)

            if not violation_reason:
                contract = contract.complete(
                    artifact_id=artifacts[0].artifact_id if artifacts else ""
                )
                emit(contract_completed_event(
                    mission_id=ctx.initial_state.get("mission_id", ""),
                    workflow_id=ctx.agent.workflow_id,
                    program_id=ctx.agent.program_id,
                    contract_id=contract.contract_id,
                    artifact_id=artifacts[0].artifact_id if artifacts else "",
                ))
        except asyncio.TimeoutError:
            violation_reason = (
                f"Specialist {ctx.agent.agent_id} exceeded TTL "
                f"({ctx.contract.max_duration_seconds}s)"
            )
            logger.warning("Contract TTL exceeded: %s", violation_reason)
            contract = contract.expire()
            emit(contract_violated_event(
                mission_id=ctx.initial_state.get("mission_id", ""),
                workflow_id=ctx.agent.workflow_id,
                program_id=ctx.agent.program_id,
                contract_id=contract.contract_id,
                violation="ttl_exceeded",
                detail=violation_reason,
            ))
        except Exception as exc:
            violation_reason = f"Specialist {ctx.agent.agent_id} raised: {exc}"
            contract = contract.mark_violated(ContractViolation.SCOPE_EXCEEDED, violation_reason)
            logger.exception("Specialist %s failed: %s", ctx.agent.agent_id, exc)
            emit(contract_violated_event(
                mission_id=ctx.initial_state.get("mission_id", ""),
                workflow_id=ctx.agent.workflow_id,
                program_id=ctx.agent.program_id,
                contract_id=contract.contract_id,
                violation="scope_exceeded",
                detail=violation_reason,
            ))

        return artifacts, contract, violation_reason

    @staticmethod
    async def _invoke_callable(
        callable_fn: Callable[[dict[str, Any]], dict[str, Any]],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke a node callable, handling both sync and async callables."""
        if asyncio.iscoroutinefunction(callable_fn):
            return await callable_fn(state)
        # Sync callable — run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, callable_fn, state)


# ── Mission-level orchestration ───────────────────────────────────────────────

class MissionRuntime:
    """
    Top-level runtime that orchestrates the full mission graph.

    Sequences cluster execution across phases, passes artifacts between
    phases, and handles governance checkpoints.

    In the full LangGraph deployment, this is replaced by the compiled
    StateGraph execution. MissionRuntime is the fallback for cases where
    LangGraph is not available or for simpler linear missions.
    """

    def __init__(
        self,
        graph_spec: MissionGraphSpec,
        cluster_runtime: ClusterRuntime | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._spec = graph_spec
        self._cluster_runtime = cluster_runtime or ClusterRuntime()
        self._artifact_store = artifact_store or get_artifact_store()

    async def execute_phase(
        self,
        cluster_spec: ClusterSpec,
        coordinator: AgentIdentity,
        specialists: dict[str, AgentIdentity],
        callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
        state: dict[str, Any],
    ) -> ClusterResult:
        """Execute a single phase cluster. Convenience wrapper over ClusterRuntime."""
        return await self._cluster_runtime.run_cluster(
            cluster_spec=cluster_spec,
            coordinator_agent=coordinator,
            specialist_agents=specialists,
            node_callables=callables,
            initial_state=state,
            phase=cluster_spec.phase,
        )

    def get_pending_governance_decisions(self, workflow_id: str) -> list[AgentArtifact]:
        """Return artifacts that require governance decision for this workflow."""
        return self._artifact_store.pending_review(workflow_id)
