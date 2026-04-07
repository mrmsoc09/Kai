"""
Shuffle Orchestration Agent for KAISON AI.

Routes findings and mission events to Shuffle workflows for
automated incident response orchestration.

Runs alongside TheHive handoff and Wazuh monitoring to trigger
response workflows based on severity, confidence, and anomalies.
"""
from __future__ import annotations

import logging
from typing import Any

from core.shuffle_client import ShuffleClient

logger = logging.getLogger(__name__)


class ShuffleOrchestrationAgent:
    """
    Routes findings and mission events to Shuffle
    for automated incident response orchestration.

    Receives findings from evidence analysis pipeline
    and routes to appropriate Shuffle workflows:
    - Critical findings → incident response
    - Approval-required → approval workflow
    - Mission complete → closure/reporting
    - Anomalies → containment
    """

    def __init__(self):
        self.client = ShuffleClient()

    def route_finding(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Routes finding to appropriate Shuffle workflow.

        Logic:
        - If critical → trigger critical finding workflow
        - If confidence < threshold → trigger approval workflow
        - Otherwise → log only (no workflow)

        Args:
            finding: Confirmed finding dict with:
              - type: vulnerability type
              - severity: critical/high/medium/low
              - value: finding title
              - target: affected resource
              - confidence: confidence score
            scan_context: Scan context with:
              - scan_id: KAISON scan ID
              - mission_id: Mission ID
              - program_name: Bug bounty program

        Returns:
            {
              routed: bool,
              workflow_type: str or None,
              success: bool,
              message: str,
            }
        """
        result = {
            "routed": False,
            "workflow_type": None,
            "success": False,
            "message": "Not routed",
        }

        try:
            severity = finding.get(
                "severity", "low"
            ).lower()
            confidence = finding.get(
                "confidence", 0.0
            )

            # Route critical findings to incident response
            if severity == "critical":
                success = (
                    self.client.trigger_critical_finding_workflow(
                        finding,
                        scan_context,
                    )
                )
                result["routed"] = True
                result["workflow_type"] = (
                    "critical_finding"
                )
                result["success"] = success
                result["message"] = (
                    "Critical finding routed "
                    "to incident response"
                )

                if success:
                    logger.info(
                        "Mission %s: routed critical "
                        "finding to Shuffle",
                        scan_context.get(
                            "mission_id"
                        ),
                    )
                else:
                    logger.error(
                        "Failed to route critical "
                        "finding to Shuffle"
                    )

            # Route low-confidence findings to approval
            elif confidence < 0.6:
                success = (
                    self.client.trigger_approval_required_workflow(
                        finding,
                        "Low confidence score",
                        scan_context,
                    )
                )
                result["routed"] = True
                result["workflow_type"] = (
                    "approval_required"
                )
                result["success"] = success
                result["message"] = (
                    "Low confidence finding "
                    "routed to approval"
                )

                if success:
                    logger.info(
                        "Mission %s: routed "
                        "low-confidence finding "
                        "to approval",
                        scan_context.get(
                            "mission_id"
                        ),
                    )
                else:
                    logger.error(
                        "Failed to route finding "
                        "to approval workflow"
                    )

            else:
                result["message"] = (
                    "Finding does not match "
                    "routing criteria"
                )

            return result

        except Exception as e:
            logger.error(
                "Finding routing failed: %s",
                e,
            )
            result["success"] = False
            result["message"] = f"Error: {e}"
            return result

    def route_mission_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Routes mission-level events to Shuffle workflows.

        Event types:
        - mission_complete: mission finished
        - host_anomaly: Wazuh detected anomaly
        - approval_required: manual intervention needed

        Args:
            event_type: Type of mission event
            event_data: Event-specific data dict
            scan_context: Scan context dict

        Returns:
            {
              routed: bool,
              workflow_type: str or None,
              success: bool,
              message: str,
            }
        """
        result = {
            "routed": False,
            "workflow_type": None,
            "success": False,
            "message": "Not routed",
        }

        try:
            if event_type == "mission_complete":
                success = (
                    self.client.trigger_mission_complete_workflow(
                        scan_context.get(
                            "mission_id"
                        ),
                        scan_context,
                        event_data,
                    )
                )
                result["routed"] = True
                result["workflow_type"] = (
                    "mission_complete"
                )
                result["success"] = success
                result["message"] = (
                    "Mission completion "
                    "routed to closure workflow"
                )

                if success:
                    logger.info(
                        "Mission %s: routed "
                        "completion to Shuffle",
                        scan_context.get(
                            "mission_id"
                        ),
                    )

            elif event_type == "host_anomaly":
                success = (
                    self.client.trigger_host_anomaly_workflow(
                        event_data,
                        scan_context,
                    )
                )
                result["routed"] = True
                result["workflow_type"] = (
                    "host_anomaly"
                )
                result["success"] = success
                result["message"] = (
                    "Anomaly detected, "
                    "routed to containment"
                )

                if success:
                    logger.warning(
                        "Mission %s: routed "
                        "anomaly to Shuffle",
                        scan_context.get(
                            "mission_id"
                        ),
                    )

            else:
                result["message"] = (
                    f"Unknown event type: "
                    f"{event_type}"
                )

            return result

        except Exception as e:
            logger.error(
                "Mission event routing failed: %s",
                e,
            )
            result["success"] = False
            result["message"] = f"Error: {e}"
            return result

    def pre_mission_check(
        self,
        mission_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verifies Shuffle is available before mission starts.

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
                        "Shuffle is unavailable"
                    ),
                }

            return {
                "safe_to_proceed": True,
                "reason": (
                    "Shuffle is healthy"
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
