"""
AutoGen Adapter — Praison → AutoGen2
=======================================
Converts a K1 AgentIdentity into an AutoGen agent configuration dict
and optionally an instantiated AssistantAgent.

Mapping:
    Praison field      AutoGen concept
    ─────────────────  ────────────────────────────────────
    agent_id           name
    persona            (injected into system_message preamble)
    system_prompt      system_message
    allowed_tools      tool_registry (resolved from K1 tool registry)
    llm_pin            llm_config.config_list[].model (via llm_providers routing)
    review_policy      governance middleware injection point

LLM routing: llm_pin → resolve_provider_enum() → llm_factory.providers[...].model
AutoGen uses a config_list format for its LLM configuration. The adapter
extracts the model name from the K1 llm_providers factory.

Two outputs:
    to_autogen_config()  → dict, safe for serialization / audit
    to_autogen_agent()   → AssistantAgent (requires pyautogen installed)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from apps.backend.src.core.praison_agent import AgentIdentity, resolve_litellm_string
from apps.backend.src.core.praison_adapters import FrameworkNotInstalledError

logger = logging.getLogger(__name__)


def to_autogen_config(identity: AgentIdentity) -> dict[str, Any]:
    """
    Convert AgentIdentity to an AutoGen agent configuration dict.
    Safe for serialization — no live objects. Use this for audit trails
    and when AutoGen is not installed.

    Returns:
        {
            "name":           str,
            "system_message": str,
            "llm_config":     dict,
            "allowed_tools":  list[str],
            "risk_profile":   str,
            "review_policy":  str,
            "workflow_id":    str,
            "program_id":     str,
        }
    """
    llm_model = _resolve_autogen_model(identity.llm_pin)

    system_message = (
        f"[Persona: {identity.persona}]\n\n"
        f"{identity.system_prompt}"
    )

    return {
        "name":           identity.agent_id,
        "system_message": system_message,
        "llm_config": {
            "config_list": [
                {
                    "model":   llm_model,
                    "api_key": _resolve_api_key_hint(identity.llm_pin),
                }
            ],
            "temperature": 0.1 if identity.review_policy == "strict" else 0.7,
            "timeout":     120,
        },
        "allowed_tools":  identity.allowed_tools,
        "risk_profile":   identity.risk_profile,
        "review_policy":  identity.review_policy,
        "workflow_id":    identity.workflow_id,
        "program_id":     identity.program_id,
    }


def to_autogen_agent(identity: AgentIdentity) -> Any:
    """
    Convert a Praison AgentIdentity to an AutoGen AssistantAgent instance.

    Args:
        identity: Fully populated AgentIdentity.

    Returns:
        autogen.AssistantAgent instance.

    Raises:
        FrameworkNotInstalledError: if pyautogen is not installed.
    """
    try:
        from autogen import AssistantAgent  # type: ignore[import-untyped]
    except ImportError:
        raise FrameworkNotInstalledError(
            framework="autogen",
            package="pyautogen",
            install_hint="pip install 'pyautogen>=0.3,<1.0'",
        )

    config = to_autogen_config(identity)

    agent = AssistantAgent(
        name=config["name"],
        system_message=config["system_message"],
        llm_config=config["llm_config"],
    )

    logger.debug(
        "AutoGen agent created: name=%s model=%s",
        config["name"],
        config["llm_config"]["config_list"][0]["model"],
    )
    return agent


def to_autogen_user_proxy(
    identity: AgentIdentity,
    human_input_mode: str = "NEVER",
) -> Any:
    """
    Create an AutoGen UserProxyAgent for a Praison-originated identity.
    Used when an agent needs to act as the task initiator in an AutoGen
    conversation group.

    Args:
        identity:         AgentIdentity for the proxy.
        human_input_mode: "NEVER" | "TERMINATE" | "ALWAYS"

    Returns:
        autogen.UserProxyAgent instance.
    """
    try:
        from autogen import UserProxyAgent  # type: ignore[import-untyped]
    except ImportError:
        raise FrameworkNotInstalledError(
            framework="autogen",
            package="pyautogen",
            install_hint="pip install 'pyautogen>=0.3,<1.0'",
        )

    config = to_autogen_config(identity)

    return UserProxyAgent(
        name=f"{config['name']}_proxy",
        system_message=config["system_message"],
        human_input_mode=human_input_mode,
        llm_config=config["llm_config"],
        code_execution_config=False,  # K1 tools are external; no local code execution
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_autogen_model(llm_pin: str | None) -> str:
    """
    Resolve the model string for AutoGen's config_list.
    Reads from the K1 llm_providers factory to stay in sync with platform config.
    """
    try:
        from apps.backend.src.core.llm_providers import llm_factory, LLMProvider
        from apps.backend.src.core.praison_agent import resolve_provider_enum

        provider_enum = resolve_provider_enum(llm_pin)
        if provider_enum and provider_enum in llm_factory.providers:
            return llm_factory.providers[provider_enum].model or _fallback_model(llm_pin)
    except Exception:
        pass  # Fall back to env-based resolution

    # Fallback: extract model from LiteLLM string
    litellm = resolve_litellm_string(llm_pin)
    # "anthropic/claude-sonnet-4-6" → "claude-sonnet-4-6"
    return litellm.split("/", 1)[-1] if "/" in litellm else litellm


def _fallback_model(llm_pin: str | None) -> str:
    provider = (llm_pin or os.getenv("K1_PRIMARY_LLM_PROVIDER", "anthropic")).lower()
    defaults = {
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o",
        "gemini": "gemini-1.5-pro",
        "ollama": "llama3",
        "gemma": "gemma:7b",
    }
    return defaults.get(provider, "claude-sonnet-4-6")


def _resolve_api_key_hint(llm_pin: str | None) -> str:
    """
    Return the env var name that holds the API key for this provider.
    AutoGen's config_list needs either the actual key or the env var name.
    We return a sentinel that AutoGen resolves at runtime to avoid
    embedding keys in config dicts.
    """
    provider = (llm_pin or os.getenv("K1_PRIMARY_LLM_PROVIDER", "anthropic")).lower()
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
        "gemini":    "GOOGLE_API_KEY",
        "ollama":    "",  # local, no key needed
        "gemma":     "GOOGLE_API_KEY",
    }
    return os.getenv(key_map.get(provider, ""), "")
