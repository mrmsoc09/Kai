from __future__ import annotations

import logging
from typing import Any

from ..base_tool_agent import BaseToolAgent
from apps.backend.src.core.misp_client import MISPClient

logger = logging.getLogger(__name__)


class MISPAgent(BaseToolAgent):
    """
    MISP threat intelligence agent — enriches IOCs and findings with
    community threat intelligence. Delegates to MISPClient (Vault-backed).
    """

    TOOL_NAME = "misp"
    DEFAULT_TIMEOUT_SECONDS = 60
    EXECUTION_MODE = "api"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: MISPClient | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def _get_client(self) -> MISPClient:
        if self._client is None:
            self._client = MISPClient()
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
        Enrich target IOC against MISP threat intelligence.

        options:
          ioc_type (str): "ip" | "domain" | "url" | "hash" (default: "domain")
          finding (dict): if present, add finding as a new MISP event
          scan_id (str): scan ID for MISP event tagging
        """
        opts = options or {}
        client = self._get_client()

        if not client.health_check():
            logger.warning("MISP unreachable — skipping enrichment for %s", target)
            return {
                "tool": self.TOOL_NAME,
                "target": target,
                "healthy": False,
                "enrichment": {},
                "event_created": None,
            }

        ioc_type = opts.get("ioc_type", "domain")
        enrichment = client.enrich_ioc(ioc_type=ioc_type, ioc_value=target)

        event_uuid = None
        if opts.get("finding"):
            scan_id = opts.get("scan_id", target)
            event_uuid = client.add_finding_as_event(opts["finding"], scan_id)

        return {
            "tool": self.TOOL_NAME,
            "target": target,
            "healthy": True,
            "enrichment": enrichment,
            "event_created": event_uuid,
            "known_malicious": enrichment.get("known_malicious", False),
            "attribute_hits": enrichment.get("attribute_hits", 0),
        }
