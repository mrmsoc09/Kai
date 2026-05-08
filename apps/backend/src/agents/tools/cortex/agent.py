from __future__ import annotations

import logging
from typing import Any

from ..base_tool_agent import BaseToolAgent
from apps.backend.src.core.cortex_client import CortexClient

logger = logging.getLogger(__name__)


class CortexAgent(BaseToolAgent):
    """
    Cortex analysis agent — runs enrichment analyzers against observables
    discovered during scanning. Delegates to CortexClient (Vault-backed).
    """

    TOOL_NAME = "cortex"
    DEFAULT_TIMEOUT_SECONDS = 120
    EXECUTION_MODE = "api"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: CortexClient | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def _get_client(self) -> CortexClient:
        if self._client is None:
            self._client = CortexClient()
        return self._client

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        return []

    def run(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Run Cortex analyzers against an observable.

        options:
          observable_type (str): "ip" | "domain" | "url" | "hash" (default: "domain")
          analyzers (list[str]): specific analyzer IDs (default: auto-select by type)
          wait (bool): wait for results (default: True)
        """
        opts = options or {}
        client = self._get_client()

        if not client.health_check():
            logger.warning("Cortex unreachable — skipping analysis for %s", target)
            return {
                "tool": self.TOOL_NAME,
                "target": target,
                "healthy": False,
                "results": [],
            }

        observable_type = opts.get("observable_type", "domain")
        preferred = opts.get("analyzers")
        wait = bool(opts.get("wait", True))

        results = client.analyze_observable(
            observable_type=observable_type,
            value=target,
            preferred_analyzers=preferred,
            wait=wait,
        )

        return {
            "tool": self.TOOL_NAME,
            "target": target,
            "healthy": True,
            "observable_type": observable_type,
            "results": results,
            "result_count": len(results),
            "successful": sum(1 for r in results if r.get("status") == "Success"),
        }
