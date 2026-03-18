"""
Praison Runtime Policy Enforcement
====================================
Centralized policy engine for K1's hybrid orchestration system.

Enforces:
  - Delegation authority (can agent A delegate to agent B?)
  - Interrupt policy (must execution pause before/after this agent?)
  - Escalation policy (when does an event require escalation?)
  - Memory scope compliance (is this write permitted?)
  - Tool access within contracts (is this tool allowed here?)

This module is the single runtime arbiter — it does NOT consult LLMs.
All decisions are deterministic, synchronous, and fast.

PraisonGovernor calls this for structural policy decisions.
LLM review is only invoked when PraisonGovernor needs qualitative assessment
of Band 2 actions — never for structural authority checks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from apps.backend.src.core.praison_agent import (
    AgentIdentity,
    VALID_AGENT_CLASSES,
    VALID_DELEGATION_SCOPES,
    VALID_ESCALATION_POLICIES,
    VALID_HANDOFF_POLICIES,
    VALID_INTERRUPT_POLICIES,
    _CLASS_DELEGATION_AUTHORITY,
    _SCOPE_RANK,
)
from apps.backend.src.core.praison_contracts import (
    ContractViolation,
    DelegationContract,
    ContractState,
)

logger = logging.getLogger(__name__)


# ── Policy decision types ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    requires_escalation: bool = False
    escalation_reason: str    = ""

    @classmethod
    def permit(cls, reason: str = "ok") -> "PolicyDecision":
        return cls(allowed=True, reason=reason)

    @classmethod
    def deny(cls, reason: str) -> "PolicyDecision":
        return cls(allowed=False, reason=reason)

    @classmethod
    def permit_with_escalation(cls, reason: str, escalation_reason: str) -> "PolicyDecision":
        return cls(allowed=True, reason=reason, requires_escalation=True, escalation_reason=escalation_reason)


# ── PraisonRuntimePolicy ──────────────────────────────────────────────────────

class PraisonRuntimePolicy:
    """
    Deterministic runtime policy engine for hybrid orchestration.

    All methods are synchronous and raise no exceptions — they return
    PolicyDecision objects. Callers decide how to handle denials.
    """

    # ── Delegation policy ─────────────────────────────────────────────────────

    def check_delegation(
        self,
        delegator: AgentIdentity,
        delegate: AgentIdentity,
    ) -> PolicyDecision:
        """Can delegator delegate execution to delegate?"""
        if delegator.delegation_scope == "none":
            return PolicyDecision.deny(
                f"{delegator.agent_id} has delegation_scope=none"
            )
        authority = _CLASS_DELEGATION_AUTHORITY.get(delegator.agent_class, frozenset())
        if delegate.agent_class not in authority:
            return PolicyDecision.deny(
                f"Class '{delegator.agent_class}' cannot delegate to class '{delegate.agent_class}'"
            )
        # Scope check: local scope can only delegate within same phase
        # (phase is checked at contract creation time — here we just check class)
        logger.debug(
            "Delegation permitted: %s (%s) → %s (%s)",
            delegator.agent_id, delegator.agent_class,
            delegate.agent_id, delegate.agent_class,
        )
        return PolicyDecision.permit(
            f"{delegator.agent_class} → {delegate.agent_class} delegation authorized"
        )

    # ── Interrupt policy ──────────────────────────────────────────────────────

    def check_interrupt_before(self, agent: AgentIdentity) -> PolicyDecision:
        """Should execution pause BEFORE this agent runs?"""
        policy = agent.interrupt_policy
        if policy == "none":
            return PolicyDecision.permit("no interrupt required")
        if agent.review_policy == "strict":
            return PolicyDecision.deny(
                f"strict review_policy requires interrupt before {agent.agent_id}"
            )
        if policy in ("before_sensitive_tools", "before_phase_exit", "before_external_calls"):
            # These are event-triggered, not unconditional — return permit here,
            # specific event checks use check_interrupt_for_event()
            return PolicyDecision.permit(f"interrupt_policy={policy} is event-triggered")
        return PolicyDecision.permit("unknown interrupt_policy — defaulting to permit")

    def check_interrupt_for_event(
        self,
        agent: AgentIdentity,
        event_type: str,
        event_context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """
        Should execution pause for a specific event?
        event_type: "sensitive_tool" | "phase_exit" | "external_call"
        """
        policy = agent.interrupt_policy
        if policy == "none":
            return PolicyDecision.permit("no interrupt policy")
        if policy == "before_sensitive_tools" and event_type == "sensitive_tool":
            return PolicyDecision.deny(
                f"Agent {agent.agent_id} must pause before sensitive tool execution"
            )
        if policy == "before_phase_exit" and event_type == "phase_exit":
            return PolicyDecision.deny(
                f"Agent {agent.agent_id} must pause before phase exit"
            )
        if policy == "before_external_calls" and event_type == "external_call":
            return PolicyDecision.deny(
                f"Agent {agent.agent_id} must pause before external call"
            )
        return PolicyDecision.permit(f"event {event_type!r} does not trigger {policy}")

    # ── Escalation policy ─────────────────────────────────────────────────────

    def check_escalation(
        self,
        agent: AgentIdentity,
        event_type: str,
        event_context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """
        Should this event trigger escalation?
        event_type: "band2_tool" | "sensitive_action" | "low_confidence" | "scope_expansion"
        """
        ctx = event_context or {}
        policy = agent.escalation_policy

        if policy == "hil_for_band2" and event_type == "band2_tool":
            return PolicyDecision.permit_with_escalation(
                "execution permitted, HIL escalation required",
                escalation_reason="Band 2 tool requires HIL review",
            )
        if policy == "governor_review_for_sensitive" and event_type == "sensitive_action":
            return PolicyDecision.permit_with_escalation(
                "execution permitted, governance review required",
                escalation_reason="Sensitive action requires governor review",
            )
        if policy == "escalate_on_low_confidence":
            confidence = ctx.get("confidence", "high")
            if confidence in ("low", "inferred"):
                return PolicyDecision.permit_with_escalation(
                    "execution permitted, escalation on low confidence",
                    escalation_reason=f"Low confidence ({confidence}) requires review",
                )
        if policy == "escalate_on_scope_expansion" and event_type == "scope_expansion":
            return PolicyDecision.permit_with_escalation(
                "scope expansion detected",
                escalation_reason="Scope expansion requires governor approval",
            )
        return PolicyDecision.permit("no escalation triggered")

    # ── Memory scope policy ───────────────────────────────────────────────────

    def check_memory_write(
        self,
        agent: AgentIdentity,
        target_scope: str,
        data_bytes: int = 0,
        max_bytes: int = 1_048_576,
    ) -> PolicyDecision:
        """
        Can agent write to target_scope?

        DENY-UNKNOWN FIX (Phase 3.5): Unknown scope names → deny.
        Previously defaulted to rank 0, permitting writes from session agents
        to any unrecognized scope name.
        """
        if data_bytes > max_bytes:
            return PolicyDecision.deny(
                f"Memory write exceeds limit: {data_bytes} > {max_bytes} bytes"
            )
        # Use AgentIdentity.can_write_to_scope() which has the deny-unknown fix
        if not agent.can_write_to_scope(target_scope):
            return PolicyDecision.deny(
                f"Agent scope '{agent.memory_scope}' cannot write to '{target_scope}'"
            )
        if target_scope == "persistent" and (not agent.workflow_id or not agent.program_id):
            return PolicyDecision.deny(
                "Persistent scope writes require workflow_id and program_id context"
            )
        return PolicyDecision.permit(f"memory write to {target_scope!r} authorized")

    # ── Contract tool enforcement ─────────────────────────────────────────────

    def check_tool_under_contract(
        self,
        contract: DelegationContract,
        tool_id: str,
    ) -> PolicyDecision:
        """Is tool_id permitted under the active contract?"""
        if contract.state != ContractState.ACTIVE:
            return PolicyDecision.deny(
                f"Contract {contract.contract_id} is not active (state={contract.state})"
            )
        if contract.is_expired:
            return PolicyDecision.deny(
                f"Contract {contract.contract_id} has expired"
            )
        if not contract.tool_allowed(tool_id):
            return PolicyDecision.deny(
                f"Tool {tool_id!r} not in contract allowed_tools"
            )
        return PolicyDecision.permit(f"tool {tool_id!r} authorized under contract")

    # ── Target enforcement ────────────────────────────────────────────────────

    def check_target_under_contract(
        self,
        contract: DelegationContract,
        target: str,
    ) -> PolicyDecision:
        """Is target permitted under the active contract?"""
        if not contract.target_allowed(target):
            return PolicyDecision.deny(
                f"Target {target!r} not in contract allowed_targets"
            )
        return PolicyDecision.permit(f"target {target!r} authorized under contract")

    # ── Adaptive execution policy (Phase 4) ──────────────────────────────────

    def validate_adaptive_change(
        self,
        agent: AgentIdentity,
        change_type: str,
        new_value: Any,
        strategy: Any = None,
    ) -> PolicyDecision:
        """
        Validate whether an agent is permitted to make an adaptive execution change.

        Imports praison_adaptive here to avoid circular imports at module level.
        Delegates to praison_adaptive.validate_plan_patch() for patch-level validation.
        This method adds agent-level policy checks on top.
        """
        from apps.backend.src.core.praison_adaptive import (
            ExecutionPlanPatch,
            ExecutionStrategy,
            validate_plan_patch,
            _FORBIDDEN_CHANGE_TYPES,
            _ALLOWED_CHANGE_TYPES,
        )

        # Specialists can only make low-impact adaptive changes
        if agent.agent_class == "specialist" and change_type not in (
            "select_tool_candidate", "select_prompt_profile", "select_parameter_profile",
            "adjust_retry", "reprioritize_work",
        ):
            return PolicyDecision.deny(
                f"Specialist '{agent.agent_id}' cannot make '{change_type}' adaptive changes. "
                "Only tool/prompt/param selection and retry adjustments permitted."
            )

        # Forbidden changes: always deny
        if change_type in _FORBIDDEN_CHANGE_TYPES:
            return PolicyDecision.deny(
                f"Change type '{change_type}' is forbidden in adaptive execution."
            )

        # Unknown change type: deny by default
        if change_type not in _ALLOWED_CHANGE_TYPES:
            return PolicyDecision.deny(
                f"Unknown adaptive change type '{change_type}'."
            )

        # If a strategy is provided, validate the patch against it
        if strategy and isinstance(strategy, ExecutionStrategy):
            patch = ExecutionPlanPatch(
                mission_id="",
                proposed_by_agent=agent.agent_id,
                change_type=change_type,
                new_value=new_value,
            )
            result = validate_plan_patch(patch, strategy)
            if not result.valid:
                if result.requires_escalation:
                    return PolicyDecision.permit_with_escalation(
                        "Adaptive change requires governance review",
                        escalation_reason=result.reason,
                    )
                return PolicyDecision.deny(result.reason)

        return PolicyDecision.permit(
            f"Adaptive change '{change_type}' by {agent.agent_id} permitted"
        )

    # ── Agent identity validation ─────────────────────────────────────────────

    def validate_identity(self, agent: AgentIdentity) -> list[str]:
        """
        Validate all policy fields on an AgentIdentity.
        Returns list of validation errors (empty = valid).
        """
        errors: list[str] = []
        if agent.agent_class not in VALID_AGENT_CLASSES:
            errors.append(f"invalid agent_class: {agent.agent_class!r}")
        if agent.delegation_scope not in VALID_DELEGATION_SCOPES:
            errors.append(f"invalid delegation_scope: {agent.delegation_scope!r}")
        if agent.handoff_policy not in VALID_HANDOFF_POLICIES:
            errors.append(f"invalid handoff_policy: {agent.handoff_policy!r}")
        if agent.interrupt_policy not in VALID_INTERRUPT_POLICIES:
            errors.append(f"invalid interrupt_policy: {agent.interrupt_policy!r}")
        if agent.escalation_policy not in VALID_ESCALATION_POLICIES:
            errors.append(f"invalid escalation_policy: {agent.escalation_policy!r}")
        # Class/delegation scope consistency
        if agent.agent_class == "specialist" and agent.delegation_scope != "none":
            errors.append("specialists must have delegation_scope=none")
        if agent.agent_class == "governor" and agent.delegation_scope == "none":
            errors.append("governors must have delegation_scope != none")
        return errors


# ── Module singleton ──────────────────────────────────────────────────────────

_POLICY = PraisonRuntimePolicy()


def get_runtime_policy() -> PraisonRuntimePolicy:
    return _POLICY
