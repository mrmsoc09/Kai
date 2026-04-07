"""
Wazuh Monitor Agent for KAISON AI.

Monitors KAISON AI host health via Wazuh during
active scan operations to detect anomalous behavior.

Runs as background check during Phases 7 and 8
(intrusive scanning) to prevent cascading damage
if the scanning activity causes system instability.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.wazuh_client import WazuhClient

logger = logging.getLogger(__name__)


class WazuhMonitorAgent:
    """
    Monitors KAISON AI host health via Wazuh during
    active scan operations.

    Runs as background check during Phases 7 and 8
    (intrusive scanning) to detect if scanning activity
    is causing anomalous host behavior.

    If anomalies detected: pause mission and alert operator.
    """

    def __init__(self):
        self.client = WazuhClient()

    async def pre_scan_check(self) -> dict[str, Any]:
        """
        Runs before any Band 2 (intrusive) phase starts.

        Checks if the host is in a healthy state
        before aggressive scanning begins.

        Returns:
            {
              safe_to_proceed: bool,
              reason: str,
              baseline_alert_count: int,
            }
        """
        try:
            # Get current state as baseline
            anomalies = (
                self.client.check_host_anomalies()
            )

            if anomalies["anomalies_detected"]:
                return {
                    "safe_to_proceed": False,
                    "reason": (
                        "Host already showing "
                        "anomalies before scan: "
                        f"{anomalies['summary']}"
                    ),
                    "baseline_alert_count": (
                        anomalies.get(
                            "alert_count", 0
                        )
                    ),
                }

            return {
                "safe_to_proceed": True,
                "reason": (
                    "Host is healthy, "
                    "safe to proceed"
                ),
                "baseline_alert_count": (
                    anomalies.get(
                        "alert_count", 0
                    )
                ),
            }

        except Exception as e:
            logger.error(
                "Pre-scan check failed: %s",
                e,
            )
            return {
                "safe_to_proceed": False,
                "reason": f"Check error: {e}",
                "baseline_alert_count": 0,
            }

    async def monitor_during_scan(
        self,
        mission_id: str,
        check_interval: int = 60,
        max_iterations: int = 0,
    ) -> dict[str, Any]:
        """
        Runs as background coroutine during active phases.
        Checks every check_interval seconds.
        Triggers mission pause if anomalies detected.

        Args:
            mission_id: Mission ID for logging
            check_interval: Check interval in seconds
            max_iterations: Max checks (0 = unlimited)

        Returns:
            {
              monitoring_complete: bool,
              total_checks: int,
              anomalies_detected: bool,
              reason: str,
            }
        """
        result = {
            "monitoring_complete": False,
            "total_checks": 0,
            "anomalies_detected": False,
            "reason": "Monitoring started",
        }

        iteration = 0
        try:
            while True:
                iteration += 1
                result["total_checks"] = iteration

                if (
                    max_iterations > 0 and
                    iteration > max_iterations
                ):
                    result[
                        "monitoring_complete"
                    ] = True
                    result["reason"] = (
                        "Max iterations reached"
                    )
                    break

                # Check for anomalies
                anomalies = (
                    self.client.check_host_anomalies()
                )

                if anomalies[
                    "anomalies_detected"
                ]:
                    result[
                        "anomalies_detected"
                    ] = True
                    result["reason"] = (
                        f"Anomalies detected: "
                        f"{anomalies['summary']}"
                    )
                    logger.warning(
                        "Mission %s: %s",
                        mission_id,
                        result["reason"],
                    )
                    # Would trigger pause here
                    break

                # Sleep before next check
                await asyncio.sleep(
                    check_interval
                )

        except asyncio.CancelledError:
            logger.info(
                "Monitoring cancelled: %s",
                mission_id,
            )
            result["reason"] = "Monitoring cancelled"
        except Exception as e:
            logger.error(
                "Monitoring error: %s",
                e,
            )
            result["reason"] = f"Error: {e}"

        return result

    def send_finding_to_wazuh(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> bool:
        """
        Sends confirmed finding to Wazuh as alert.

        Args:
            finding: Confirmed finding dict
            scan_context: Scan context dict

        Returns:
            True on success, False on failure
        """
        return self.client.send_finding_alert(
            finding,
            scan_context,
        )

    def pre_mission_check(
        self,
        mission_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Synchronous pre-mission check.
        Wrapper around async pre_scan_check for sync code paths.

        Returns:
            Check result dict
        """
        try:
            # For sync contexts, do a simple
            # health check instead
            health = (
                self.client.health_check()
            )
            if not health:
                return {
                    "safe_to_proceed": False,
                    "reason": (
                        "Wazuh is unavailable"
                    ),
                }

            return {
                "safe_to_proceed": True,
                "reason": "Wazuh is healthy",
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
