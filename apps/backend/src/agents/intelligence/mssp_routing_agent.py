"""
MSSP Routing Agent for KAISON AI.

Routes findings and alerts to Managed Security Service Provider
platforms via syslog (RFC 5424) for centralized monitoring,
alerting, and ticket generation.

Runs in parallel with Shuffle to enable hybrid orchestration:
- Shuffle handles internal workflows
- MSSP handles external security operations
"""
from __future__ import annotations

import logging
from typing import Any

from core.mssp_client import MSPPClient

logger = logging.getLogger(__name__)


class MSPPRoutingAgent:
    """
    Routes findings and alerts to MSSP platforms
    for centralized security operations monitoring.

    Sends via syslog (RFC 5424) for:
    - Real-time alert streaming
    - MSSP platform ingestion
    - Ticket/case auto-generation
    - Audit trail maintenance
    """

    def __init__(self):
        self.client = MSPPClient()

    def route_finding_to_mssp(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Routes confirmed finding to MSSP via syslog.

        All findings (regardless of severity) are sent
        to MSSP for centralized tracking and reporting.

        Args:
            finding: Finding dict with severity, type, etc.
            scan_context: Scan context dict

        Returns:
            {
              sent: bool,
              message: str,
            }
        """
        result = {
            "sent": False,
            "message": "Not sent",
        }

        try:
            success = (
                self.client.send_finding_to_mssp(
                    finding,
                    scan_context,
                )
            )

            result["sent"] = success
            if success:
                result["message"] = (
                    "Finding sent to MSSP"
                )
                logger.info(
                    "Mission %s: finding sent to MSSP",
                    scan_context.get(
                        "mission_id"
                    ),
                )
            else:
                result["message"] = (
                    "Failed to send to MSSP"
                )
                logger.error(
                    "Failed to send finding to MSSP"
                )

            return result

        except Exception as e:
            logger.error(
                "Finding routing failed: %s",
                e,
            )
            result["message"] = f"Error: {e}"
            return result

    def route_critical_alert_to_mssp(
        self,
        severity: str,
        message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Routes critical alert to MSSP for immediate attention.

        Used for:
        - Critical findings requiring urgent action
        - Host anomalies detected during scanning
        - Policy violations or access issues
        - Operational emergencies

        Args:
            severity: Alert severity
            message: Alert message
            context: Additional context dict

        Returns:
            {
              sent: bool,
              message: str,
            }
        """
        result = {
            "sent": False,
            "message": "Not sent",
        }

        try:
            success = (
                self.client.send_alert_to_mssp(
                    "critical_alert",
                    severity,
                    message,
                    context,
                )
            )

            result["sent"] = success
            if success:
                result["message"] = (
                    "Alert sent to MSSP"
                )
                logger.warning(
                    "Critical alert sent to MSSP: %s",
                    message,
                )
            else:
                result["message"] = (
                    "Failed to send alert"
                )

            return result

        except Exception as e:
            logger.error(
                "Alert routing failed: %s",
                e,
            )
            result["message"] = f"Error: {e}"
            return result

    def route_mission_status_to_mssp(
        self,
        mission_id: str,
        status: str,
        statistics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Routes mission status update to MSSP.

        Provides periodic status updates for ongoing
        missions to keep MSSP informed of progress.

        Args:
            mission_id: Mission ID
            status: Mission status
            statistics: Mission stats

        Returns:
            {
              sent: bool,
              message: str,
            }
        """
        result = {
            "sent": False,
            "message": "Not sent",
        }

        try:
            context = {
                "mission_id": mission_id,
                "status": status,
                **statistics,
            }

            success = (
                self.client.send_alert_to_mssp(
                    "mission_status",
                    "info",
                    f"Mission {mission_id}: {status}",
                    context,
                )
            )

            result["sent"] = success
            if success:
                result["message"] = (
                    "Status sent to MSSP"
                )
            else:
                result["message"] = (
                    "Failed to send status"
                )

            return result

        except Exception as e:
            logger.error(
                "Status routing failed: %s",
                e,
            )
            result["message"] = f"Error: {e}"
            return result

    def handle_mssp_webhook(
        self,
        payload: str,
        signature: str,
    ) -> dict[str, Any]:
        """
        Handles incoming MSSP webhook request.

        Verifies signature and processes acknowledgments,
        updates, or other messages from MSSP platform.

        Args:
            payload: Request body (JSON)
            signature: X-MSSP-Signature header

        Returns:
            {
              valid: bool,
              processed: bool,
              message: str,
              data: dict or None,
            }
        """
        result = {
            "valid": False,
            "processed": False,
            "message": "Invalid signature",
            "data": None,
        }

        try:
            # Verify signature
            if not self.client.verify_webhook_request(
                payload,
                signature,
            ):
                logger.warning(
                    "Invalid MSSP webhook signature"
                )
                return result

            result["valid"] = True
            result["message"] = (
                "Signature verified"
            )

            # Parse payload
            import json
            data = json.loads(payload)

            # Process based on event type
            event_type = data.get("event_type")

            if event_type == "acknowledgment":
                self.client.acknowledge_finding(
                    data.get("finding_id"),
                    data.get("ticket_id"),
                    data.get("status"),
                )
                result["processed"] = True
                result["message"] = (
                    "Acknowledgment recorded"
                )

            elif event_type == "status_update":
                logger.info(
                    "MSSP status update: %s",
                    data,
                )
                result["processed"] = True
                result["message"] = (
                    "Status update recorded"
                )

            else:
                logger.warning(
                    "Unknown MSSP event type: %s",
                    event_type,
                )
                result["message"] = (
                    f"Unknown event: {event_type}"
                )

            result["data"] = data
            return result

        except json.JSONDecodeError as e:
            logger.error(
                "MSSP webhook JSON decode failed: %s",
                e,
            )
            result["message"] = "Invalid JSON"
            return result

        except Exception as e:
            logger.error(
                "MSSP webhook handling failed: %s",
                e,
            )
            result["message"] = f"Error: {e}"
            return result

    def pre_mission_check(
        self,
        mission_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verifies MSSP connectivity before mission starts.

        Returns:
            {
              safe_to_proceed: bool,
              reason: str,
            }
        """
        try:
            health = self.client.health_check()
            if not health:
                return {
                    "safe_to_proceed": False,
                    "reason": (
                        "MSSP is unavailable"
                    ),
                }

            return {
                "safe_to_proceed": True,
                "reason": (
                    "MSSP is healthy"
                ),
            }

        except Exception as e:
            logger.error(
                "Pre-mission check failed: %s",
                e,
            )
            return {
                "safe_to_proceed": False,
                "reason": f"Error: {e}",
            }
