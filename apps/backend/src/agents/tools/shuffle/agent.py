from __future__ import annotations

import logging
from typing import Any

from ..base_tool_agent import BaseToolAgent
from apps.backend.src.core.shuffle_client import ShuffleClient

logger = logging.getLogger(__name__)


class ShuffleAgent(BaseToolAgent):
    """
    Shuffle SOAR agent — triggers automated incident response workflows
    for findings, mission completions, and approval gates.
    Delegates to ShuffleClient (Vault-backed credentials).
    """

    TOOL_NAME = "shuffle"
    DEFAULT_TIMEOUT_SECONDS = 60
    EXECUTION_MODE = "api"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client: ShuffleClient | None = None

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def _get_client(self) -> ShuffleClient:
        if self._client is None:
            self._client = ShuffleClient()
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
        Trigger a Shuffle SOAR workflow.

        options:
          workflow_type (str): "critical_finding" | "mission_complete" |
                               "approval_required" | "host_anomaly" | "webhook"
          finding (dict): finding dict (for critical_finding / approval_required)
          scan_context (dict): scan context dict
          statistics (dict): mission stats (for mission_complete)
          anomaly_data (dict): anomaly dict (for host_anomaly)
          webhook_id (str): explicit webhook ID (for workflow_type="webhook")
          payload (dict): raw payload (for workflow_type="webhook")
          reason (str): approval reason (for approval_required)
        """
        opts = options or {}
        client = self._get_client()

        if not client.health_check():
            logger.warning("Shuffle unreachable — skipping workflow for %s", target)
            return {
                "tool": self.TOOL_NAME,
                "target": target,
                "healthy": False,
                "triggered": False,
            }

        workflow_type = opts.get("workflow_type", "webhook")
        scan_context = opts.get("scan_context", {"scan_id": target, "mission_id": target})
        triggered = False

        if workflow_type == "critical_finding":
            finding = opts.get("finding", {})
            triggered = client.trigger_critical_finding_workflow(finding, scan_context)

        elif workflow_type == "mission_complete":
            mission_id = opts.get("mission_id", target)
            statistics = opts.get("statistics", {})
            triggered = client.trigger_mission_complete_workflow(
                mission_id, scan_context, statistics
            )

        elif workflow_type == "approval_required":
            finding = opts.get("finding", {})
            reason = opts.get("reason", "Human review required")
            triggered = client.trigger_approval_required_workflow(
                finding, reason, scan_context
            )

        elif workflow_type == "host_anomaly":
            anomaly_data = opts.get("anomaly_data", {})
            triggered = client.trigger_host_anomaly_workflow(anomaly_data, scan_context)

        elif workflow_type == "webhook":
            webhook_id = opts.get("webhook_id", "")
            payload = opts.get("payload", {})
            if webhook_id:
                triggered = client.trigger_webhook(webhook_id, payload)
            else:
                logger.warning("ShuffleAgent: webhook_id required for workflow_type='webhook'")

        return {
            "tool": self.TOOL_NAME,
            "target": target,
            "healthy": True,
            "workflow_type": workflow_type,
            "triggered": triggered,
        }
