"""
K1 PraisonAI Agent Registry
==============================
Single source of truth for loading, validating, and instantiating all K1
agent personas. Reads from orchestration/praison/agents.yaml `agents:` section.

All framework adapters (CrewAI, AutoGen, DeepAgents, LangGraph) instantiate
agents through this registry — they never define agents independently.

LLM routing is always delegated to llm_providers.py via resolve_litellm_string()
and resolve_provider_enum() from praison_agent.py. No adapter calls a model
directly; they request a provider from the platform router.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from apps.backend.src.core.praison_agent import (
    AgentIdentity,
    VALID_AGENT_CLASSES,
    VALID_DELEGATION_SCOPES,
    VALID_ESCALATION_POLICIES,
    VALID_HANDOFF_POLICIES,
    VALID_INTERRUPT_POLICIES,
    VALID_MEMORY_SCOPES,
    VALID_REVIEW_POLICIES,
    VALID_RISK_PROFILES,
)

logger = logging.getLogger(__name__)

# Required fields every agent config must supply
_REQUIRED_FIELDS = frozenset({"persona", "description", "system_prompt"})


def _resolve_config_path(path: str | None) -> Path:
    if path:
        return Path(path)
    env_path = os.getenv("K1_PRAISON_CONFIG")
    if env_path:
        return Path(env_path)
    return (
        Path(__file__).resolve().parents[4]
        / "orchestration" / "praison" / "agents.yaml"
    )


# ── Registry ──────────────────────────────────────────────────────────────────

class PraisonAgentRegistry:
    """
    Loads and manages all K1 agent personas from agents.yaml.

    Usage:
        registry = PraisonAgentRegistry()
        registry.load_agents()

        identity = registry.get_agent("SecurityGovernorAgent")
        crewai_agent = registry.instantiate_agent("SecurityGovernorAgent", "crewai",
                                                   workflow_id="wf1", program_id="prog1")
    """

    def __init__(self, config_path: str | None = None):
        self._config_path = _resolve_config_path(config_path)
        self._agents: dict[str, AgentIdentity] = {}
        self._lifecycle_policy: dict[str, Any] = {}
        self._loaded = False
        self._lock = Lock()

    # ── Loading ───────────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """
        Ensure agents are loaded. Thread-safe. No-op if already loaded.

        TOCTOU FIX (Phase 3.5): The previous pattern checked self._loaded
        outside the lock, then acquired the lock inside load_agents(). This
        allowed two threads to both observe _loaded=False and both proceed
        to call _load_locked. While _load_locked was idempotent, the check
        itself was outside any lock. Now the check is always inside the lock.
        """
        with self._lock:
            if not self._loaded:
                self._load_locked()

    def load_agents(self) -> None:
        """
        Load and validate all agent definitions from agents.yaml.
        Thread-safe; idempotent (subsequent calls are no-ops).
        """
        self._ensure_loaded()

    def _load_locked(self) -> None:
        """Internal loader — must be called under self._lock."""
        try:
            with self._config_path.open(encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except FileNotFoundError:
            raise RuntimeError(
                f"PraisonAI agents.yaml not found at {self._config_path}. "
                "Ensure orchestration/praison/agents.yaml exists."
            )
        except yaml.YAMLError as exc:
            raise RuntimeError(f"agents.yaml parse error: {exc}") from exc

        agents_section = raw.get("agents", {})
        if not agents_section:
            raise RuntimeError(
                "agents.yaml has no 'agents:' section. "
                "Add canonical agent definitions under the 'agents:' key."
            )

        loaded: dict[str, AgentIdentity] = {}
        errors: list[str] = []

        for agent_id, config in agents_section.items():
            if not isinstance(config, dict):
                errors.append(f"{agent_id}: config must be a dict, got {type(config).__name__}")
                continue
            try:
                self.validate_agent_policy(config, agent_id=agent_id)
                identity = AgentIdentity(
                    agent_id=agent_id,
                    persona=config["persona"],
                    description=str(config.get("description", "")),
                    system_prompt=str(config.get("system_prompt", config.get("backstory", ""))),
                    allowed_tools=list(config.get("allowed_tools", [])),
                    risk_profile=str(config.get("risk_profile", "standard")),
                    llm_pin=config.get("llm_pin") or None,
                    memory_scope=str(config.get("memory_scope", "session")),
                    review_policy=str(config.get("review_policy", "standard")),
                    agent_class=str(config.get("agent_class", "specialist")),
                    delegation_scope=str(config.get("delegation_scope", "none")),
                    allowed_peer_targets=list(config.get("allowed_peer_targets", [])),
                    handoff_policy=str(config.get("handoff_policy", "coordinator_visible")),
                    interrupt_policy=str(config.get("interrupt_policy", "none")),
                    escalation_policy=str(config.get("escalation_policy", "hil_for_band2")),
                )
                loaded[agent_id] = identity
                logger.debug("Loaded agent: %s (profile=%s llm=%s)", agent_id, identity.risk_profile, identity.llm_pin)
            except (ValueError, KeyError) as exc:
                errors.append(f"{agent_id}: {exc}")

        if errors:
            raise RuntimeError(
                f"agents.yaml validation failed for {len(errors)} agent(s):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        self._agents = loaded
        self._lifecycle_policy = raw.get("agent_lifecycle_policy", {})
        self._loaded = True

        logger.info(
            "PraisonAgentRegistry loaded %d agents: %s",
            len(loaded),
            list(loaded.keys()),
        )

    def reload(self) -> None:
        """Force-reload the agent definitions from disk. Thread-safe."""
        with self._lock:
            self._loaded = False
            self._agents.clear()
            self._load_locked()

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_agent(self, agent_id: str) -> AgentIdentity:
        """
        Return the AgentIdentity for the given agent_id.
        Raises KeyError if not found. Lazy-loads on first call.

        All access is under the registry lock to prevent TOCTOU races.
        """
        self._ensure_loaded()
        with self._lock:
            if agent_id not in self._agents:
                available = sorted(self._agents.keys())
                raise KeyError(
                    f"Agent '{agent_id}' not found in registry. "
                    f"Available agents: {available}"
                )
            return self._agents[agent_id]

    def list_agents(self) -> list[dict[str, Any]]:
        """Return serialized agent identity dicts. Safe for API responses."""
        self._ensure_loaded()
        with self._lock:
            return [a.to_dict() for a in self._agents.values()]

    def agent_ids(self) -> list[str]:
        """Return list of all registered agent IDs."""
        self._ensure_loaded()
        with self._lock:
            return list(self._agents.keys())

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_agent_policy(
        self,
        agent_config: dict[str, Any],
        agent_id: str = "<unknown>",
    ) -> None:
        """
        Validate an agent config dict against required fields and policy rules.
        Raises ValueError with a descriptive message on any violation.
        """
        # Required fields
        missing = _REQUIRED_FIELDS - set(agent_config.keys())
        if missing:
            raise ValueError(f"Missing required fields: {sorted(missing)}")

        # risk_profile
        profile = str(agent_config.get("risk_profile", "standard"))
        if profile not in VALID_RISK_PROFILES:
            raise ValueError(
                f"Invalid risk_profile '{profile}'. "
                f"Must be one of: {sorted(VALID_RISK_PROFILES)}"
            )

        # memory_scope
        scope = str(agent_config.get("memory_scope", "session"))
        if scope not in VALID_MEMORY_SCOPES:
            raise ValueError(
                f"Invalid memory_scope '{scope}'. "
                f"Must be one of: {sorted(VALID_MEMORY_SCOPES)}"
            )

        # review_policy
        policy = str(agent_config.get("review_policy", "standard"))
        if policy not in VALID_REVIEW_POLICIES:
            raise ValueError(
                f"Invalid review_policy '{policy}'. "
                f"Must be one of: {sorted(VALID_REVIEW_POLICIES)}"
            )

        # allowed_tools must be a list if present
        tools = agent_config.get("allowed_tools", [])
        if not isinstance(tools, list):
            raise ValueError(
                f"allowed_tools must be a list, got {type(tools).__name__}"
            )

        # agent_class
        agent_class = str(agent_config.get("agent_class", "specialist"))
        if agent_class not in VALID_AGENT_CLASSES:
            raise ValueError(
                f"Invalid agent_class '{agent_class}'. "
                f"Must be one of: {sorted(VALID_AGENT_CLASSES)}"
            )

        # delegation_scope
        delegation_scope = str(agent_config.get("delegation_scope", "none"))
        if delegation_scope not in VALID_DELEGATION_SCOPES:
            raise ValueError(
                f"Invalid delegation_scope '{delegation_scope}'. "
                f"Must be one of: {sorted(VALID_DELEGATION_SCOPES)}"
            )

        # handoff_policy
        handoff_policy = str(agent_config.get("handoff_policy", "coordinator_visible"))
        if handoff_policy not in VALID_HANDOFF_POLICIES:
            raise ValueError(
                f"Invalid handoff_policy '{handoff_policy}'. "
                f"Must be one of: {sorted(VALID_HANDOFF_POLICIES)}"
            )

        # interrupt_policy
        interrupt_policy = str(agent_config.get("interrupt_policy", "none"))
        if interrupt_policy not in VALID_INTERRUPT_POLICIES:
            raise ValueError(
                f"Invalid interrupt_policy '{interrupt_policy}'. "
                f"Must be one of: {sorted(VALID_INTERRUPT_POLICIES)}"
            )

        # escalation_policy
        escalation_policy = str(agent_config.get("escalation_policy", "hil_for_band2"))
        if escalation_policy not in VALID_ESCALATION_POLICIES:
            raise ValueError(
                f"Invalid escalation_policy '{escalation_policy}'. "
                f"Must be one of: {sorted(VALID_ESCALATION_POLICIES)}"
            )

        # specialists must have delegation_scope=none
        if agent_class == "specialist" and delegation_scope != "none":
            raise ValueError(
                f"Specialists must have delegation_scope=none, got '{delegation_scope}'"
            )

        # governors must be able to delegate
        if agent_class == "governor" and delegation_scope == "none":
            raise ValueError(
                f"Governors must have delegation_scope != none"
            )

        # allowed_peer_targets must be a list if present
        peer_targets = agent_config.get("allowed_peer_targets", [])
        if not isinstance(peer_targets, list):
            raise ValueError(
                f"allowed_peer_targets must be a list, got {type(peer_targets).__name__}"
            )

    # ── Instantiation ─────────────────────────────────────────────────────────

    def instantiate_agent(
        self,
        agent_id: str,
        framework: str,
        workflow_id: str = "",
        program_id: str = "",
        parent_agent: str = "",
    ) -> Any:
        """
        Instantiate a framework-native agent object from a registered identity.

        The agent_spawn governance hook fires before instantiation. If the
        governance layer blocks the spawn, PraisonGovernanceError is raised.

        Args:
            agent_id:     Registry key (e.g. "SecurityGovernorAgent")
            framework:    Target framework: crewai | autogen | deepagents | langgraph
            workflow_id:  Active campaign workflow ID
            program_id:   Bug bounty program ID
            parent_agent: agent_id of spawning agent (for hierarchy audit)

        Returns:
            Framework-native agent object (CrewAI Agent, AutoGen agent dict,
            DeepAgents agent, or LangGraph node spec dict).

        Raises:
            KeyError:               agent_id not in registry
            PraisonGovernanceError: spawn blocked by governance policy
            ValueError:             unknown framework
            NotImplementedError:    framework not yet installed (adapters raise this)
        """
        # Resolve identity and populate runtime fields
        identity = self.get_agent(agent_id).with_runtime(
            workflow_id=workflow_id,
            program_id=program_id,
            parent_agent=parent_agent,
        )

        # Fire agent_spawn governance hook
        self._fire_spawn_hook(identity, framework)

        # Route to appropriate adapter
        framework_key = framework.strip().lower()
        return self._dispatch_to_adapter(framework_key, identity)

    def _fire_spawn_hook(self, identity: AgentIdentity, framework: str) -> None:
        """Fire the agent_spawn hook. PraisonGovernanceError propagates up."""
        try:
            from apps.backend.src.core.hook_registry import get_hook_registry
        except ImportError:
            logger.warning("hook_registry not available — skipping agent_spawn hook")
            return

        try:
            get_hook_registry().run(
                "agent_spawn",
                {
                    "hook_type":    "agent_spawn",
                    "agent_id":     identity.agent_id,
                    "framework":    framework,
                    "workflow_id":  identity.workflow_id,
                    "program_id":   identity.program_id,
                    "parent_agent": identity.parent_agent,
                    "risk_profile": identity.risk_profile,
                    "execution_id": identity.execution_id,
                },
            )
        except Exception:
            raise  # PraisonGovernanceError and others propagate unchanged

    def _dispatch_to_adapter(self, framework: str, identity: AgentIdentity) -> Any:
        """Route identity to the correct framework adapter."""
        if framework == "crewai":
            from apps.backend.src.core.praison_adapters.crewai_adapter import to_crewai_agent
            return to_crewai_agent(identity)
        elif framework == "autogen":
            from apps.backend.src.core.praison_adapters.autogen_adapter import to_autogen_agent
            return to_autogen_agent(identity)
        elif framework == "deepagents":
            from apps.backend.src.core.praison_adapters.deepagents_adapter import to_deepagents_agent
            return to_deepagents_agent(identity)
        elif framework == "langgraph":
            from apps.backend.src.core.praison_adapters.langgraph_adapter import to_langgraph_node
            return to_langgraph_node(identity)
        else:
            raise ValueError(
                f"Unknown framework '{framework}'. "
                "Must be one of: crewai, autogen, deepagents, langgraph"
            )


# ── Module-level singleton ────────────────────────────────────────────────────

_registry: PraisonAgentRegistry | None = None
_registry_lock = Lock()


def get_agent_registry() -> PraisonAgentRegistry:
    """Return the initialized PraisonAgentRegistry singleton."""
    global _registry
    if _registry is None:
        raise RuntimeError(
            "PraisonAgentRegistry not initialized. "
            "Call initialize_agent_registry() during application startup."
        )
    return _registry


def initialize_agent_registry(config_path: str | None = None) -> PraisonAgentRegistry:
    """
    Initialize the PraisonAgentRegistry singleton and eagerly load agents.
    Call once during app startup after PraisonGovernor is initialized.
    """
    global _registry
    with _registry_lock:
        _registry = PraisonAgentRegistry(config_path)
        _registry.load_agents()
        logger.info(
            "PraisonAgentRegistry initialized with %d agents: %s",
            len(_registry.agent_ids()),
            _registry.agent_ids(),
        )
    return _registry
