"""
Praison Delegation Contracts
============================
Structured contracts required for all agent-to-agent delegation in K1's
hybrid hierarchical + decentralized orchestration model.

Every handoff between agents must carry a DelegationContract. This is not
optional scaffolding — it is the enforcement mechanism that keeps the
hierarchy coherent and auditable.

IMMUTABILITY CONTRACT (Phase 3.5 hardening):
  DelegationContract is frozen. State transitions produce NEW instances
  via dataclasses.replace(). Direct mutation raises FrozenInstanceError.
  list fields (allowed_tools, allowed_targets) are coerced to tuples in
  __post_init__.

EMPTY-LIST SEMANTICS FIX (Phase 3.5):
  allowed_tools=() means NO tools permitted (not permit-all).
  allowed_targets=() means NO targets permitted (not permit-all).
  The factory (create_delegation_contract) always explicitly sets these
  from the delegate's declared tool list. Callers cannot accidentally
  produce a permit-all contract by omitting the field.

BIDIRECTIONAL TRUST FIX (Phase 3.5):
  _validate_delegation_authority enforces the delegator's allowed_peer_targets
  list. If the delegator has a non-empty allowed_peer_targets and the delegate
  is not in that list, the contract is rejected at creation time.

Contract lifecycle:
  1. create_delegation_contract() — validates authority, creates PENDING contract
  2. validate_contract()          — validates structural invariants
  3. contract.activate()          — delegate accepts → ACTIVE
  4. contract.complete()          — delegate finishes → COMPLETED
  5. contract.revoke()            — delegator cancels → REVOKED
  6. contract.mark_violated()     — violation detected → VIOLATED (non-terminal only)
  7. contract.expire()            — TTL elapsed → EXPIRED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from apps.backend.src.core.praison_agent import (
    AgentIdentity,
    VALID_DELEGATION_SCOPES,
    _CLASS_DELEGATION_AUTHORITY,
)


# ── Contract states ───────────────────────────────────────────────────────────

class ContractState(str, Enum):
    PENDING   = "pending"    # Created, not yet accepted by delegate
    ACTIVE    = "active"     # Delegate has accepted and is executing
    COMPLETED = "completed"  # Delegate finished successfully
    REVOKED   = "revoked"    # Delegator cancelled before completion
    VIOLATED  = "violated"   # Delegate exceeded contract scope
    EXPIRED   = "expired"    # TTL elapsed before completion


_TERMINAL_STATES = frozenset({
    ContractState.COMPLETED,
    ContractState.REVOKED,
    ContractState.VIOLATED,
    ContractState.EXPIRED,
})


# ── Violation types ───────────────────────────────────────────────────────────

class ContractViolation(str, Enum):
    SCOPE_EXCEEDED             = "scope_exceeded"
    TOOL_NOT_ALLOWED           = "tool_not_allowed"
    HANDOFF_UNAUTHORIZED       = "handoff_unauthorized"
    MEMORY_SCOPE_BREACH        = "memory_scope_breach"
    EXTERNAL_CALL_UNAUTHORIZED = "external_call_unauthorized"


# ── DelegationContract ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DelegationContract:
    """
    Structured contract for all agent-to-agent delegation. FROZEN.

    State transitions return NEW instances via replace() — the original
    is never mutated. FrozenInstanceError raised on direct assignment.

    Tool/target enforcement semantics:
      allowed_tools=()  → NO tools permitted
      allowed_targets=() → NO targets permitted
      Non-empty tuples  → exact whitelist
    """

    # Identity
    contract_id: str      = field(default_factory=lambda: str(uuid.uuid4()))
    delegator_id: str     = ""
    delegate_id: str      = ""
    delegator_class: str  = ""
    delegate_class: str   = ""

    # Authorization context
    workflow_id: str      = ""
    program_id: str       = ""
    phase: str            = ""

    # Scope constraints — tuples, always explicitly set by factory
    delegation_scope: str          = "local"
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    allowed_targets: tuple[str, ...] = field(default_factory=tuple)
    can_sub_delegate: bool          = False

    # Execution constraints
    objective: str              = ""
    expected_artifact_type: str = ""
    max_duration_seconds: int   = 3600

    # Lifecycle
    state: ContractState             = ContractState.PENDING
    created_at: datetime             = field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: datetime | None    = None
    closed_at: datetime | None       = None
    result_artifact_id: str          = ""
    violation: ContractViolation | None = None
    violation_detail: str            = ""

    def __post_init__(self) -> None:
        """Coerce list inputs to tuples for true immutability."""
        if isinstance(self.allowed_tools, list):
            object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools))
        if isinstance(self.allowed_targets, list):
            object.__setattr__(self, "allowed_targets", tuple(self.allowed_targets))

    # ── State transitions ─────────────────────────────────────────────────────

    def activate(self) -> "DelegationContract":
        """Delegate accepts the contract. Returns new ACTIVE instance."""
        if self.state != ContractState.PENDING:
            raise ContractStateError(f"Cannot activate contract in state {self.state.value}")
        return replace(self, state=ContractState.ACTIVE, activated_at=datetime.now(timezone.utc))

    def complete(self, artifact_id: str = "") -> "DelegationContract":
        """Delegate signals successful completion. Returns new COMPLETED instance."""
        if self.state != ContractState.ACTIVE:
            raise ContractStateError(f"Cannot complete contract in state {self.state.value}")
        return replace(
            self,
            state=ContractState.COMPLETED,
            closed_at=datetime.now(timezone.utc),
            result_artifact_id=artifact_id,
        )

    def revoke(self) -> "DelegationContract":
        """Delegator cancels contract. Returns new REVOKED instance."""
        if self.state not in (ContractState.PENDING, ContractState.ACTIVE):
            raise ContractStateError(f"Cannot revoke contract in state {self.state.value}")
        return replace(self, state=ContractState.REVOKED, closed_at=datetime.now(timezone.utc))

    def mark_violated(self, violation: ContractViolation, detail: str = "") -> "DelegationContract":
        """
        Record a contract violation. Returns new VIOLATED instance.

        GUARD FIX (Phase 3.5): Cannot mark a terminal contract violated.
        Previously allowed overwriting COMPLETED/EXPIRED states.
        """
        if self.is_terminal:
            raise ContractStateError(
                f"Cannot mark violated: contract {self.contract_id} is already "
                f"in terminal state {self.state.value}"
            )
        return replace(
            self,
            state=ContractState.VIOLATED,
            closed_at=datetime.now(timezone.utc),
            violation=violation,
            violation_detail=detail,
        )

    def expire(self) -> "DelegationContract":
        """TTL elapsed before completion. Returns new EXPIRED instance."""
        if self.is_terminal:
            raise ContractStateError(
                f"Cannot expire contract already in terminal state {self.state.value}"
            )
        return replace(self, state=ContractState.EXPIRED, closed_at=datetime.now(timezone.utc))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.state in _TERMINAL_STATES

    @property
    def elapsed_seconds(self) -> float:
        end = self.closed_at or datetime.now(timezone.utc)
        return (end - self.created_at).total_seconds()

    @property
    def is_expired(self) -> bool:
        if self.state in (ContractState.COMPLETED, ContractState.REVOKED):
            return False
        return self.elapsed_seconds > self.max_duration_seconds

    def tool_allowed(self, tool_id: str) -> bool:
        """
        Return True if tool_id is permitted under this contract.

        SEMANTICS FIX (Phase 3.5): empty tuple = NO tools permitted.
        Previously empty list meant permit-all, creating an accidental
        privilege escalation vector. The factory always sets allowed_tools
        from the delegate's declared tool list, so empty tuples are only
        produced by intentional calls with allowed_tools=[].
        """
        return tool_id in self.allowed_tools

    def target_allowed(self, target: str) -> bool:
        """
        Return True if target is permitted under this contract.

        SEMANTICS FIX (Phase 3.5): empty tuple = NO targets permitted.
        """
        return target in self.allowed_targets

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id":            self.contract_id,
            "delegator_id":           self.delegator_id,
            "delegate_id":            self.delegate_id,
            "delegator_class":        self.delegator_class,
            "delegate_class":         self.delegate_class,
            "workflow_id":            self.workflow_id,
            "program_id":             self.program_id,
            "phase":                  self.phase,
            "delegation_scope":       self.delegation_scope,
            "allowed_tools":          list(self.allowed_tools),
            "allowed_targets":        list(self.allowed_targets),
            "can_sub_delegate":       self.can_sub_delegate,
            "objective":              self.objective,
            "expected_artifact_type": self.expected_artifact_type,
            "max_duration_seconds":   self.max_duration_seconds,
            "state":                  self.state.value,
            "created_at":             self.created_at.isoformat(),
            "activated_at":           self.activated_at.isoformat() if self.activated_at else None,
            "closed_at":              self.closed_at.isoformat() if self.closed_at else None,
            "result_artifact_id":     self.result_artifact_id,
            "violation":              self.violation.value if self.violation else None,
            "violation_detail":       self.violation_detail,
        }


# ── Contract exceptions ───────────────────────────────────────────────────────

class ContractStateError(RuntimeError):
    """Raised when a state transition is invalid."""


class ContractValidationError(ValueError):
    """Raised when a proposed contract fails validation."""
    def __init__(self, reason: str, contract_id: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.contract_id = contract_id


# ── Contract factory ──────────────────────────────────────────────────────────

def create_delegation_contract(
    delegator: AgentIdentity,
    delegate: AgentIdentity,
    *,
    objective: str,
    phase: str = "",
    allowed_tools: list[str] | None = None,
    allowed_targets: list[str] | None = None,
    expected_artifact_type: str = "",
    max_duration_seconds: int = 3600,
    can_sub_delegate: bool = False,
) -> DelegationContract:
    """
    Create a delegation contract from delegator to delegate.

    allowed_tools semantics:
      None         → use delegate's full declared tool list (no additional restriction)
      []           → NO tools permitted (explicit deny-all)
      ["nmap", …]  → whitelist; must be subset of delegate.allowed_tools

    allowed_targets semantics:
      None         → use delegate's allowed_peer_targets list
      []           → NO targets permitted (explicit deny-all)
      ["host.com"] → explicit whitelist

    Raises ContractValidationError on:
      - Class authority violation (specialist can't delegate)
      - delegation_scope=none
      - Delegator's allowed_peer_targets doesn't include delegate (bidirectional trust)
      - allowed_tools not subset of delegate's declared tools
    """
    _validate_delegation_authority(delegator, delegate)

    # Tool list: None = use delegate's full list; explicit list is validated as subset
    if allowed_tools is None:
        tools: tuple[str, ...] = tuple(delegate.allowed_tools)
    else:
        if allowed_tools:  # non-empty explicit list — validate subset
            unauthorized = set(allowed_tools) - set(delegate.allowed_tools)
            if unauthorized:
                raise ContractValidationError(
                    f"Contract grants tools not in delegate's allowed_tools: {sorted(unauthorized)}",
                )
        tools = tuple(allowed_tools)

    # Target list: None = use delegate's peer targets (may be empty for specialists)
    targets: tuple[str, ...] = tuple(allowed_targets) if allowed_targets is not None else tuple(delegate.allowed_peer_targets)

    return DelegationContract(
        delegator_id=delegator.agent_id,
        delegate_id=delegate.agent_id,
        delegator_class=delegator.agent_class,
        delegate_class=delegate.agent_class,
        workflow_id=delegator.workflow_id,
        program_id=delegator.program_id,
        phase=phase,
        delegation_scope=delegator.delegation_scope,
        allowed_tools=tools,
        allowed_targets=targets,
        can_sub_delegate=can_sub_delegate,
        objective=objective,
        expected_artifact_type=expected_artifact_type,
        max_duration_seconds=max_duration_seconds,
    )


def validate_contract(contract: DelegationContract) -> None:
    """
    Validate a contract's structural invariants before activating it.
    Raises ContractValidationError if any constraint is violated.
    """
    if not contract.delegator_id:
        raise ContractValidationError("delegator_id is required", contract.contract_id)
    if not contract.delegate_id:
        raise ContractValidationError("delegate_id is required", contract.contract_id)
    if not contract.workflow_id:
        raise ContractValidationError("workflow_id is required", contract.contract_id)
    if not contract.objective:
        raise ContractValidationError("objective is required", contract.contract_id)
    if contract.delegation_scope not in VALID_DELEGATION_SCOPES:
        raise ContractValidationError(
            f"invalid delegation_scope: {contract.delegation_scope}", contract.contract_id
        )
    if contract.delegator_class not in _CLASS_DELEGATION_AUTHORITY:
        raise ContractValidationError(
            f"unknown delegator_class: {contract.delegator_class}", contract.contract_id
        )
    authority = _CLASS_DELEGATION_AUTHORITY[contract.delegator_class]
    if contract.delegate_class not in authority:
        raise ContractValidationError(
            f"{contract.delegator_class} cannot delegate to {contract.delegate_class}",
            contract.contract_id,
        )
    if contract.max_duration_seconds <= 0:
        raise ContractValidationError(
            f"max_duration_seconds must be > 0, got {contract.max_duration_seconds}",
            contract.contract_id,
        )


def _validate_delegation_authority(delegator: AgentIdentity, delegate: AgentIdentity) -> None:
    """
    Validate delegation authority at contract creation time.

    Checks (in order):
      1. Class authority: delegator.agent_class can delegate to delegate.agent_class
      2. Scope: delegator.delegation_scope != "none"
      3. Outbound target list (BIDIRECTIONAL TRUST FIX Phase 3.5):
         If delegator.allowed_peer_targets is non-empty, delegate.agent_id must be in it.
         This enforces: a coordinator with allowed_peer_targets=[A, B] cannot delegate to C
         even if C is a valid class target.

    Raises ContractValidationError on any violation.
    """
    if not delegator.can_delegate_to(delegate.agent_class):
        raise ContractValidationError(
            f"Agent class '{delegator.agent_class}' ({delegator.agent_id}) cannot delegate "
            f"to class '{delegate.agent_class}' ({delegate.agent_id})"
        )
    if delegator.delegation_scope == "none":
        raise ContractValidationError(
            f"Agent {delegator.agent_id} has delegation_scope=none and cannot delegate"
        )
    # BIDIRECTIONAL TRUST: enforce delegator's outbound target list
    if delegator.allowed_peer_targets and delegate.agent_id not in delegator.allowed_peer_targets:
        raise ContractValidationError(
            f"Agent '{delegator.agent_id}' may not delegate to '{delegate.agent_id}'. "
            f"Authorized delegation targets: {list(delegator.allowed_peer_targets)}"
        )
