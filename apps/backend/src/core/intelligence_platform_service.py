"""
Intelligence Platform Service for KAISON AI.

Orchestrates the five intelligence platforms at mission lifecycle points:

  Wazuh  — SIEM host monitoring (mission start / anomaly checks)
  MISP   — Threat intel IOC enrichment (pre-phase / finding enrichment)
  Cortex — Observable analysis (finding discovery)
  TheHive — Case management (finding → case, mission → case set)
  Shuffle — SOAR automation (critical finding escalation, mission complete)

Usage:
  svc = IntelligencePlatformService()
  await svc.on_mission_start(mission_id, program_name, targets)
  enriched = await svc.on_finding_discovered(finding, scan_context)
  await svc.on_mission_complete(mission_id, scan_context, stats)
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports — each client is only instantiated when first used,
# so missing credentials degrade gracefully rather than hard-failing.

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="intel-svc")


def _run_sync(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a synchronous callable in the shared thread pool."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))


class IntelligencePlatformService:
    """
    Lifecycle coordinator for KAISON's intelligence platforms.

    All network calls are delegated to the typed clients; this service
    only decides *when* and *which* calls to make at each lifecycle point.
    """

    def __init__(self) -> None:
        self._wazuh: Any = None
        self._misp: Any = None
        self._cortex: Any = None
        self._thehive: Any = None
        self._shuffle: Any = None

    # ------------------------------------------------------------------
    # Lazy client accessors
    # ------------------------------------------------------------------

    def _get_wazuh(self) -> Any:
        if self._wazuh is None:
            from .wazuh_client import WazuhClient
            self._wazuh = WazuhClient()
        return self._wazuh

    def _get_misp(self) -> Any:
        if self._misp is None:
            from .misp_client import MISPClient
            self._misp = MISPClient()
        return self._misp

    def _get_cortex(self) -> Any:
        if self._cortex is None:
            from .cortex_client import CortexClient
            self._cortex = CortexClient()
        return self._cortex

    def _get_thehive(self) -> Any:
        if self._thehive is None:
            from .hil_thehive_client import TheHiveClient
            self._thehive = TheHiveClient()
        return self._thehive

    def _get_shuffle(self) -> Any:
        if self._shuffle is None:
            from .shuffle_client import ShuffleClient
            self._shuffle = ShuffleClient()
        return self._shuffle

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def on_mission_start(
        self,
        mission_id: str,
        program_name: str,
        targets: list[str],
    ) -> dict[str, Any]:
        """
        Called when a mission begins.

        Actions:
        - Wazuh: verify host health / auth
        - TheHive: create a mission-level tracking case
        """
        results: dict[str, Any] = {
            "mission_id": mission_id,
            "program_name": program_name,
        }

        # Wazuh — ensure auth is established before scan
        try:
            wazuh = self._get_wazuh()
            healthy = await asyncio.get_event_loop().run_in_executor(
                _executor, wazuh.health_check
            )
            results["wazuh_healthy"] = healthy
            if healthy:
                await asyncio.get_event_loop().run_in_executor(
                    _executor, wazuh.authenticate
                )
                logger.info("Wazuh authenticated for mission %s", mission_id)
        except Exception as exc:
            logger.warning("Wazuh on_mission_start error: %s", exc)
            results["wazuh_healthy"] = False

        # TheHive — create mission case
        try:
            thehive = self._get_thehive()
            healthy = await asyncio.get_event_loop().run_in_executor(
                _executor, thehive.health_check
            )
            results["thehive_healthy"] = healthy
            if healthy:
                mission_finding = {
                    "value": f"Mission: {mission_id}",
                    "target": ", ".join(targets[:5]),
                    "type": "mission_start",
                    "severity": "info",
                }
                case_id = await asyncio.get_event_loop().run_in_executor(
                    _executor,
                    thehive.create_case_from_finding,
                    mission_finding,
                    mission_id,
                    program_name,
                )
                results["thehive_mission_case_id"] = case_id
                logger.info("TheHive case %s created for mission %s", case_id, mission_id)
        except Exception as exc:
            logger.warning("TheHive on_mission_start error: %s", exc)
            results["thehive_healthy"] = False

        return results

    async def on_pre_phase(
        self,
        phase: str,
        targets: list[str],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Called before each scan phase.

        Actions:
        - MISP: pre-enrich known targets as IOCs (identifies known-bad targets)
        - Wazuh: check host anomalies before phase begins
        """
        results: dict[str, Any] = {"phase": phase, "targets_checked": len(targets)}
        ioc_hits: list[dict[str, Any]] = []
        blocked_targets: list[str] = []

        # MISP enrichment
        try:
            misp = self._get_misp()
            if misp.health_check():
                for target in targets[:10]:  # cap to avoid excessive queries
                    ioc_type = _guess_ioc_type(target)
                    enrichment = await asyncio.get_event_loop().run_in_executor(
                        _executor, misp.enrich_ioc, ioc_type, target
                    )
                    if enrichment.get("known_malicious"):
                        ioc_hits.append(enrichment)
                        logger.warning(
                            "MISP: target %s has %d attribute hits — known malicious IOC",
                            target,
                            enrichment.get("attribute_hits", 0),
                        )
        except Exception as exc:
            logger.warning("MISP on_pre_phase error: %s", exc)

        # Wazuh host anomaly check
        anomaly_check: dict[str, Any] = {}
        try:
            wazuh = self._get_wazuh()
            if wazuh.health_check():
                anomaly_check = await asyncio.get_event_loop().run_in_executor(
                    _executor, wazuh.check_host_anomalies
                )
                if anomaly_check.get("anomalies_detected"):
                    logger.warning(
                        "Wazuh: host anomalies detected before phase %s: %s",
                        phase,
                        anomaly_check.get("summary"),
                    )
                    # Trigger Shuffle alert if anomalies found
                    try:
                        shuffle = self._get_shuffle()
                        await asyncio.get_event_loop().run_in_executor(
                            _executor,
                            shuffle.trigger_host_anomaly_workflow,
                            anomaly_check,
                            scan_context,
                        )
                    except Exception as exc2:
                        logger.warning("Shuffle anomaly trigger error: %s", exc2)
        except Exception as exc:
            logger.warning("Wazuh on_pre_phase error: %s", exc)

        results["misp_ioc_hits"] = ioc_hits
        results["blocked_targets"] = blocked_targets
        results["wazuh_anomaly_check"] = anomaly_check
        return results

    async def on_finding_discovered(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Called when a new finding is confirmed.

        Actions:
        - Cortex: run analyzers on the finding's observable
        - MISP: enrich finding IOC
        - TheHive: create case for high/critical findings
        - Shuffle: trigger critical finding workflow if critical/high
        - Wazuh: send finding alert to SIEM
        """
        results: dict[str, Any] = {
            "finding_type": finding.get("finding_type") or finding.get("type"),
            "severity": finding.get("severity", "info"),
        }
        target = str(finding.get("target") or finding.get("value") or "")
        severity = str(finding.get("severity", "info")).lower()

        # Cortex analysis
        try:
            cortex = self._get_cortex()
            if cortex.health_check() and target:
                ioc_type = _guess_ioc_type(target)
                cortex_results = await asyncio.get_event_loop().run_in_executor(
                    _executor,
                    cortex.analyze_observable,
                    ioc_type,
                    target,
                    None,
                    False,  # don't wait — async jobs
                )
                results["cortex_jobs"] = len(cortex_results)
                logger.info("Cortex: %d analyzer jobs started for %s", len(cortex_results), target)
        except Exception as exc:
            logger.warning("Cortex on_finding_discovered error: %s", exc)

        # MISP enrichment
        try:
            misp = self._get_misp()
            if misp.health_check() and target:
                ioc_type = _guess_ioc_type(target)
                enrichment = await asyncio.get_event_loop().run_in_executor(
                    _executor, misp.enrich_ioc, ioc_type, target
                )
                results["misp_enrichment"] = enrichment
                finding["misp_known_malicious"] = enrichment.get("known_malicious", False)
                finding["misp_attribute_hits"] = enrichment.get("attribute_hits", 0)
        except Exception as exc:
            logger.warning("MISP on_finding_discovered error: %s", exc)

        # TheHive case creation for high/critical
        if severity in ("high", "critical"):
            try:
                thehive = self._get_thehive()
                if thehive.health_check():
                    case_id = await asyncio.get_event_loop().run_in_executor(
                        _executor,
                        thehive.create_case_from_finding,
                        finding,
                        scan_context.get("scan_id", ""),
                        scan_context.get("program_name", ""),
                    )
                    results["thehive_case_id"] = case_id
                    finding["thehive_case_id"] = case_id
                    logger.info("TheHive case %s created for %s finding", case_id, severity)
            except Exception as exc:
                logger.warning("TheHive on_finding_discovered error: %s", exc)

            # Shuffle critical escalation
            try:
                shuffle = self._get_shuffle()
                triggered = await asyncio.get_event_loop().run_in_executor(
                    _executor,
                    shuffle.trigger_critical_finding_workflow,
                    finding,
                    scan_context,
                )
                results["shuffle_triggered"] = triggered
            except Exception as exc:
                logger.warning("Shuffle on_finding_discovered error: %s", exc)

        # Wazuh finding alert
        try:
            wazuh = self._get_wazuh()
            if wazuh.health_check():
                await asyncio.get_event_loop().run_in_executor(
                    _executor,
                    wazuh.send_finding_alert,
                    finding,
                    scan_context,
                )
        except Exception as exc:
            logger.warning("Wazuh on_finding_discovered error: %s", exc)

        return results

    async def on_mission_complete(
        self,
        mission_id: str,
        scan_context: dict[str, Any],
        statistics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Called when a mission finishes (success or failure).

        Actions:
        - Shuffle: trigger mission_complete workflow
        - Wazuh: final host anomaly check
        """
        results: dict[str, Any] = {"mission_id": mission_id}

        try:
            shuffle = self._get_shuffle()
            triggered = await asyncio.get_event_loop().run_in_executor(
                _executor,
                shuffle.trigger_mission_complete_workflow,
                mission_id,
                scan_context,
                statistics,
            )
            results["shuffle_mission_complete"] = triggered
        except Exception as exc:
            logger.warning("Shuffle on_mission_complete error: %s", exc)

        try:
            wazuh = self._get_wazuh()
            if wazuh.health_check():
                anomaly_check = await asyncio.get_event_loop().run_in_executor(
                    _executor, wazuh.check_host_anomalies
                )
                results["wazuh_final_anomaly_check"] = anomaly_check
        except Exception as exc:
            logger.warning("Wazuh on_mission_complete error: %s", exc)

        return results

    async def on_approval_requested(
        self,
        finding: dict[str, Any],
        reason: str,
        scan_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Called when a Band 2 finding requires human approval.

        Actions:
        - Shuffle: trigger approval_required workflow (notifies review team)
        """
        results: dict[str, Any] = {"reason": reason}
        try:
            shuffle = self._get_shuffle()
            triggered = await asyncio.get_event_loop().run_in_executor(
                _executor,
                shuffle.trigger_approval_required_workflow,
                finding,
                reason,
                scan_context,
            )
            results["shuffle_triggered"] = triggered
        except Exception as exc:
            logger.warning("Shuffle on_approval_requested error: %s", exc)
        return results


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_intel_svc: IntelligencePlatformService | None = None


def get_intelligence_service() -> IntelligencePlatformService:
    """Return module-level IntelligencePlatformService singleton."""
    global _intel_svc
    if _intel_svc is None:
        _intel_svc = IntelligencePlatformService()
    return _intel_svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _guess_ioc_type(value: str) -> str:
    """Heuristically classify a value as ip/domain/url/hash."""
    if not value:
        return "domain"
    if value.startswith("http://") or value.startswith("https://"):
        return "url"
    # IPv4
    parts = value.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return "ip"
    # Hash (md5/sha1/sha256 length heuristic)
    if all(c in "0123456789abcdefABCDEF" for c in value) and len(value) in (32, 40, 64):
        return "hash"
    return "domain"
