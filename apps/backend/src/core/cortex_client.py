"""
Cortex Analysis Engine Integration for KAISON AI.

Cortex is TheHive's integrated analysis engine. It runs
analyzers against observables to enrich findings with
threat intelligence automatically.

Credentials: CORTEX_URL, CORTEX_API_KEY via Vault.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .secret_manager import get_secret_manager

logger = logging.getLogger(__name__)


class CortexClient:
    """
    Cortex is TheHive's analysis engine.
    Runs analyzers against observables to enrich
    findings with threat intelligence.

    Supported analyzers by observable type:
      ip: VirusTotal, Shodan, AbuseIPDB
      domain: PassiveTotal, VirusTotal, URLScan
      url: URLScan, VirusTotal
      hash: VirusTotal, MalwareBazaar
    """

    def __init__(self, url: str = "", api_key: str = ""):
        self.url = (
            url or
            get_secret_manager().get_optional(
                "CORTEX_URL"
            ) or "http://localhost:9001"
        ).rstrip("/")
        self.api_key = (
            api_key or
            get_secret_manager().get_optional(
                "CORTEX_API_KEY"
            ) or ""
        )
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            })

    def health_check(self) -> bool:
        """
        Checks if Cortex is reachable and responding.
        Returns True if healthy, False otherwise.
        """
        try:
            url = f"{self.url}/api/status"
            response = self.session.get(
                url,
                timeout=10,
            )
            return response.status_code < 400
        except Exception as e:
            logger.warning(
                "Cortex health check failed: %s",
                e,
            )
            return False

    def list_analyzers(
        self,
        data_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lists available Cortex analyzers.

        Args:
            data_type: Optional filter by data type:
              ip, domain, url, hash, file

        Returns:
            List of analyzer dicts with id, name, version, etc.
        """
        try:
            url = f"{self.url}/api/analyzer"
            response = self.session.get(
                url,
                timeout=30,
            )
            if response.status_code < 400:
                analyzers = response.json()
                if data_type:
                    filtered = [
                        a for a in analyzers
                        if data_type in a.get(
                            "dataTypes", []
                        )
                    ]
                    return filtered
                return analyzers
            else:
                logger.warning(
                    "List analyzers failed: %s",
                    response.status_code,
                )
                return []
        except Exception as e:
            logger.error(
                "List analyzers error: %s",
                e,
            )
            return []

    def run_analyzer(
        self,
        analyzer_id: str,
        observable_type: str,
        observable_value: str,
        tlp: int = 2,
    ) -> str | None:
        """
        Runs a single Cortex analyzer against an observable.

        Args:
            analyzer_id: Analyzer ID (e.g., "VirusTotal_GetReport")
            observable_type: ip, domain, url, hash, file
            observable_value: The actual observable value
            tlp: Traffic Light Protocol (0=WHITE, 1=GREEN,
                 2=AMBER, 3=RED)

        Returns:
            job_id (str) or None on failure
        """
        url = f"{self.url}/api/job"
        payload = {
            "analyzerId": analyzer_id,
            "tlp": max(0, min(3, tlp)),
            "dataType": observable_type,
            "data": observable_value,
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )
            if response.status_code in (
                200, 201
            ):
                data = response.json()
                job_id = data.get("id") or data.get(
                    "_id"
                )
                logger.info(
                    "Started Cortex job %s",
                    job_id,
                )
                return job_id
            else:
                logger.warning(
                    "Analyzer run failed: %s",
                    response.status_code,
                )
                return None
        except Exception as e:
            logger.error(
                "Analyzer run error: %s",
                e,
            )
            return None

    def get_job_result(
        self,
        job_id: str,
        wait: bool = True,
        timeout: int = 60,
    ) -> dict[str, Any] | None:
        """
        Gets Cortex analyzer job result.

        Args:
            job_id: Job ID from run_analyzer
            wait: If True, poll until complete or timeout
            timeout: Poll timeout in seconds

        Returns:
            Result dict or None on failure/timeout
        """
        url = f"{self.url}/api/job/{job_id}"
        start_time = time.time()

        try:
            while True:
                response = self.session.get(
                    url,
                    timeout=30,
                )
                if response.status_code < 400:
                    data = response.json()
                    status = data.get("status")

                    # Job complete
                    if status in (
                        "Success", "Failure"
                    ):
                        logger.info(
                            "Job %s completed: %s",
                            job_id,
                            status,
                        )
                        return data

                    # Job still running
                    if wait:
                        elapsed = (
                            time.time() - start_time
                        )
                        if elapsed > timeout:
                            logger.warning(
                                "Job poll timeout: %s",
                                job_id,
                            )
                            return None
                        time.sleep(2)
                        continue
                    else:
                        return data
                else:
                    logger.warning(
                        "Get result failed: %s",
                        response.status_code,
                    )
                    return None

        except Exception as e:
            logger.error(
                "Get job result error: %s",
                e,
            )
            return None

    def analyze_observable(
        self,
        observable_type: str,
        value: str,
        preferred_analyzers: list[str] | None = None,
        wait: bool = True,
    ) -> list[dict[str, Any]]:
        """
        High-level method: runs appropriate analyzers
        for an observable type and returns enriched results.

        Args:
            observable_type: ip, domain, url, hash, file
            value: The observable value
            preferred_analyzers: Optional list of analyzer IDs
                                 to use (default: auto-select)
            wait: If True, wait for results

        Returns:
            List of result dicts from all analyzers
        """
        results = []

        # Auto-select analyzers by type
        if not preferred_analyzers:
            preferred_analyzers = (
                self._get_default_analyzers(
                    observable_type
                )
            )

        logger.info(
            "Analyzing %s:%s with %d analyzers",
            observable_type,
            value[:30],
            len(preferred_analyzers),
        )

        for analyzer_id in preferred_analyzers:
            job_id = self.run_analyzer(
                analyzer_id,
                observable_type,
                value,
            )
            if not job_id:
                continue

            if wait:
                result = self.get_job_result(
                    job_id,
                    wait=True,
                    timeout=60,
                )
                if result:
                    results.append(result)
            else:
                results.append({
                    "id": job_id,
                    "status": "Submitted",
                })

        return results

    def _get_default_analyzers(
        self,
        observable_type: str,
    ) -> list[str]:
        """
        Returns default analyzer list for observable type.
        """
        defaults = {
            "ip": [
                "VirusTotal_GetReport",
                "Shodan_DNSResolve",
                "AbuseIPDB",
            ],
            "domain": [
                "VirusTotal_GetReport",
                "PassiveTotal_Passive",
                "URLScan_GetReport",
            ],
            "url": [
                "URLScan_Submit",
                "VirusTotal_GetReport",
            ],
            "hash": [
                "VirusTotal_GetReport",
                "MalwareBazaar_Lookup",
            ],
        }
        return defaults.get(observable_type, [])
