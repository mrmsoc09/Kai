from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .secret_manager import get_secret_manager

logger = logging.getLogger(__name__)


class TheHiveClient:
    """
    TheHive case management client for KAISON AI.

    Handles case creation, observable attachment, task management,
    and alert creation for security findings.

    Credentials sourced from Vault only:
      THEHIVE_URL: http://localhost:9000
      THEHIVE_API_KEY: API key for authentication
    """

    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = (
            base_url or
            os.getenv(
                "THEHIVE_URL",
                "http://localhost:9000"
            )
        ).rstrip("/")
        self.api_key = (
            api_key or
            get_secret_manager().get_optional(
                "THEHIVE_API_KEY"
            ) or ""
        )
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            })

    def health_check(self) -> bool:
        """
        Checks if TheHive is reachable and responding.
        Returns True if healthy, False otherwise.
        """
        try:
            url = f"{self.base_url}/api/status"
            response = self.session.get(
                url,
                timeout=10,
            )
            return response.status_code < 400
        except Exception as e:
            logger.warning(
                "TheHive health check failed: %s",
                e,
            )
            return False

    def create_case_from_finding(
        self,
        finding: dict[str, Any],
        scan_id: str,
        program_name: str,
    ) -> str | None:
        """
        Creates a TheHive case from a platform finding.

        Args:
            finding: Finding dict with type, severity, value, target, etc.
            scan_id: KAISON AI scan ID for tracking
            program_name: Bug bounty program name

        Returns:
            case_id (str) or None on failure

        Severity mapping:
          critical → 3 (HIGH)
          high → 3 (HIGH)
          medium → 2 (MEDIUM)
          low → 1 (LOW)
        """
        severity_map = {
            "critical": 3,
            "high": 3,
            "medium": 2,
            "low": 1,
            "info": 0,
        }
        thehive_severity = severity_map.get(
            finding.get("severity", "info"), 0
        )

        url = f"{self.base_url}/api/v1/case"
        payload = {
            "title": finding.get(
                "value", "Unknown Finding"
            ),
            "description": (
                f"Target: {finding.get('target', 'N/A')}\n"
                f"Type: {finding.get('type', 'N/A')}\n"
                f"Severity: {finding.get('severity', 'unknown')}\n"
                f"Raw Evidence: {finding.get('raw_evidence', 'N/A')}"
            ),
            "severity": thehive_severity,
            "tags": [
                program_name,
                "KAISON-AI",
                finding.get("type", "unknown"),
            ],
            "customFields": {
                "kaison_scan_id": {"string": scan_id},
                "kaison_program": {
                    "string": program_name
                },
                "kaison_finding_type": {
                    "string": finding.get("type", "")
                },
            },
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )
            if response.status_code in (200, 201):
                data = response.json()
                case_id = data.get("id") or data.get(
                    "_id"
                )
                logger.info(
                    "Created TheHive case %s",
                    case_id,
                )
                return case_id
            else:
                logger.error(
                    "Case creation failed: %s %s",
                    response.status_code,
                    response.text[:200],
                )
                return None
        except Exception as e:
            logger.error(
                "TheHive case creation error: %s",
                e,
            )
            return None

    def add_observable(
        self,
        case_id: str,
        observable_type: str,
        value: str,
        tags: list[str] | None = None,
    ) -> bool:
        """
        Adds an observable to a TheHive case.

        Args:
            case_id: TheHive case ID
            observable_type: ip, domain, url, hash, filename
            value: Observable value
            tags: Optional tags for the observable

        Returns:
            True on success, False on failure
        """
        valid_types = (
            "ip", "domain", "url", "hash",
            "filename", "email", "user-agent"
        )
        if observable_type not in valid_types:
            logger.warning(
                "Invalid observable type: %s",
                observable_type,
            )
            return False

        url = (
            f"{self.base_url}/api/v1/case/"
            f"{case_id}/observables"
        )
        payload = {
            "dataType": observable_type,
            "data": value,
            "tags": tags or [],
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )
            if response.status_code in (200, 201):
                logger.info(
                    "Added observable %s:%s to case %s",
                    observable_type,
                    value[:30],
                    case_id,
                )
                return True
            else:
                logger.warning(
                    "Observable add failed: %s",
                    response.status_code,
                )
                return False
        except Exception as e:
            logger.error(
                "Observable add error: %s",
                e,
            )
            return False

    def create_task(
        self,
        case_id: str,
        title: str,
        description: str,
        assignee: str | None = None,
    ) -> str | None:
        """
        Creates a task within a TheHive case.

        Args:
            case_id: TheHive case ID
            title: Task title
            description: Task description
            assignee: Optional assignee username

        Returns:
            task_id or None on failure
        """
        url = (
            f"{self.base_url}/api/v1/case/"
            f"{case_id}/tasks"
        )
        payload = {
            "title": title,
            "description": description,
        }
        if assignee:
            payload["assignee"] = assignee

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )
            if response.status_code in (200, 201):
                data = response.json()
                task_id = data.get("id") or data.get(
                    "_id"
                )
                logger.info(
                    "Created task %s in case %s",
                    task_id,
                    case_id,
                )
                return task_id
            else:
                logger.warning(
                    "Task creation failed: %s",
                    response.status_code,
                )
                return None
        except Exception as e:
            logger.error(
                "Task creation error: %s",
                e,
            )
            return None

    def create_alert(
        self,
        title: str,
        description: str,
        severity: int,
        source: str,
        source_ref: str,
        observables: list[dict] | None = None,
    ) -> str | None:
        """
        Creates a TheHive alert for urgent findings.

        Args:
            title: Alert title
            description: Alert description
            severity: 0-3 (0=LOW, 3=HIGH)
            source: Alert source (e.g., "KAISON-AI")
            source_ref: Source reference ID
            observables: List of observable dicts

        Returns:
            alert_id or None on failure
        """
        url = f"{self.base_url}/api/v1/alert"
        payload = {
            "title": title,
            "description": description,
            "severity": max(0, min(3, severity)),
            "source": source,
            "sourceRef": source_ref,
            "observables": observables or [],
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )
            if response.status_code in (200, 201):
                data = response.json()
                alert_id = data.get("id") or data.get(
                    "_id"
                )
                logger.info(
                    "Created alert %s",
                    alert_id,
                )
                return alert_id
            else:
                logger.warning(
                    "Alert creation failed: %s",
                    response.status_code,
                )
                return None
        except Exception as e:
            logger.error(
                "Alert creation error: %s",
                e,
            )
            return None

    def close_case(
        self,
        case_id: str,
        status: str = "Resolved",
        summary: str = "",
    ) -> bool:
        """
        Closes a TheHive case.

        Args:
            case_id: TheHive case ID
            status: Case status (Resolved, Duplicated, etc.)
            summary: Closing summary

        Returns:
            True on success, False on failure
        """
        url = f"{self.base_url}/api/v1/case/{case_id}"
        payload = {
            "status": status,
            "summary": summary,
        }

        try:
            response = self.session.patch(
                url,
                json=payload,
                timeout=30,
            )
            if response.status_code < 400:
                logger.info(
                    "Closed case %s with status %s",
                    case_id,
                    status,
                )
                return True
            else:
                logger.warning(
                    "Case close failed: %s",
                    response.status_code,
                )
                return False
        except Exception as e:
            logger.error(
                "Case close error: %s",
                e,
            )
            return False

    def ensure_case(
        self,
        title: str,
        summary: str,
    ) -> str | None:
        """
        Backward compatibility wrapper for case creation.
        Kept for existing code paths.
        """
        url = f"{self.base_url}/api/v1/case"
        payload = {
            "title": title,
            "description": summary,
        }
        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )
            if response.status_code in (200, 201):
                data = response.json()
                return data.get("id") or data.get(
                    "_id"
                )
            else:
                logger.error(
                    "Case creation failed: %s %s",
                    response.status_code,
                    response.text[:200],
                )
                return None
        except Exception as e:
            logger.error(
                "ensure_case error: %s",
                e,
            )
            return None
