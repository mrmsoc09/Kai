"""
K1 PraisonAI Agent Identity Model
===================================
Canonical dataclass for all agent personas in K1. Single source of truth
consumed by every framework adapter and governance layer.

All agents instantiated in CrewAI, AutoGen, DeepAgents, or LangGraph carry
an AgentIdentity object. No framework defines agents independently — they
translate this model into their native format.

LLM routing goes through llm_providers.py. The resolve_litellm_string()
function here bridges agent.llm_pin → LiteLLM model string understood
by CrewAI / AutoGen / PraisonAI's internal LiteLLM calls.

IMMUTABILITY CONTRACT (Phase 3.5 hardening):
  AgentIdentity is frozen. All list fields are coerced to tuples in
  __post_init__. Use with_runtime() to produce runtime-annotated copies.
  Direct attribute mutation raises FrozenInstanceError.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any


# ── LLM routing bridge ────────────────────────────────────────────────────────

def resolve_litellm_string(llm_pin: str | None) -> str:
    """
    Resolve an agent's llm_pin to a LiteLLM model string.
    Routes through K1's provider configuration without bypassing llm_providers.py
    — adapters use the same provider selection logic, just expressed in LiteLLM
    format which CrewAI / AutoGen / PraisonAI understand natively.

    Priority:
      1. llm_pin from agent definition  (e.g., "anthropic")
      2. K1_PRIMARY_LLM_PROVIDER env    (e.g., "anthropic")
      3. Hardcoded default              "anthropic/claude-sonnet-4-6"
    """
    provider = (llm_pin or os.getenv("K1_PRIMARY_LLM_PROVIDER", "anthropic")).strip().lower()

    _model_map: dict[str, str] = {
        "anthropic": f"anthropic/{os.getenv('K1_ANTHROPIC_MODEL', os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-6'))}",
        "openai":    f"openai/{os.getenv('K1_OPENAI_MODEL', os.getenv('OPENAI_MODEL', 'gpt-4.1'))}",
        "gemini":    f"gemini/{os.getenv('K1_GEMINI_MODEL', os.getenv('GEMINI_MODEL', 'gemini-1.5-pro'))}",
        "openrouter": f"openrouter/{os.getenv('KAI_MODEL_ROUTE_BULK', 'deepseek/deepseek-v4-flash')}",
        "deepseek":  f"openrouter/{os.getenv('KAI_MODEL_ROUTE_BULK', 'deepseek/deepseek-v4-flash')}",
        "kimi":      f"openrouter/{os.getenv('KAI_MODEL_ROUTE_PREMIUM', 'moonshotai/kimi-k2.5')}",
        "local":     f"openai/{os.getenv('KAI_LOCAL_BULK_MODEL', os.getenv('K1_OLLAMA_MODEL', 'llama3'))}",
        "ollama":    f"ollama/{os.getenv('K1_OLLAMA_MODEL', os.getenv('OLLAMA_MODEL', 'llama3'))}",
        "gemma":     f"ollama/{os.getenv('K1_GEMMA_MODEL', os.getenv('GEMMA_MODEL', 'gemma:7b'))}",
    }
    return _model_map.get(provider, f"openrouter/{os.getenv('KAI_MODEL_ROUTE_BULK', 'deepseek/deepseek-v4-flash')}")


def resolve_provider_enum(llm_pin: str | None):
    """
    Resolve llm_pin to a LLMProvider enum value from llm_providers.py.
    Used by adapters that need to call llm_factory.complete(preferred_provider=...).
    Returns None if the provider is not registered.
    """
    from apps.backend.src.core.llm_providers import LLMProvider  # avoid circular at module level

    provider = (llm_pin or os.getenv("K1_PRIMARY_LLM_PROVIDER", "anthropic")).strip().lower()
    _enum_map: dict[str, LLMProvider] = {
        "anthropic": LLMProvider.ANTHROPIC,
        "openai":    LLMProvider.OPENAI,
        "gemini":    LLMProvider.GEMINI,
        "deepseek":  LLMProvider.DEEPSEEK,
        "kimi":      LLMProvider.KIMI,
        "ollama":    LLMProvider.OLLAMA,
        "gemma":     LLMProvider.GEMMA,
    }
    return _enum_map.get(provider)


# ── Valid policy values ───────────────────────────────────────────────────────

VALID_RISK_PROFILES   = frozenset({"governance", "analysis", "orchestration", "recon", "reporting", "standard"})
VALID_MEMORY_SCOPES   = frozenset({"session", "phase", "workflow", "mission", "persistent"})
VALID_REVIEW_POLICIES = frozenset({"strict", "moderate", "standard"})

# ── Hybrid orchestration hierarchy fields ────────────────────────────────────
# agent_class: authority tier in the hierarchy
VALID_AGENT_CLASSES = frozenset({"governor", "director", "coordinator", "specialist"})

# delegation_scope: how far down the hierarchy an agent may delegate
VALID_DELEGATION_SCOPES = frozenset({"none", "local", "phase", "global"})

# handoff_policy: protocol required for passing execution to another agent
VALID_HANDOFF_POLICIES = frozenset({
    "explicit_contract_required",
    "coordinator_visible",
    "director_approval_required",
})

# interrupt_policy: when this agent's execution must pause for review
VALID_INTERRUPT_POLICIES = frozenset({
    "none",
    "before_sensitive_tools",
    "before_phase_exit",
    "before_external_calls",
})

# escalation_policy: conditions that trigger upward escalation
VALID_ESCALATION_POLICIES = frozenset({
    "hil_for_band2",
    "governor_review_for_sensitive",
    "escalate_on_low_confidence",
    "escalate_on_scope_expansion",
})

# Agent class delegation authority: what classes an agent class may delegate TO
# governor can delegate to anyone; specialist cannot delegate to anyone
_CLASS_DELEGATION_AUTHORITY: dict[str, frozenset[str]] = {
    "governor":    frozenset({"director", "coordinator", "specialist"}),  # NOT to other governors
    "director":    frozenset({"coordinator", "specialist"}),
    "coordinator": frozenset({"specialist"}),
    "specialist":  frozenset(),  # specialists cannot delegate
}

# Memory scope hierarchy: session < phase < workflow < mission < persistent
_SCOPE_RANK: dict[str, int] = {
    "session":    0,
    "phase":      1,
    "workflow":   2,
    "mission":    3,
    "persistent": 4,
}


# ── Identity dataclass ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentIdentity:
    """
    Canonical agent persona and policy definition. FROZEN — immutable after creation.

    Static fields (from orchestration/praison/agents.yaml):
        agent_id        Unique registry key, e.g. "SecurityGovernorAgent"
        persona         Human-readable role title
        description     One-line summary of what this agent does
        system_prompt   Full system prompt injected when the agent is invoked
        allowed_tools   Immutable tuple of K1 tool IDs this agent may invoke
        risk_profile    Capability tier: governance|analysis|orchestration|recon|reporting|standard
        llm_pin         Preferred provider: anthropic|openai|gemini|ollama|None (platform default)
        memory_scope    Persistence boundary: session|phase|workflow|mission|persistent
        review_policy   Approval strictness: strict|moderate|standard

    Orchestration hierarchy fields (Phase 3):
        agent_class          Authority tier: governor|director|coordinator|specialist
        delegation_scope     How far down an agent may delegate: none|local|phase|global
        allowed_peer_targets Immutable tuple of agent_ids this agent is authorized to delegate TO
        handoff_policy       Protocol for passing execution: explicit_contract_required|coordinator_visible|director_approval_required
        interrupt_policy     When to pause: none|before_sensitive_tools|before_phase_exit|before_external_calls
        escalation_policy    Trigger for upward escalation (one of VALID_ESCALATION_POLICIES)

    Runtime fields (set via with_runtime(), never mutated in place):
        workflow_id     Active campaign workflow ID
        program_id      Bug bounty program ID
        parent_agent    agent_id of the spawning agent
        execution_id    Unique per-execution UUID (auto-generated)
        spawned_at      UTC timestamp of when this instance was created

    Immutability guarantees:
        - FrozenInstanceError raised on any direct attribute assignment
        - list inputs coerced to tuple in __post_init__ (lists have no .append)
        - Use with_runtime() to produce runtime-annotated copies via dataclasses.replace()
    """

    # ── Static identity (from YAML) ───────────────────────────────────────────
    agent_id: str
    persona: str
    description: str
    system_prompt: str
    allowed_tools: tuple[str, ...]    = field(default_factory=tuple)
    risk_profile: str                 = "standard"
    llm_pin: str | None               = None
    memory_scope: str                 = "session"
    review_policy: str                = "standard"

    # ── Orchestration hierarchy fields (Phase 3) ──────────────────────────────
    agent_class: str                  = "specialist"
    delegation_scope: str             = "none"
    allowed_peer_targets: tuple[str, ...] = field(default_factory=tuple)
    handoff_policy: str               = "coordinator_visible"
    interrupt_policy: str             = "none"
    escalation_policy: str            = "hil_for_band2"

    # ── Runtime metadata (set via with_runtime()) ─────────────────────────────
    workflow_id: str    = ""
    program_id: str     = ""
    parent_agent: str   = ""
    execution_id: str   = field(default_factory=lambda: str(uuid.uuid4()))
    spawned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """
        Coerce mutable list inputs to immutable tuples.
        Uses object.__setattr__ because the dataclass is frozen — this is the
        standard Python pattern for frozen dataclass post-construction coercion.
        Called automatically by __init__.
        """
        if isinstance(self.allowed_tools, list):
            object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools))
        if isinstance(self.allowed_peer_targets, list):
            object.__setattr__(self, "allowed_peer_targets", tuple(self.allowed_peer_targets))

    # ── Derived helpers ───────────────────────────────────────────────────────

    @property
    def litellm_model(self) -> str:
        """LiteLLM model string for this agent (CrewAI / AutoGen / PraisonAI use this)."""
        return resolve_litellm_string(self.llm_pin)

    @property
    def memory_scope_rank(self) -> int:
        """Numeric rank of memory scope for hierarchy enforcement."""
        return _SCOPE_RANK.get(self.memory_scope, 0)

    def can_write_to_scope(self, target_scope: str) -> bool:
        """
        Return True if this agent is permitted to write to the target memory scope.

        SECURITY FIX (Phase 3.5): Unknown scope names → DENY.
        Previously unknown scopes defaulted to rank 0 (same as session), which
        permitted writes from session-level agents to any unrecognized scope name.
        Now both the agent's scope and the target scope must be registered in
        _SCOPE_RANK or the check fails closed.
        """
        agent_rank = _SCOPE_RANK.get(self.memory_scope, -1)
        target_rank = _SCOPE_RANK.get(target_scope, -1)
        if agent_rank < 0 or target_rank < 0:
            return False  # unknown scope = deny
        return target_rank <= agent_rank

    @property
    def delegation_authority(self) -> frozenset[str]:
        """Set of agent classes this agent is permitted to delegate to."""
        return _CLASS_DELEGATION_AUTHORITY.get(self.agent_class, frozenset())

    def can_delegate_to(self, target_class: str) -> bool:
        """Return True if this agent class may delegate to target_class."""
        return target_class in self.delegation_authority

    def with_runtime(
        self,
        workflow_id: str = "",
        program_id: str = "",
        parent_agent: str = "",
    ) -> "AgentIdentity":
        """
        Return a new AgentIdentity with runtime fields populated.
        The original (static) identity is not mutated — frozen guarantees this.
        """
        return replace(
            self,
            workflow_id=workflow_id,
            program_id=program_id,
            parent_agent=parent_agent,
            execution_id=str(uuid.uuid4()),
            spawned_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for audit trail, API responses, and adapter consumption."""
        return {
            "agent_id":             self.agent_id,
            "persona":              self.persona,
            "description":          self.description,
            "allowed_tools":        list(self.allowed_tools),
            "risk_profile":         self.risk_profile,
            "llm_pin":              self.llm_pin,
            "memory_scope":         self.memory_scope,
            "review_policy":        self.review_policy,
            "agent_class":          self.agent_class,
            "delegation_scope":     self.delegation_scope,
            "allowed_peer_targets": list(self.allowed_peer_targets),
            "handoff_policy":       self.handoff_policy,
            "interrupt_policy":     self.interrupt_policy,
            "escalation_policy":    self.escalation_policy,
            "workflow_id":          self.workflow_id,
            "program_id":           self.program_id,
            "parent_agent":         self.parent_agent,
            "execution_id":         self.execution_id,
            "spawned_at":           self.spawned_at.isoformat(),
        }
