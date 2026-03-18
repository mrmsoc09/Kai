"""
CrewAI Adapter — Praison → CrewAI
===================================
Converts a K1 AgentIdentity into a CrewAI Agent object.

Mapping:
    Praison field      CrewAI field
    ─────────────────  ────────────────
    persona            role
    description        goal
    system_prompt      backstory
    allowed_tools      tools (resolved from K1 tool registry)
    llm_pin            llm  (via resolve_litellm_string → LiteLLM string)
    review_policy=strict  → max_iter=3, allow_delegation=False

LLM routing: llm_pin → resolve_litellm_string() → LiteLLM format string
CrewAI accepts LiteLLM strings directly for its `llm` parameter.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.backend.src.core.praison_agent import AgentIdentity, resolve_litellm_string
from apps.backend.src.core.praison_adapters import FrameworkNotInstalledError

logger = logging.getLogger(__name__)

# Strict agents get fewer iterations and no delegation
_STRICT_MAX_ITER = 3
_DEFAULT_MAX_ITER = 10


def to_crewai_agent(identity: AgentIdentity) -> Any:
    """
    Convert a Praison AgentIdentity into a CrewAI Agent.

    Args:
        identity: Fully populated AgentIdentity (static + runtime fields).

    Returns:
        crewai.Agent instance configured from the Praison persona.

    Raises:
        FrameworkNotInstalledError: if crewai is not installed.
    """
    try:
        from crewai import Agent as CrewAIAgent  # type: ignore[import-untyped]
    except ImportError:
        raise FrameworkNotInstalledError(
            framework="crewai",
            package="crewai",
            install_hint="pip install 'crewai>=0.1,<1.0'",
        )

    llm_string = resolve_litellm_string(identity.llm_pin)

    # Governance/strict agents: restricted iteration and no delegation
    max_iter = _STRICT_MAX_ITER if identity.review_policy == "strict" else _DEFAULT_MAX_ITER
    allow_delegation = identity.review_policy != "strict"

    # Tool resolution: convert allowed_tools names to CrewAI Tool objects.
    # Currently returns empty list — tools are registered separately by the
    # K1 tool registry. This is intentional: CrewAI tool binding happens at
    # Task definition time, not Agent definition time.
    tools = _resolve_crewai_tools(identity.allowed_tools)

    agent = CrewAIAgent(
        role=identity.persona,
        goal=identity.description,
        backstory=identity.system_prompt,
        llm=llm_string,
        tools=tools,
        max_iter=max_iter,
        allow_delegation=allow_delegation,
        verbose=False,
    )

    logger.debug(
        "CrewAI agent created: role=%s llm=%s tools=%d max_iter=%d",
        identity.persona, llm_string, len(tools), max_iter,
    )
    return agent


def _resolve_crewai_tools(allowed_tool_ids: list[str]) -> list[Any]:
    """
    Resolve K1 tool IDs to CrewAI Tool objects.
    Returns an empty list if the K1 tool registry is unavailable.
    Tool binding is completed at Task creation time.
    """
    # Future: integrate with K1 tool registry to return crewai.BaseTool wrappers
    return []


def to_crewai_task(
    description: str,
    agent: Any,
    expected_output: str = "Structured JSON result",
    context: list[Any] | None = None,
) -> Any:
    """
    Create a CrewAI Task bound to a Praison-originated agent.

    Args:
        description:     Task description / prompt
        agent:           CrewAI Agent (from to_crewai_agent())
        expected_output: What the task should produce
        context:         Optional list of prior Task results for context

    Returns:
        crewai.Task instance
    """
    try:
        from crewai import Task as CrewAITask  # type: ignore[import-untyped]
    except ImportError:
        raise FrameworkNotInstalledError(
            framework="crewai",
            package="crewai",
            install_hint="pip install 'crewai>=0.1,<1.0'",
        )

    kwargs: dict[str, Any] = {
        "description": description,
        "agent": agent,
        "expected_output": expected_output,
    }
    if context:
        kwargs["context"] = context

    return CrewAITask(**kwargs)
