"""
Intigriti platform client implementation.
Uses Intigriti REST API for submission and duplicate checking.
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

INTIGRITI_API_URL = "https://api.intigriti.com/external/researcher/v1"


class IntigrityClient(BasePlatformClient):
    """Intigriti REST API client."""

    def __init__(self, api_key: str):
        """Initialize with Intigriti API key."""
        super().__init__(api_key, INTIGRITI_API_URL)
        self.authenticated = False

    async def authenticate(self) -> bool:
        """Authenticate with Intigriti REST API."""
        try:
            headers = self._get_auth_headers()
            self.session = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout,
            )

            # Test authentication using /programs instead of /profile
            response = await self.session.get(f"{self.api_url}/programs")
            if response.status_code == 200:
                self.authenticated = True
                logger.info("✓ Authenticated with Intigriti API")
                return True
            else:
                logger.error(
                    f"✗ Intigriti authentication failed: {response.status_code}"
                )
                return False
        except Exception as e:
            logger.error(f"✗ Intigriti authentication error: {str(e)}")
            return False

    async def submit_finding(self, payload: SubmissionPayload) -> SubmissionResult:
        """Submit vulnerability to Intigriti."""
        if not self.authenticated:
            return SubmissionResult(
                success=False,
                message="Not authenticated with Intigriti",
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
            # Build Intigriti submission
            submission_data = {
                "title": payload.title,
                "description": payload.description,
                "vulnerabilityType": payload.vulnerability_type,
                "severity": self._map_severity_to_intigriti(payload.severity),
                "affectedUrl": payload.target_url,
                "proofOfConcept": payload.proof_of_concept,
                "impact": payload.impact_description,
            }

            # Add optional fields
            if payload.remediation:
                submission_data["suggestedFix"] = payload.remediation
            if payload.affected_version:
                submission_data["affectedVersion"] = payload.affected_version

            program_id = self._extract_intigriti_program(payload.target_url)
            endpoint = f"{self.api_url}/programs/{program_id}/submissions"

            response = await self.session.post(endpoint, json=submission_data)

            if response.status_code in (200, 201):
                data = response.json()
                return SubmissionResult(
                    success=True,
                    platform_submission_id=data.get("id"),
                    submission_url=data.get("url"),
                    message="Vulnerability submission created successfully",
                    submitted_at=self._get_current_timestamp(),
                )
            else:
                return SubmissionResult(
                    success=False,
                    message=f"Intigriti submission failed: {response.status_code}",
                    error_code=f"HTTP_{response.status_code}",
                )

        except Exception as e:
            logger.error(f"✗ Intigriti submission error: {str(e)}")
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
            endpoint = f"{self.api_url}/submissions"
            response = await self.session.get(endpoint)

            if response.status_code == 200:
                data = response.json()
                submissions = data.get("submissions", [])
                for submission in submissions:
                    title = submission.get("title", "")
                    affected_url = submission.get("affectedUrl", "")
                    if cve_id in title and target in affected_url:
                        return True
            return False
        except Exception as e:
            logger.warning(f"Duplicate check failed: {str(e)}")
            return False

    async def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get status of Intigriti submission."""
        if not self.authenticated:
            return {"status": "unknown", "error": "Not authenticated"}

        try:
            endpoint = f"{self.api_url}/submissions/{submission_id}"
            response = await self.session.get(endpoint)

            if response.status_code == 200:
                return response.json()
            return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_programs(self) -> list[Dict[str, Any]]:
        """List available Intigriti programs."""
        if not self.authenticated:
            return []

        try:
            endpoint = f"{self.api_url}/programs"
            response = await self.session.get(endpoint)

            if response.status_code == 200:
                data = response.json()
                return data.get("records") or data.get("programs") or []
            return []
        except Exception as e:
            logger.warning(f"Failed to list programs: {str(e)}")
            return []

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get Intigriti API authentication headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_intigriti_program(target_url: str) -> str:
        """Extract Intigriti program ID from target URL."""
        # Intigriti programs map
        for program in [
            "google",
            "microsoft",
            "apple",
            "amazon",
            "facebook",
            "airbnb",
            "stripe",
            "dropbox",
        ]:
            if program in target_url:
                return program
        return "target"

    @staticmethod
    def _map_severity_to_intigriti(severity: str) -> str:
        """Map K1 severity to Intigriti severity values."""
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }
        return mapping.get(severity.lower(), "medium")
