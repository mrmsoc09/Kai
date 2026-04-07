"""
Intelligence Orchestrator for KAISON AI.

Coordinates all security operations integrations:
- TheHive: case management and collaboration
- Cortex: observable enrichment with threat intelligence
- Wazuh: host monitoring and anomaly detection
- Shuffle: automated incident response orchestration
- MSSP: centralized remote SIEM

The orchestrator maintains finding lifecycle across all systems,
tracks integration health, and provides unified status reporting.

All operations are fault-tolerant — failure of one integration
does not block subsequent processing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .hil_thehive_client import TheHiveClient
from .cortex_client import CortexClient
from .wazuh_client import WazuhClient
from .shuffle_client import ShuffleClient
from .mssp_client import MSPPClient

logger = logging.getLogger(__name__)


class IntelligenceOrchestrator:
    """
    Orchestrates all security operations integrations.

    Finding lifecycle:
    1. Finding confirmed (EvidenceAnalystAgent)
    2. TheHive case created + observables added
    3. Cortex enriches observables with threat intelligence
    4. Wazuh monitors host during scan operations
    5. Shuffle routes finding to automated response workflows
    6. MSSP receives alert for centralized monitoring

    Each step is fault-tolerant:
    - Failure of one integration does not block others
    - All integrations are optional (health check determines flow)
    - Results tracked for audit and reporting
    """

    def __init__(self):
        self.thehive = TheHiveClient()
        self.cortex = CortexClient()
        self.wazuh = WazuhClient()
        self.shuffle = ShuffleClient()
        self.mssp = MSPPClient()

        self.integration_status = {
            "thehive": {"healthy": False, "checked_at": None},
            "cortex": {"healthy": False, "checked_at": None},
            "wazuh": {"healthy": False, "checked_at": None},
            "shuffle": {"healthy": False, "checked_at": None},
            "mssp": {"healthy": False, "checked_at": None},
        }

    def health_check_all(self) -> dict[str, Any]:
        """
        Performs health checks on all integrations.

        Returns:
            {
              overall_healthy: bool,
              integrations: {
                thehive: bool,
                cortex: bool,
                wazuh: bool,
                shuffle: bool,
                mssp: bool,
              },
              checked_at: ISO timestamp,
            }
        """
        try:
            timestamp = (
                datetime.now(timezone.utc).isoformat()
            )

            # Check each integration
            self.integration_status["thehive"][
                "healthy"
            ] = self.thehive.health_check()

            self.integration_status["cortex"][
                "healthy"
            ] = self.cortex.health_check()

            self.integration_status["wazuh"][
                "healthy"
            ] = self.wazuh.health_check()

            self.integration_status["shuffle"][
                "healthy"
            ] = self.shuffle.health_check()

            self.integration_status["mssp"][
                "healthy"
            ] = self.mssp.health_check()

            # Update check times
            for integration in self.integration_status:
                self.integration_status[
                    integration
                ]["checked_at"] = timestamp

            overall = any(
                self.integration_status[i][
                    "healthy"
                ]
                for i in self.integration_status
            )

            logger.info(
                "Integration health check: %d/5 healthy",
                sum(
                    1
                    for i in self.integration_status
                    if self.integration_status[i][
                        "healthy"
                    ]
                ),
            )

            return {
                "overall_healthy": overall,
                "integrations": {
                    i: self.integration_status[i][
                        "healthy"
                    ]
                    for i in self.integration_status
                },
                "checked_at": timestamp,
            }

        except Exception as e:
            logger.error(
                "Health check failed: %s",
                e,
            )
            return {
                "overall_healthy": False,
                "integrations": {
                    i: False
                    for i in self.integration_status
                },
                "checked_at": None,
                "error": str(e),
            }

    def process_confirmed_finding(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Routes confirmed finding through all integrations.

        Processing order:
        1. TheHive: create case + observables
        2. Cortex: enrich observables (if available)
        3. Shuffle: route to incident response workflows
        4. Wazuh: log to host monitoring
        5. MSSP: send to centralized SIEM

        All failures are logged but do not block subsequent steps.

        Args:
            finding: Confirmed finding dict
            scan_context: Scan context dict

        Returns:
            {
              finding_id: str or None,
              thehive_case_id: str or None,
              cortex_enriched: bool,
              shuffle_routed: bool,
              wazuh_logged: bool,
              mssp_sent: bool,
              status: str,
              message: str,
            }
        """
        result = {
            "finding_id": finding.get(
                "id"
            ),
            "thehive_case_id": None,
            "cortex_enriched": False,
            "shuffle_routed": False,
            "wazuh_logged": False,
            "mssp_sent": False,
            "status": "processing",
            "message": "",
            "steps": [],
        }

        try:
            # Step 1: TheHive case creation
            if self.integration_status[
                "thehive"
            ]["healthy"]:
                try:
                    case_id = (
                        self.thehive.create_case_from_finding(
                            finding,
                            scan_context,
                        )
                    )
                    result["thehive_case_id"] = (
                        case_id
                    )
                    result["steps"].append(
                        "thehive_case_created"
                    )
                    logger.info(
                        "TheHive case created: %s",
                        case_id,
                    )

                    # Add observables
                    if case_id:
                        target = finding.get(
                            "target"
                        )
                        if target:
                            self.thehive.add_observable(
                                case_id,
                                target,
                                "domain",
                            )

                except Exception as e:
                    logger.error(
                        "TheHive processing failed: %s",
                        e,
                    )
                    result["steps"].append(
                        "thehive_case_failed"
                    )

            # Step 2: Cortex enrichment (if case created)
            if result["thehive_case_id"] and (
                self.integration_status["cortex"][
                    "healthy"
                ]
            ):
                try:
                    observables = [
                        {
                            "dataType": "domain",
                            "data": finding.get(
                                "target"
                            ),
                        }
                    ]
                    enrichment = (
                        self.cortex.analyze_observable(
                            "domain",
                            finding.get(
                                "target"
                            ),
                        )
                    )
                    if enrichment:
                        result[
                            "cortex_enriched"
                        ] = True
                        result["steps"].append(
                            "cortex_enriched"
                        )
                        logger.info(
                            "Cortex enrichment complete"
                        )

                except Exception as e:
                    logger.warning(
                        "Cortex enrichment failed: %s",
                        e,
                    )

            # Step 3: Shuffle routing
            if self.integration_status[
                "shuffle"
            ]["healthy"]:
                try:
                    success = (
                        self.shuffle.trigger_critical_finding_workflow(
                            finding,
                            scan_context,
                        )
                        if finding.get(
                            "severity"
                        ) == "critical"
                        else True
                    )
                    if success:
                        result["shuffle_routed"] = (
                            True
                        )
                        result["steps"].append(
                            "shuffle_routed"
                        )

                except Exception as e:
                    logger.warning(
                        "Shuffle routing failed: %s",
                        e,
                    )

            # Step 4: Wazuh logging
            if self.integration_status[
                "wazuh"
            ]["healthy"]:
                try:
                    success = (
                        self.wazuh.send_finding_alert(
                            finding,
                            scan_context,
                        )
                    )
                    if success:
                        result["wazuh_logged"] = (
                            True
                        )
                        result["steps"].append(
                            "wazuh_logged"
                        )

                except Exception as e:
                    logger.warning(
                        "Wazuh logging failed: %s",
                        e,
                    )

            # Step 5: MSSP notification
            if self.integration_status[
                "mssp"
            ]["healthy"]:
                try:
                    success = (
                        self.mssp.send_finding_to_mssp(
                            finding,
                            scan_context,
                        )
                    )
                    if success:
                        result["mssp_sent"] = True
                        result["steps"].append(
                            "mssp_sent"
                        )

                except Exception as e:
                    logger.warning(
                        "MSSP notification failed: %s",
                        e,
                    )

            result["status"] = "completed"
            result["message"] = (
                f"Finding processed through "
                f"{len(result['steps'])} integrations"
            )

            logger.info(
                "Finding orchestration complete: "
                "finding_id=%s, case_id=%s, "
                "steps=%d",
                result["finding_id"],
                result["thehive_case_id"],
                len(result["steps"]),
            )

            return result

        except Exception as e:
            logger.error(
                "Finding orchestration failed: %s",
                e,
            )
            result["status"] = "failed"
            result["message"] = str(e)
            return result

    def process_host_anomaly(
        self,
        anomaly_data: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Routes host anomaly detection through integrations.

        Anomalies trigger:
        - Wazuh alert escalation
        - Shuffle containment workflow
        - MSSP emergency notification

        Args:
            anomaly_data: Anomaly dict from Wazuh
            scan_context: Scan context dict

        Returns:
            {
              anomalies_detected: bool,
              shuffle_notified: bool,
              mssp_notified: bool,
              status: str,
            }
        """
        result = {
            "anomalies_detected": anomaly_data.get(
                "anomalies_detected", False
            ),
            "shuffle_notified": False,
            "mssp_notified": False,
            "status": "processing",
        }

        try:
            if not result["anomalies_detected"]:
                result["status"] = "no_anomalies"
                return result

            # Notify Shuffle
            if self.integration_status[
                "shuffle"
            ]["healthy"]:
                try:
                    success = (
                        self.shuffle.trigger_host_anomaly_workflow(
                            anomaly_data,
                            scan_context,
                        )
                    )
                    result[
                        "shuffle_notified"
                    ] = success

                except Exception as e:
                    logger.error(
                        "Shuffle anomaly workflow failed: %s",
                        e,
                    )

            # Notify MSSP
            if self.integration_status[
                "mssp"
            ]["healthy"]:
                try:
                    success = (
                        self.mssp.send_alert_to_mssp(
                            "host_anomaly",
                            "high",
                            anomaly_data.get(
                                "summary",
                                "Host anomaly detected",
                            ),
                            anomaly_data,
                        )
                    )
                    result["mssp_notified"] = (
                        success
                    )

                except Exception as e:
                    logger.error(
                        "MSSP anomaly notification failed: %s",
                        e,
                    )

            result["status"] = "completed"
            logger.warning(
                "Anomaly orchestration complete: "
                "detected=%s, shuffle=%s, mssp=%s",
                result["anomalies_detected"],
                result["shuffle_notified"],
                result["mssp_notified"],
            )

            return result

        except Exception as e:
            logger.error(
                "Anomaly orchestration failed: %s",
                e,
            )
            result["status"] = "failed"
            return result

    def get_integration_status(
        self,
    ) -> dict[str, Any]:
        """
        Returns current integration status.

        Returns:
            {
              thehive: {healthy, checked_at},
              cortex: {healthy, checked_at},
              wazuh: {healthy, checked_at},
              shuffle: {healthy, checked_at},
              mssp: {healthy, checked_at},
              overall_healthy: bool,
            }
        """
        return {
            **self.integration_status,
            "overall_healthy": any(
                self.integration_status[i][
                    "healthy"
                ]
                for i in self.integration_status
            ),
        }
