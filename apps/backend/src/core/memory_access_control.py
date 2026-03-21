"""
Memory Access Control — Selective Memory Sharing
===================================================
Agents MUST NOT see all memory. This module enforces who sees what.

Access model:
  Each agent class has an explicit allowlist of:
    - which MemoryScopes it may read
    - which MemoryTypes it may read
    - which tags it may see (empty = all tags allowed)
    - whether it may write to each scope

Agent classes:
  RECON          — sees endpoint + surface data only (no exploit patterns)
  EXPLOIT        — sees validated vulns + exploit patterns (no raw unvalidated)
  REPORT         — sees final validated findings only (not exploit patterns)
  ANALYST        — sees mid + long-term, all types, read-only
  ORCHESTRATOR   — sees all scopes, all types (coordinator)
  ADMIN          — full access (human operator)

Delegation (contract-based sharing):
  An agent may delegate a subset of its access to another agent.
  Delegation is explicit, logged, and scoped — no implicit escalation.

Usage::

    policy = AccessPolicy.for_agent(AgentClass.EXPLOIT)
    allowed_entries = policy.filter(candidate_entries)

    if policy.can_read(entry):
        data = entry.decrypt()
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .intelligence_memory import MemoryEntry, MemoryScope, MemoryType, ValidationStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent classes
# ---------------------------------------------------------------------------


class AgentClass(str, Enum):
    RECON = "recon"
    EXPLOIT = "exploit"
    REPORT = "report"
    ANALYST = "analyst"
    ORCHESTRATOR = "orchestrator"
    ADMIN = "admin"


# ---------------------------------------------------------------------------
# Access rules per agent class
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessRule:
    """Immutable access rule for an agent class."""

    readable_scopes: frozenset[MemoryScope]
    readable_types: frozenset[MemoryType]
    required_validation: ValidationStatus | None  # None = no requirement
    writable_scopes: frozenset[MemoryScope]
    allowed_tags: frozenset[str]  # empty = all tags allowed
    can_delegate: bool = False

    def can_read(self, entry: MemoryEntry) -> bool:
        if entry.scope not in self.readable_scopes:
            return False
        if entry.memory_type not in self.readable_types:
            return False
        if self.required_validation and entry.validation_status != self.required_validation:
            return False
        if self.allowed_tags:
            if not any(t in self.allowed_tags for t in entry.tags):
                return False
        return True

    def can_write(self, scope: MemoryScope) -> bool:
        return scope in self.writable_scopes


# Predefined rules per agent class
_RULES: dict[AgentClass, AccessRule] = {
    AgentClass.RECON: AccessRule(
        readable_scopes=frozenset({MemoryScope.SHORT_TERM, MemoryScope.MID_TERM}),
        readable_types=frozenset({
            MemoryType.ENDPOINT_BEHAVIOR,
            MemoryType.TECH_STACK,
            MemoryType.PATTERN_SIGNATURE,
        }),
        required_validation=None,
        writable_scopes=frozenset({MemoryScope.SHORT_TERM, MemoryScope.MID_TERM}),
        allowed_tags=frozenset(),  # all tags
        can_delegate=False,
    ),
    AgentClass.EXPLOIT: AccessRule(
        readable_scopes=frozenset({
            MemoryScope.MID_TERM,
            MemoryScope.LONG_TERM,
            MemoryScope.STRATEGIC,
        }),
        readable_types=frozenset({
            MemoryType.FINDING,
            MemoryType.EXPLOIT_PATTERN,
            MemoryType.TOOL_SEQUENCE,
            MemoryType.VULN_CLASS,
            MemoryType.OPPORTUNITY_SIGNAL,
            MemoryType.PATTERN_SIGNATURE,  # exploit agents need to see compressed patterns
        }),
        required_validation=ValidationStatus.CONFIRMED,
        writable_scopes=frozenset({MemoryScope.MID_TERM}),
        allowed_tags=frozenset(),
        can_delegate=False,
    ),
    AgentClass.REPORT: AccessRule(
        readable_scopes=frozenset({MemoryScope.MID_TERM, MemoryScope.LONG_TERM}),
        readable_types=frozenset({MemoryType.FINDING}),
        required_validation=ValidationStatus.CONFIRMED,
        writable_scopes=frozenset(),  # read-only
        allowed_tags=frozenset(),
        can_delegate=False,
    ),
    AgentClass.ANALYST: AccessRule(
        readable_scopes=frozenset({
            MemoryScope.MID_TERM,
            MemoryScope.LONG_TERM,
            MemoryScope.STRATEGIC,
        }),
        readable_types=frozenset(MemoryType),  # all types
        required_validation=None,
        writable_scopes=frozenset(),  # read-only
        allowed_tags=frozenset(),
        can_delegate=False,
    ),
    AgentClass.ORCHESTRATOR: AccessRule(
        readable_scopes=frozenset(MemoryScope),  # all scopes
        readable_types=frozenset(MemoryType),
        required_validation=None,
        writable_scopes=frozenset({
            MemoryScope.SHORT_TERM,
            MemoryScope.MID_TERM,
            MemoryScope.LONG_TERM,
        }),
        allowed_tags=frozenset(),
        can_delegate=True,
    ),
    AgentClass.ADMIN: AccessRule(
        readable_scopes=frozenset(MemoryScope),
        readable_types=frozenset(MemoryType),
        required_validation=None,
        writable_scopes=frozenset(MemoryScope),
        allowed_tags=frozenset(),
        can_delegate=True,
    ),
}


# ---------------------------------------------------------------------------
# Delegation contract
# ---------------------------------------------------------------------------


@dataclass
class DelegationContract:
    """
    A contract allowing one agent to share a SUBSET of its access with another.

    Delegation is:
      - Explicit: must be created by a delegating agent that has can_delegate=True
      - Scoped: delegated access ≤ delegator's access
      - Time-limited: expires at expires_at
      - Logged: every contract creation is audit-logged
    """

    contract_id: str
    delegator_class: AgentClass
    delegate_agent_id: str
    granted_scopes: frozenset[MemoryScope]
    granted_types: frozenset[MemoryType]
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600.0)  # 1h default
    reason: str = ""

    def is_valid(self) -> bool:
        return time.time() < self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "delegator_class": self.delegator_class.value,
            "delegate_agent_id": self.delegate_agent_id,
            "granted_scopes": [s.value for s in self.granted_scopes],
            "granted_types": [t.value for t in self.granted_types],
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "reason": self.reason,
        }


def create_delegation(
    delegator_class: AgentClass,
    delegate_agent_id: str,
    granted_scopes: set[MemoryScope],
    granted_types: set[MemoryType],
    expires_in_seconds: float = 3600.0,
    reason: str = "",
) -> DelegationContract:
    """
    Create a delegation contract. Validates that delegator has can_delegate=True
    and that granted access is a subset of delegator's own access.
    """
    rule = _RULES[delegator_class]
    if not rule.can_delegate:
        raise PermissionError(
            f"AgentClass.{delegator_class.value} does not have delegation privilege"
        )

    # Constrain to delegator's own access
    scopes = frozenset(granted_scopes) & rule.readable_scopes
    types = frozenset(granted_types) & rule.readable_types

    contract = DelegationContract(
        contract_id=str(uuid.uuid4()),
        delegator_class=delegator_class,
        delegate_agent_id=delegate_agent_id,
        granted_scopes=scopes,
        granted_types=types,
        expires_at=time.time() + expires_in_seconds,
        reason=reason,
    )
    logger.info(
        "memory_access_control.delegation_created contract=%s delegate=%s scopes=%s",
        contract.contract_id,
        delegate_agent_id,
        [s.value for s in scopes],
    )
    return contract


# ---------------------------------------------------------------------------
# Access policy (per-agent evaluation surface)
# ---------------------------------------------------------------------------


class AccessPolicy:
    """
    Evaluates read/write access for a specific agent instance.
    Combines base AgentClass rules with any active delegation contracts.
    """

    def __init__(
        self,
        agent_class: AgentClass,
        tenant_id: str | None = None,
        contracts: list[DelegationContract] | None = None,
    ) -> None:
        self._class = agent_class
        self._rule = _RULES[agent_class]
        self._tenant_id = tenant_id
        self._contracts = [c for c in (contracts or []) if c.is_valid()]

    @classmethod
    def for_agent(cls, agent_class: AgentClass, tenant_id: str | None = None) -> "AccessPolicy":
        return cls(agent_class, tenant_id)

    def can_read(self, entry: MemoryEntry) -> bool:
        """Check if this agent may read the given memory entry."""
        # Tenant isolation: agent can only read entries from same tenant (or no-tenant)
        if self._tenant_id and entry.tenant_id and entry.tenant_id != self._tenant_id:
            return False

        # Base rule check
        if self._rule.can_read(entry):
            return True

        # Check delegation contracts
        for contract in self._contracts:
            if entry.scope in contract.granted_scopes and entry.memory_type in contract.granted_types:
                return True

        return False

    def can_write(self, scope: MemoryScope) -> bool:
        return self._rule.can_write(scope)

    def filter(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """Filter a list of entries to only those this agent may read."""
        allowed = [e for e in entries if self.can_read(e)]
        denied = len(entries) - len(allowed)
        if denied > 0:
            logger.debug(
                "memory_access_control.filter agent=%s denied=%d allowed=%d",
                self._class.value, denied, len(allowed),
            )
        return allowed

    def describe(self) -> dict[str, Any]:
        return {
            "agent_class": self._class.value,
            "tenant_id": self._tenant_id,
            "readable_scopes": [s.value for s in self._rule.readable_scopes],
            "readable_types": [t.value for t in self._rule.readable_types],
            "required_validation": self._rule.required_validation.value
            if self._rule.required_validation else None,
            "writable_scopes": [s.value for s in self._rule.writable_scopes],
            "can_delegate": self._rule.can_delegate,
            "active_contracts": len(self._contracts),
        }
