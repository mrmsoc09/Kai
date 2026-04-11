"""
Base platform client abstraction for bug bounty platforms.
Defines interface and common functionality for HackerOne, Bugcrowd, Intigriti.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SubmissionPayload:
    """Standardized submission payload across platforms."""

    title: str
    description: str
    vulnerability_type: str
    cve_id: str
    target_url: str
    severity: str  # "critical", "high", "medium", "low"
    proof_of_concept: str
    impact_description: str
    affected_version: Optional[str] = None
    remediation: Optional[str] = None
    http_request: Optional[Dict[str, str]] = None
    http_response: Optional[Dict[str, str]] = None
    curl_command: Optional[str] = None
    screenshots: Optional[list[str]] = None  # Base64 encoded
    reference_links: Optional[list[str]] = None


@dataclass
class SubmissionResult:
    """Result of submission attempt."""

    success: bool
    platform_submission_id: Optional[str] = None
    submission_url: Optional[str] = None
    message: str = ""
    submitted_at: Optional[str] = None
    error_code: Optional[str] = None
    retry_after_seconds: Optional[int] = None


class BasePlatformClient(ABC):
    """Abstract base class for platform clients."""

    def __init__(self, api_key: str, api_url: str, timeout: int = 30):
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.session = None

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with platform API."""
        pass

    @abstractmethod
    async def submit_finding(self, payload: SubmissionPayload) -> SubmissionResult:
        """Submit vulnerability finding to platform."""
        pass

    @abstractmethod
    async def check_duplicate(self, target: str, cve_id: str) -> bool:
        """Check if CVE already submitted on target."""
        pass

    @abstractmethod
    async def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get status of submitted finding."""
        pass

    @abstractmethod
    async def list_programs(self) -> list[Dict[str, Any]]:
        """List available bug bounty programs."""
        pass

    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.aclose()

    @staticmethod
    def _get_severity_numeric(severity: str) -> int:
        """Convert severity string to numeric value."""
        severity_map = {
            "critical": 5,
            "high": 4,
            "medium": 3,
            "low": 2,
            "informational": 1,
        }
        return severity_map.get(severity.lower(), 0)

    @staticmethod
    def _is_duplicate_check_enabled() -> bool:
        """Check if duplicate detection is enabled."""
        import os

        return os.getenv("K1_ENABLE_DUPLICATE_CHECK", "true").lower() in {
            "1",
            "true",
            "yes",
        }

    @staticmethod
    def _get_current_timestamp() -> str:
        """Get current UTC timestamp."""
        return datetime.now(timezone.utc).isoformat()
