from __future__ import annotations

import logging
from typing import Any

from ..base_tool_agent import BaseToolAgent
from apps.backend.src.core.hil_thehive_client import TheHiveClient

logger = logging.getLogger(__name__)


class TheHiveAgent(BaseToolAgent):
    """
    TheHive case management agent — creates and tracks cases for findings
    discovered during bug hunts. Delegates to TheHiveClient (Vault-backed).
    """

    TOOL_NAME = "thehive"
    DEFAULT_TIMEOUT_SECONDS = 60
    EXECUTION_MODE = "api"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: TheHiveClient | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def _get_client(self) -> TheHiveClient:
        if self._client is None:
            self._client = TheHiveClient()
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
        Create or update a TheHive case for a finding.

        options:
          finding (dict): finding to create a case for (required)
          scan_id (str): KAISON scan ID (default: target)
          program_name (str): bug bounty program name
        """
        opts = options or {}
        client = self._get_client()

        if not client.health_check():
            logger.warning("TheHive unreachable — skipping case creation for %s", target)
            return {
                "tool": self.TOOL_NAME,
                "target": target,
                "healthy": False,
                "case_id": None,
            }

        finding = opts.get("finding") or {"target": target, "value": target, "severity": "info"}
        scan_id = opts.get("scan_id", target)
        program_name = opts.get("program_name", "unknown")

        case_id = client.create_case_from_finding(
            finding=finding,
            scan_id=scan_id,
            program_name=program_name,
        )

        return {
            "tool": self.TOOL_NAME,
            "target": target,
            "healthy": True,
            "case_id": case_id,
            "case_created": case_id is not None,
        }
