"""
TheHive Handoff Agent for KAISON AI.

Receives confirmed findings and automatically creates corresponding
TheHive cases, observables, and investigation tasks.

Runs after EvidenceAnalystAgent validation in the intelligence chain.
"""
from __future__ import annotations

import logging
from typing import Any

from core.hil_thehive_client import TheHiveClient

logger = logging.getLogger(__name__)


class TheHiveHandoffAgent:
    """
    Receives confirmed findings from EvidenceAnalyst
    and creates corresponding TheHive cases,
    observables, and tasks automatically.

    Runs after EvidenceAnalystAgent in the pipeline.
    All operations are fault-tolerant — failure of one
    step does not block subsequent steps.
    """

    def __init__(self):
        self.client = TheHiveClient()

    def process_confirmed_finding(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Creates TheHive case, adds observables,
        creates investigation tasks.

        Args:
            finding: Confirmed finding dict with:
              - type: vulnerability type
              - severity: critical/high/medium/low
              - value: finding title/value
              - target: affected resource
              - raw_evidence: evidence details
              - confidence: confidence score
            scan_context: Scan context with:
              - scan_id: KAISON scan ID
              - mission_id: Mission ID
              - program_name: Bug bounty program

        Returns:
            {
              case_id: str or None,
              observables_added: int,
              tasks_created: int,
              alerts_created: int,
              success: bool,
            }
        """
        case_id = None
        observables_added = 0
        tasks_created = 0
        alerts_created = 0

        try:
            # Create case from finding
            case_id = self._create_case(
                finding,
                scan_context,
            )
            if not case_id:
                logger.error(
                    "Failed to create TheHive case"
                )
                return {
                    "case_id": None,
                    "observables_added": 0,
                    "tasks_created": 0,
                    "alerts_created": 0,
                    "success": False,
                }

            # Add observables extracted from finding
            observables_added = self._add_observables(
                case_id,
                finding,
            )

            # Create investigation tasks
            tasks_created = self._create_tasks(
                case_id,
                finding,
            )

            # Create alert if critical severity
            if finding.get("severity") == "critical":
                if self._create_alert(
                    case_id,
                    finding,
                    scan_context,
                ):
                    alerts_created = 1

            logger.info(
                "TheHive handoff complete: case=%s, "
                "observables=%d, tasks=%d",
                case_id,
                observables_added,
                tasks_created,
            )

            return {
                "case_id": case_id,
                "observables_added": observables_added,
                "tasks_created": tasks_created,
                "alerts_created": alerts_created,
                "success": True,
            }

        except Exception as e:
            logger.error(
                "TheHive handoff failed: %s",
                e,
            )
            return {
                "case_id": case_id,
                "observables_added": observables_added,
                "tasks_created": tasks_created,
                "alerts_created": alerts_created,
                "success": False,
            }

    def process_critical_finding(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Critical findings get immediate alert first
        for operator attention, then full case.

        Args:
            finding: Critical finding dict
            scan_context: Scan context dict

        Returns:
            Combined result from alert and case creation
        """
        result = {
            "alert_id": None,
            "case_id": None,
            "success": False,
        }

        try:
            # Create immediate alert for critical findings
            alert_id = self.client.create_alert(
                title=(
                    f"CRITICAL: {finding.get('value')}"
                ),
                description=(
                    f"Target: {finding.get('target')}\n"
                    f"Type: {finding.get('type')}\n"
                    f"Evidence: {finding.get('raw_evidence')}"
                ),
                severity=3,
                source="KAISON-AI",
                source_ref=(
                    f"{scan_context.get('scan_id')}"
                ),
                observables=[],
            )

            result["alert_id"] = alert_id

            # Then create full case
            case_result = (
                self.process_confirmed_finding(
                    finding,
                    scan_context,
                )
            )
            result["case_id"] = case_result.get(
                "case_id"
            )
            result["success"] = (
                alert_id is not None and
                case_result.get("success")
            )

            return result

        except Exception as e:
            logger.error(
                "Critical finding handoff failed: %s",
                e,
            )
            return result

    def _create_case(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> str | None:
        """Creates TheHive case from finding."""
        return self.client.create_case_from_finding(
            finding,
            scan_context.get("scan_id", ""),
            scan_context.get("program_name", ""),
        )

    def _add_observables(
        self,
        case_id: str,
        finding: dict[str, Any],
    ) -> int:
        """
        Extracts observables from finding and
        adds them to the case.
        """
        count = 0

        # Add target as observable if it looks like
        # an IP or domain
        target = finding.get("target", "")
        if target:
            obs_type = (
                "ip" if _is_ip(target)
                else "domain"
            )
            if self.client.add_observable(
                case_id,
                obs_type,
                target,
                tags=["target"],
            ):
                count += 1

        # Add URLs if present
        urls = finding.get("urls", [])
        if isinstance(urls, list):
            for url in urls:
                if self.client.add_observable(
                    case_id,
                    "url",
                    url,
                    tags=["evidence"],
                ):
                    count += 1

        # Add hashes if present
        hashes = finding.get("hashes", [])
        if isinstance(hashes, list):
            for h in hashes:
                if self.client.add_observable(
                    case_id,
                    "hash",
                    h,
                    tags=["evidence"],
                ):
                    count += 1

        return count

    def _create_tasks(
        self,
        case_id: str,
        finding: dict[str, Any],
    ) -> int:
        """
        Creates investigation tasks for the case.
        """
        count = 0

        # Create analysis task
        if self.client.create_task(
            case_id,
            "Analyze Finding",
            (
                f"Analyze and verify the finding: "
                f"{finding.get('value', 'Unknown')}"
            ),
        ):
            count += 1

        # Create remediation task for high severity
        if finding.get("severity") in (
            "critical", "high"
        ):
            if self.client.create_task(
                case_id,
                "Remediation",
                (
                    f"Plan and execute remediation "
                    f"for {finding.get('type', 'finding')}"
                ),
            ):
                count += 1

        # Create verification task
        if self.client.create_task(
            case_id,
            "Verify Fix",
            (
                f"Verify that the finding has been "
                f"remediated"
            ),
        ):
            count += 1

        return count

    def _create_alert(
        self,
        case_id: str,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> bool:
        """Creates an alert within the case."""
        obs = []
        target = finding.get("target", "")
        if target:
            obs.append({
                "dataType": (
                    "ip" if _is_ip(target)
                    else "domain"
                ),
                "data": target,
            })

        return (
            self.client.create_alert(
                title=(
                    f"CRITICAL: {finding.get('value')}"
                ),
                description=(
                    f"Critical finding in case {case_id}"
                ),
                severity=3,
                source="KAISON-AI",
                source_ref=(
                    f"{scan_context.get('scan_id')}"
                ),
                observables=obs,
            ) is not None
        )


def _is_ip(value: str) -> bool:
    """Simple IP address check."""
    try:
        parts = value.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit():
                return False
            n = int(part)
            if n < 0 or n > 255:
                return False
        return True
    except Exception:
        return False
