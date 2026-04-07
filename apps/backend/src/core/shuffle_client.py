"""
Shuffle SOAR (Security Orchestration, Automation, and Response) Integration
for KAISON AI.

Shuffle automates incident response workflows triggered by findings
and mission events. Integrates with TheHive, Wazuh, and external
ticketing systems.

Credentials: SHUFFLE_URL, SHUFFLE_WEBHOOK_TOKEN via Vault.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .secret_manager import get_secret_manager

logger = logging.getLogger(__name__)


class ShuffleClient:
    """
    Shuffle SOAR integration for KAISON AI.

    Triggers automated incident response workflows when:
    - Critical findings discovered
    - Mission approval required
    - Host anomalies detected
    - Findings escalated to high risk

    Workflows are defined in workflows/shuffle/ as JSON specs.
    """

    def __init__(
        self,
        url: str = "",
        webhook_token: str = "",
    ):
        self.url = (
            url or
            get_secret_manager().get_optional(
                "SHUFFLE_URL"
            ) or "http://localhost:3001"
        ).rstrip("/")
        self.webhook_token = (
            webhook_token or
            get_secret_manager().get_optional(
                "SHUFFLE_WEBHOOK_TOKEN"
            ) or ""
        )
        self.session = requests.Session()
        if self.webhook_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.webhook_token}",
                "Content-Type": "application/json",
            })

    def health_check(self) -> bool:
        """
        Checks if Shuffle is reachable and responding.
        Returns True if healthy, False otherwise.
        """
        try:
            url = f"{self.url}/api/v1/health"
            response = self.session.get(
                url,
                timeout=10,
            )
            return response.status_code < 400
        except Exception as e:
            logger.warning(
                "Shuffle health check failed: %s",
                e,
            )
            return False

    def trigger_webhook(
        self,
        webhook_id: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Triggers a Shuffle webhook with arbitrary data.

        Args:
            webhook_id: Shuffle webhook ID (UUID)
            data: Payload dict to send

        Returns:
            True on success, False on failure
        """
        if not self.webhook_token:
            logger.warning(
                "Shuffle webhook token not configured"
            )
            return False

        try:
            url = f"{self.url}/api/v1/webhooks/{webhook_id}"
            response = self.session.post(
                url,
                json=data,
                timeout=30,
            )
            return response.status_code < 400

        except Exception as e:
            logger.error(
                "Shuffle webhook trigger failed: %s",
                e,
            )
            return False

    def trigger_critical_finding_workflow(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> bool:
        """
        Triggers incident response workflow for critical findings.

        Workflow actions typically:
        - Create/escalate TheHive case to critical
        - Send alert to on-call team
        - Initiate containment procedures
        - Create JIRA/Zendesk ticket if configured

        Args:
            finding: Finding dict with severity, type, target, etc.
            scan_context: Scan context with scan_id, mission_id, etc.

        Returns:
            True on success
        """
        if not self.webhook_token:
            return False

        try:
            payload = {
                "event_type": "critical_finding",
                "severity": finding.get(
                    "severity", "unknown"
                ),
                "finding_type": finding.get(
                    "type", "unknown"
                ),
                "finding_value": finding.get(
                    "value", "unknown"
                ),
                "target": finding.get(
                    "target", "unknown"
                ),
                "scan_id": scan_context.get(
                    "scan_id"
                ),
                "mission_id": scan_context.get(
                    "mission_id"
                ),
                "program_name": scan_context.get(
                    "program_name"
                ),
                "confidence": finding.get(
                    "confidence", 0.0
                ),
                "raw_evidence": finding.get(
                    "raw_evidence", ""
                ),
            }

            webhook_id = (
                get_secret_manager().get_optional(
                    "SHUFFLE_CRITICAL_FINDING_WEBHOOK_ID"
                )
            )
            if not webhook_id:
                logger.warning(
                    "SHUFFLE_CRITICAL_FINDING_WEBHOOK_ID "
                    "not configured"
                )
                return False

            return self.trigger_webhook(
                webhook_id,
                payload,
            )

        except Exception as e:
            logger.error(
                "Critical finding workflow failed: %s",
                e,
            )
            return False

    def trigger_mission_complete_workflow(
        self,
        mission_id: str,
        scan_context: dict[str, Any],
        statistics: dict[str, Any],
    ) -> bool:
        """
        Triggers workflow when mission completes.

        Workflow actions typically:
        - Generate final report
        - Close all related cases if no critical findings
        - Archive artifacts
        - Send completion summary

        Args:
            mission_id: Mission ID
            scan_context: Scan context dict
            statistics: Mission stats (total_findings, critical, etc.)

        Returns:
            True on success
        """
        if not self.webhook_token:
            return False

        try:
            payload = {
                "event_type": "mission_complete",
                "mission_id": mission_id,
                "scan_id": scan_context.get(
                    "scan_id"
                ),
                "program_name": scan_context.get(
                    "program_name"
                ),
                "total_findings": statistics.get(
                    "total_findings", 0
                ),
                "critical_findings": statistics.get(
                    "critical_findings", 0
                ),
                "high_findings": statistics.get(
                    "high_findings", 0
                ),
                "duration_seconds": statistics.get(
                    "duration_seconds", 0
                ),
            }

            webhook_id = (
                get_secret_manager().get_optional(
                    "SHUFFLE_MISSION_COMPLETE_WEBHOOK_ID"
                )
            )
            if not webhook_id:
                logger.warning(
                    "SHUFFLE_MISSION_COMPLETE_WEBHOOK_ID "
                    "not configured"
                )
                return False

            return self.trigger_webhook(
                webhook_id,
                payload,
            )

        except Exception as e:
            logger.error(
                "Mission complete workflow failed: %s",
                e,
            )
            return False

    def trigger_approval_required_workflow(
        self,
        finding: dict[str, Any],
        reason: str,
        scan_context: dict[str, Any],
    ) -> bool:
        """
        Triggers workflow when human approval required.

        Workflow actions typically:
        - Notify approval team
        - Create approval ticket
        - Escalate to manager
        - Log to audit trail

        Args:
            finding: Finding requiring approval
            reason: Human-readable reason (e.g., "Low confidence")
            scan_context: Scan context dict

        Returns:
            True on success
        """
        if not self.webhook_token:
            return False

        try:
            payload = {
                "event_type": "approval_required",
                "finding_type": finding.get(
                    "type", "unknown"
                ),
                "finding_value": finding.get(
                    "value", "unknown"
                ),
                "target": finding.get(
                    "target", "unknown"
                ),
                "confidence": finding.get(
                    "confidence", 0.0
                ),
                "severity": finding.get(
                    "severity", "unknown"
                ),
                "reason": reason,
                "mission_id": scan_context.get(
                    "mission_id"
                ),
                "scan_id": scan_context.get(
                    "scan_id"
                ),
            }

            webhook_id = (
                get_secret_manager().get_optional(
                    "SHUFFLE_APPROVAL_WEBHOOK_ID"
                )
            )
            if not webhook_id:
                logger.warning(
                    "SHUFFLE_APPROVAL_WEBHOOK_ID "
                    "not configured"
                )
                return False

            return self.trigger_webhook(
                webhook_id,
                payload,
            )

        except Exception as e:
            logger.error(
                "Approval workflow failed: %s",
                e,
            )
            return False

    def trigger_host_anomaly_workflow(
        self,
        anomaly_data: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> bool:
        """
        Triggers incident response for host anomalies
        detected by Wazuh during scanning.

        Workflow actions typically:
        - Pause mission
        - Alert security team
        - Initiate incident investigation
        - Log for forensics

        Args:
            anomaly_data: Anomaly dict from Wazuh
            scan_context: Scan context dict

        Returns:
            True on success
        """
        if not self.webhook_token:
            return False

        try:
            payload = {
                "event_type": "host_anomaly_detected",
                "anomalies_detected": anomaly_data.get(
                    "anomalies_detected", False
                ),
                "alert_count": anomaly_data.get(
                    "alert_count", 0
                ),
                "highest_severity": anomaly_data.get(
                    "highest_severity", 0
                ),
                "summary": anomaly_data.get(
                    "summary", "Unknown anomaly"
                ),
                "mission_id": scan_context.get(
                    "mission_id"
                ),
                "scan_id": scan_context.get(
                    "scan_id"
                ),
            }

            webhook_id = (
                get_secret_manager().get_optional(
                    "SHUFFLE_ANOMALY_WEBHOOK_ID"
                )
            )
            if not webhook_id:
                logger.warning(
                    "SHUFFLE_ANOMALY_WEBHOOK_ID "
                    "not configured"
                )
                return False

            return self.trigger_webhook(
                webhook_id,
                payload,
            )

        except Exception as e:
            logger.error(
                "Anomaly workflow failed: %s",
                e,
            )
            return False
