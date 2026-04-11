"""
Bugcrowd platform client implementation.
Uses Bugcrowd REST API for submission and duplicate checking.
"""

from __future__ import annotations

import logging
import httpx
from typing import Any, Dict, Optional
from .base_platform_client import (
    BasePlatformClient,
    SubmissionPayload,
    SubmissionResult,
)

logger = logging.getLogger(__name__)

BUGCROWD_API_URL = "https://api.bugcrowd.com"


class BugcrowdClient(BasePlatformClient):
    """Bugcrowd REST API client."""

    def __init__(self, api_key: str):
        """Initialize with Bugcrowd API key."""
        super().__init__(api_key, BUGCROWD_API_URL)
        self.authenticated = False

    async def authenticate(self) -> bool:
        """Authenticate with Bugcrowd REST API."""
        try:
            headers = self._get_auth_headers()
            self.session = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout,
            )

            # Test authentication
            response = await self.session.get(f"{self.api_url}/account")
            if response.status_code == 200:
                self.authenticated = True
                logger.info("✓ Authenticated with Bugcrowd API")
                return True
            else:
                logger.error(f"✗ Bugcrowd authentication failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ Bugcrowd authentication error: {str(e)}")
            return False

    async def submit_finding(self, payload: SubmissionPayload) -> SubmissionResult:
        """Submit vulnerability to Bugcrowd."""
        if not self.authenticated:
            return SubmissionResult(
                success=False,
                message="Not authenticated with Bugcrowd",
                error_code="AUTH_REQUIRED",
            )

        # Check for duplicates first
        if self._is_duplicate_check_enabled():
            is_dup = await self.check_duplicate(payload.target_url, payload.cve_id)
            if is_dup:
                return SubmissionResult(
                    success=False,
                    message=f"CVE {payload.cve_id} already submitted on target",
                    error_code="DUPLICATE",
                )

        try:
            # Build Bugcrowd submission
            submission_data = {
                "vulnerability_report": {
                    "title": payload.title,
                    "description": payload.description,
                    "vulnerability_type": payload.vulnerability_type,
                    "severity_rating": self._map_severity_to_bugcrowd(payload.severity),
                    "affected_url": payload.target_url,
                    "proof_of_concept": payload.proof_of_concept,
                    "impact": payload.impact_description,
                }
            }

            # Add optional fields
            if payload.remediation:
                submission_data["vulnerability_report"]["suggested_fix"] = payload.remediation
            if payload.affected_version:
                submission_data["vulnerability_report"]["affected_version"] = (
                    payload.affected_version
                )

            program_id = self._extract_bugcrowd_program(payload.target_url)
            endpoint = f"{self.api_url}/programs/{program_id}/vulnerability_reports"

            response = await self.session.post(endpoint, json=submission_data)

            if response.status_code in (200, 201):
                data = response.json()
                report = data.get("vulnerability_report", {})
                return SubmissionResult(
                    success=True,
                    platform_submission_id=report.get("id"),
                    submission_url=report.get("url"),
                    message="Vulnerability report submitted successfully",
                    submitted_at=self._get_current_timestamp(),
                )
            else:
                return SubmissionResult(
                    success=False,
                    message=f"Bugcrowd submission failed: {response.status_code}",
                    error_code=f"HTTP_{response.status_code}",
                )

        except Exception as e:
            logger.error(f"✗ Bugcrowd submission error: {str(e)}")
            return SubmissionResult(
                success=False,
                message=f"Submission exception: {str(e)}",
                error_code="EXCEPTION",
            )

    async def check_duplicate(self, target: str, cve_id: str) -> bool:
        """Check if CVE already submitted on target."""
        if not self.authenticated:
            return False

        try:
            endpoint = f"{self.api_url}/researcher/submissions"
            response = await self.session.get(endpoint)

            if response.status_code == 200:
                data = response.json()
                submissions = data.get("submissions", [])
                for submission in submissions:
                    title = submission.get("title", "")
                    if cve_id in title and target in title:
                        return True
            return False
        except Exception as e:
            logger.warning(f"Duplicate check failed: {str(e)}")
            return False

    async def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get status of Bugcrowd submission."""
        if not self.authenticated:
            return {"status": "unknown", "error": "Not authenticated"}

        try:
            endpoint = f"{self.api_url}/researcher/submissions/{submission_id}"
            response = await self.session.get(endpoint)

            if response.status_code == 200:
                return response.json().get("submission", {})
            return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_programs(self) -> list[Dict[str, Any]]:
        """List available Bugcrowd programs."""
        if not self.authenticated:
            return []

        try:
            endpoint = f"{self.api_url}/programs"
            response = await self.session.get(endpoint)

            if response.status_code == 200:
                data = response.json()
                return data.get("programs", [])
            return []
        except Exception as e:
            logger.warning(f"Failed to list programs: {str(e)}")
            return []

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get Bugcrowd API authentication headers."""
        return {
            "Authorization": f"Token {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_bugcrowd_program(target_url: str) -> str:
        """Extract Bugcrowd program ID from target URL."""
        # Bugcrowd programs: google, microsoft, apple, amazon, etc.
        for program in [
            "google",
            "microsoft",
            "apple",
            "amazon",
            "facebook",
            "uber",
            "slack",
        ]:
            if program in target_url:
                return program
        return "target"

    @staticmethod
    def _map_severity_to_bugcrowd(severity: str) -> str:
        """Map K1 severity to Bugcrowd severity values."""
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }
        return mapping.get(severity.lower(), "medium")
