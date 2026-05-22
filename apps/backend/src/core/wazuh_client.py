"""
Wazuh SIEM Integration for KAISON AI.

Wazuh monitors the KAISON AI host during scan operations
for anomalous behavior. Also receives alerts when the
platform discovers vulnerabilities.

Credentials: WAZUH_URL, WAZUH_USERNAME, WAZUH_PASSWORD via Vault.
"""
from __future__ import annotations

import logging
import os
import urllib3
from typing import Any

import requests

from .secret_manager import get_secret_manager

logger = logging.getLogger(__name__)


class WazuhClient:
    """
    Wazuh SIEM integration for KAISON AI.

    Sends platform events to Wazuh for SIEM correlation.
    Receives host anomaly alerts during scan operations.

    Credentials: WAZUH_URL, WAZUH_USERNAME,
                 WAZUH_PASSWORD via Vault.
    """

    def __init__(
        self,
        url: str = "",
        username: str = "",
        password: str = "",
    ):
        self.url = (
            url or
            get_secret_manager().get_optional(
                "WAZUH_URL"
            ) or "https://localhost:55000"
        ).rstrip("/")
        self.username = (
            username or
            get_secret_manager().get_optional(
                "WAZUH_USERNAME"
            ) or "wazuh"
        )
        self.password = (
            password or
            get_secret_manager().get_optional(
                "WAZUH_PASSWORD"
            ) or ""
        )
        self._token = None
        self.session = requests.Session()
        
        # Environment-aware SSL verification
        cert_path = os.getenv("WAZUH_CA_CERT_PATH")
        if cert_path and os.path.exists(cert_path):
            self._verify_ssl = cert_path
        else:
            if os.getenv("ENVIRONMENT") == "production":
                raise ValueError("WAZUH_CA_CERT_PATH required in production")
            self._verify_ssl = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
        self.session.verify = self._verify_ssl

    def authenticate(self) -> bool:
        """
        Gets JWT token from Wazuh API.
        Returns True on success, False on failure.
        """
        if not self.username or not self.password:
            logger.warning(
                "Wazuh credentials not configured"
            )
            return False

        try:
            url = f"{self.url}/security/user/authenticate"
            response = requests.post(
                url,
                auth=(self.username, self.password),
                timeout=10,
                verify=self._verify_ssl,
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data.get("token")
                logger.info("Wazuh authenticated")
                if self._token:
                    self.session.headers.update({
                        "Authorization": (
                            f"Bearer {self._token}"
                        ),
                        "Content-Type": (
                            "application/json"
                        ),
                    })
                    return True
            else:
                logger.warning(
                    "Wazuh auth failed: %s",
                    response.status_code,
                )
                return False

        except Exception as e:
            logger.error(
                "Wazuh authentication error: %s",
                e,
            )
            return False

    def health_check(self) -> bool:
        """
        Returns True if Wazuh is reachable.
        """
        try:
            url = f"{self.url}/ping"
            response = requests.get(
                url,
                timeout=10,
                verify=self._verify_ssl,
            )
            return response.status_code < 400
        except Exception as e:
            logger.warning(
                "Wazuh health check failed: %s",
                e,
            )
            return False

    def send_alert(
        self,
        title: str,
        description: str,
        severity: int,
        source: str = "KAISON-AI",
        data: dict[str, Any] | None = None,
    ) -> bool:
        """
        Sends a custom alert to Wazuh.

        Args:
            title: Alert title
            description: Alert description
            severity: 1-15 (Wazuh scale)
              Critical finding → 12-15
              High finding → 9-11
              Medium finding → 6-8
              Low finding → 3-5
            source: Alert source
            data: Optional additional data

        Returns:
            True on success, False on failure
        """
        if not self._token:
            if not self.authenticate():
                logger.warning(
                    "Cannot send alert: "
                    "not authenticated"
                )
                return False

        url = f"{self.url}/events"
        payload = {
            "title": title,
            "description": description,
            "severity": max(1, min(15, severity)),
            "source": source,
        }
        if data:
            payload["data"] = data

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )
            return response.status_code < 400

        except Exception as e:
            logger.error(
                "Wazuh alert send error: %s",
                e,
            )
            return False

    def send_finding_alert(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> bool:
        """
        Converts a platform finding to a Wazuh alert.
        Maps platform severity to Wazuh severity scale.

        Args:
            finding: Finding dict with severity, value, etc.
            scan_context: Scan context dict

        Returns:
            True on success
        """
        severity_map = {
            "critical": 14,
            "high": 10,
            "medium": 7,
            "low": 4,
            "info": 2,
        }
        wazuh_severity = severity_map.get(
            finding.get("severity", "info"),
            2,
        )

        return self.send_alert(
            title=finding.get(
                "value", "KAISON Finding"
            ),
            description=(
                f"Target: {finding.get('target')}\n"
                f"Type: {finding.get('type')}\n"
                f"Severity: "
                f"{finding.get('severity')}"
            ),
            severity=wazuh_severity,
            source="KAISON-AI",
            data={
                "scan_id": scan_context.get(
                    "scan_id"
                ),
                "program": scan_context.get(
                    "program_name"
                ),
                "finding_type": finding.get(
                    "type"
                ),
            },
        )

    def get_recent_alerts(
        self,
        hours: int = 1,
        level_min: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Retrieves recent host alerts from Wazuh.
        Used to detect anomalous behavior on the
        KAISON AI host during scan operations.

        Args:
            hours: Look back N hours
            level_min: Minimum alert level

        Returns:
            List of alert dicts
        """
        if not self._token:
            if not self.authenticate():
                return []

        try:
            from datetime import (
                datetime,
                timedelta,
                timezone,
            )
            now = datetime.now(timezone.utc)
            start = now - timedelta(
                hours=hours
            )

            url = (
                f"{self.url}/alerts?"
                f"level={level_min}&"
                f"rule.level>={level_min}"
            )
            response = self.session.get(
                url,
                timeout=30,
            )

            if response.status_code < 400:
                data = response.json()
                return data.get("items", [])
            else:
                logger.warning(
                    "Get alerts failed: %s",
                    response.status_code,
                )
                return []

        except Exception as e:
            logger.error(
                "Get alerts error: %s",
                e,
            )
            return []

    def check_host_anomalies(self) -> dict[str, Any]:
        """
        Checks if Wazuh has detected anomalies
        on the KAISON AI host in the last hour.

        Returns:
            {
              anomalies_detected: bool,
              alert_count: int,
              highest_severity: int,
              summary: str,
            }
        """
        try:
            alerts = self.get_recent_alerts(
                hours=1,
                level_min=7,
            )

            if not alerts:
                return {
                    "anomalies_detected": False,
                    "alert_count": 0,
                    "highest_severity": 0,
                    "summary": "No anomalies detected",
                }

            highest_severity = max(
                (a.get("rule", {}).get("level", 0)
                 for a in alerts),
                default=0,
            )

            anomaly_rules = [
                a for a in alerts
                if any(
                    pattern in (
                        a.get("rule", {}).get(
                            "description", ""
                        ).lower()
                    )
                    for pattern in [
                        "anomal",
                        "attack",
                        "exploit",
                        "malicious",
                    ]
                )
            ]

            detected = len(anomaly_rules) > 0

            summary = (
                f"{len(alerts)} alerts, "
                f"{len(anomaly_rules)} anomalies, "
                f"max severity {highest_severity}"
            )

            logger.info(
                "Host anomaly check: %s",
                summary,
            )

            return {
                "anomalies_detected": detected,
                "alert_count": len(alerts),
                "highest_severity": (
                    highest_severity
                ),
                "summary": summary,
            }

        except Exception as e:
            logger.error(
                "Check anomalies error: %s",
                e,
            )
            return {
                "anomalies_detected": False,
                "alert_count": 0,
                "highest_severity": 0,
                "summary": f"Error: {e}",
            }
