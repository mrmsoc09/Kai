"""
K1 PraisonAI Framework Adapters
=================================
Converts Praison AgentIdentity objects into framework-native agent instances.
All LLM routing goes through praison_agent.resolve_litellm_string() which
reads from llm_providers.py provider configuration.

Supported frameworks:
    crewai       → crewai_adapter.py
    autogen      → autogen_adapter.py
    deepagents   → deepagents_adapter.py
    langgraph    → langgraph_adapter.py  (scaffold — awaits Platform 3 build)

No adapter defines agent personas. All personas originate from agents.yaml
via PraisonAgentRegistry.
"""

from __future__ import annotations


class FrameworkNotInstalledError(ImportError):
    """
    Raised when a framework adapter's required package is not installed.
    Provides a clear installation instruction.
    """

    def __init__(self, framework: str, package: str, install_hint: str = ""):
        self.framework = framework
        self.package = package
        msg = f"Framework '{framework}' requires package '{package}' which is not installed."
        if install_hint:
            msg += f" Install it with: {install_hint}"
        super().__init__(msg)
