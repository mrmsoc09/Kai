"""
Cortex Enrichment Agent for KAISON AI.

Enriches TheHive observables with Cortex analyzer results
to provide threat intelligence context and assess true risk.

Runs automatically after TheHive case creation.
"""
from __future__ import annotations

import logging
from typing import Any

from core.cortex_client import CortexClient

logger = logging.getLogger(__name__)


class CortexEnrichmentAgent:
    """
    Enriches TheHive observables with Cortex analysis.
    Runs automatically after TheHive case creation.

    For each observable in a case:
      1. Runs appropriate Cortex analyzers
      2. Attaches results to TheHive case
      3. Updates finding confidence based on results
      4. Escalates severity if threat intel confirms
         active exploitation
    """

    def __init__(self):
        self.client = CortexClient()

    def enrich_case_observables(
        self,
        observables: list[dict[str, Any]],
        thehive_case_id: str = "",
    ) -> dict[str, Any]:
        """
        Runs Cortex analyzers on observables.

        Args:
            observables: List of observable dicts with:
              - dataType: ip, domain, url, hash
              - data: observable value
            thehive_case_id: Optional TheHive case ID
                            for context logging

        Returns:
            Enrichment summary:
              {
                observables_analyzed: int,
                results_found: int,
                threat_confirmed: bool,
                highest_risk_observable: str,
                analyzer_results: list[dict],
              }
        """
        summary = {
            "observables_analyzed": 0,
            "results_found": 0,
            "threat_confirmed": False,
            "highest_risk_observable": None,
            "analyzer_results": [],
            "threat_indicators": [],
        }

        try:
            for observable in observables:
                obs_type = observable.get(
                    "dataType", ""
                )
                obs_value = observable.get(
                    "data", ""
                )

                if not obs_type or not obs_value:
                    continue

                summary[
                    "observables_analyzed"
                ] += 1

                # Run analyzers
                results = (
                    self.client.analyze_observable(
                        obs_type,
                        obs_value,
                        wait=True,
                    )
                )

                for result in results:
                    summary[
                        "analyzer_results"
                    ].append({
                        "observable": obs_value,
                        "type": obs_type,
                        "result": result,
                    })

                    summary[
                        "results_found"
                    ] += 1

                    # Check for threat indicators
                    if self._has_threat_indicator(
                        result
                    ):
                        summary[
                            "threat_confirmed"
                        ] = True
                        summary[
                            "highest_risk_observable"
                        ] = obs_value
                        summary[
                            "threat_indicators"
                        ].append({
                            "observable": obs_value,
                            "indicator": result,
                        })

            logger.info(
                "Cortex enrichment complete: "
                "%d observables, %d results, "
                "threat=%s",
                summary[
                    "observables_analyzed"
                ],
                summary["results_found"],
                summary["threat_confirmed"],
            )

            return summary

        except Exception as e:
            logger.error(
                "Cortex enrichment failed: %s",
                e,
            )
            return summary

    def assess_threat_context(
        self,
        cortex_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Interprets Cortex analyzer results and assesses threat.

        Args:
            cortex_results: List of analyzer result dicts

        Returns:
            {
              threat_confirmed: bool,
              confidence_delta: float (-1 to 1),
              severity_escalation: str or None,
              threat_intel_summary: str,
              indicators_count: int,
            }
        """
        assessment = {
            "threat_confirmed": False,
            "confidence_delta": 0.0,
            "severity_escalation": None,
            "threat_intel_summary": "",
            "indicators_count": 0,
        }

        try:
            threat_count = 0
            indicators = []

            for result in cortex_results:
                status = result.get(
                    "status"
                )
                if status != "Success":
                    continue

                # Check for threat indicators in result
                full_report = result.get(
                    "report", {}
                )
                summary = full_report.get(
                    "summary", {}
                )

                # VirusTotal: check harmless vs malicious
                if "malicious" in summary:
                    malicious = summary.get(
                        "malicious", 0
                    )
                    if malicious > 0:
                        threat_count += 1
                        indicators.append(
                            f"VirusTotal: {malicious} "
                            f"detections"
                        )

                # URLScan: check verdict
                if "verdict" in summary:
                    verdict = summary.get(
                        "verdict"
                    )
                    if verdict in (
                        "malicious",
                        "suspicious",
                    ):
                        threat_count += 1
                        indicators.append(
                            f"URLScan: {verdict}"
                        )

                # Shodan: check for interesting ports
                if "ports" in summary:
                    ports = summary.get(
                        "ports", []
                    )
                    if len(ports) > 5:
                        indicators.append(
                            f"Shodan: {len(ports)} "
                            f"open ports"
                        )

            # Assess based on threat count
            assessment[
                "indicators_count"
            ] = len(indicators)

            if threat_count > 0:
                assessment[
                    "threat_confirmed"
                ] = True
                assessment[
                    "confidence_delta"
                ] = min(
                    0.5,
                    threat_count * 0.25,
                )

                if threat_count >= 3:
                    assessment[
                        "severity_escalation"
                    ] = "high"
                elif threat_count >= 2:
                    assessment[
                        "severity_escalation"
                    ] = "medium"
                elif threat_count == 1:
                    assessment[
                        "severity_escalation"
                    ] = "low"

            assessment[
                "threat_intel_summary"
            ] = (
                "; ".join(indicators)
                if indicators
                else "No threats detected"
            )

            logger.info(
                "Threat assessment: confirmed=%s, "
                "escalation=%s, indicators=%d",
                assessment[
                    "threat_confirmed"
                ],
                assessment[
                    "severity_escalation"
                ],
                assessment["indicators_count"],
            )

            return assessment

        except Exception as e:
            logger.error(
                "Threat assessment failed: %s",
                e,
            )
            return assessment

    def _has_threat_indicator(
        self,
        result: dict[str, Any],
    ) -> bool:
        """
        Checks if analyzer result contains threat indicators.
        """
        try:
            status = result.get("status")
            if status != "Success":
                return False

            report = result.get("report", {})
            summary = report.get("summary", {})

            # VirusTotal detection
            if summary.get("malicious", 0) > 0:
                return True

            # URLScan verdict
            verdict = summary.get("verdict")
            if verdict in (
                "malicious",
                "suspicious",
            ):
                return True

            # Shodan: suspicious ports
            ports = summary.get("ports", [])
            if len(ports) > 10:
                return True

            return False

        except Exception:
            return False
