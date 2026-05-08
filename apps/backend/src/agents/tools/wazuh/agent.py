from __future__ import annotations

import logging
from typing import Any

from ..base_tool_agent import BaseToolAgent
from apps.backend.src.core.wazuh_client import WazuhClient

logger = logging.getLogger(__name__)


class WazuhAgent(BaseToolAgent):
    """
    Wazuh SIEM agent — checks host anomaly alerts and reports
    platform findings into Wazuh for SIEM correlation.
    Delegates all I/O to WazuhClient (Vault-backed credentials).
    """

    TOOL_NAME = "wazuh"
    DEFAULT_TIMEOUT_SECONDS = 60
    EXECUTION_MODE = "api"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: WazuhClient | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def _get_client(self) -> WazuhClient:
        if self._client is None:
            self._client = WazuhClient()
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
        Check recent Wazuh host alerts and optionally report a finding.

        options:
          finding (dict): if present, send as a Wazuh alert
          hours (int): look-back window for recent alerts (default 1)
        """
        opts = options or {}
        client = self._get_client()

        if not client.health_check():
            logger.warning("Wazuh unreachable — skipping for %s", target)
            return {
                "tool": self.TOOL_NAME,
                "target": target,
                "healthy": False,
                "anomaly_check": {},
                "finding_sent": False,
            }

        anomaly_check = client.check_host_anomalies()
        finding_sent = False

        if opts.get("finding"):
            scan_context = opts.get("scan_context", {"scan_id": target})
            finding_sent = client.send_finding_alert(opts["finding"], scan_context)

        return {
            "tool": self.TOOL_NAME,
            "target": target,
            "healthy": True,
            "anomaly_check": anomaly_check,
            "finding_sent": finding_sent,
        }
