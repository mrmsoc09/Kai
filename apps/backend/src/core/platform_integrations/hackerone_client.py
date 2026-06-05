"""
HackerOne platform client implementation.
Uses HackerOne GraphQL API for submission and duplicate checking.
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

H1_API_URL = "https://api.hackerone.com/v1/hackers"


class HackerOneClient(BasePlatformClient):
    """HackerOne REST API client for hackers/researchers."""

    def __init__(self, api_key: str, api_secret: str):
        """Initialize with H1 API credentials."""
        super().__init__(api_key, H1_API_URL)
        self.api_secret = api_secret
        self.authenticated = False

    async def authenticate(self) -> bool:
        """Authenticate with H1 Hacker REST API."""
        try:
            self.session = httpx.AsyncClient(
                auth=(self.api_key, self.api_secret),
                timeout=self.timeout,
            )
            # Test authentication with simple GET query to hackers/me/reports
            response = await self.session.get(f"{self.api_url}/me/reports")
            if response.status_code == 200:
                self.authenticated = True
                logger.info("✓ Authenticated with HackerOne API")
                return True
            else:
                logger.error(f"✗ H1 authentication failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ H1 authentication error: {str(e)}")
            return False

    async def submit_finding(self, payload: SubmissionPayload) -> SubmissionResult:
        """Submit vulnerability to HackerOne."""
        if not self.authenticated:
            return SubmissionResult(
                success=False,
                message="Not authenticated with HackerOne",
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
            # Build H1 report submission REST payload
            team_handle = self._extract_h1_program(payload.target_url)
            
            # Use a default mapping or generic description for impact
            impact_desc = "An attacker can exploit this vulnerability to compromise the target application."
            
            data = {
                "data": {
                    "type": "report",
                    "attributes": {
                        "team_handle": team_handle,
                        "title": payload.title,
                        "vulnerability_information": payload.description,
                        "impact": impact_desc,
                        "severity_rating": self._map_severity_to_h1(payload.severity)
                    }
                }
            }

            response = await self.session.post(
                f"{self.api_url}/reports", json=data
            )

            if response.status_code in (200, 201):
                res_data = response.json()
                report_id = res_data.get("data", {}).get("id")
                report_url = f"https://hackerone.com/reports/{report_id}" if report_id else None
                return SubmissionResult(
                    success=True,
                    platform_submission_id=report_id,
                    submission_url=report_url,
                    message="Report submitted successfully",
                    submitted_at=self._get_current_timestamp(),
                )
            else:
                errors = response.json().get("errors", [])
                return SubmissionResult(
                    success=False,
                    message=f"H1 submission failed: {errors}",
                    error_code="SUBMISSION_ERROR",
                )

        except Exception as e:
            logger.error(f"✗ H1 submission error: {str(e)}")
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
            response = await self.session.get(f"{self.api_url}/me/reports")
            if response.status_code == 200:
                data = response.json()
                reports = data.get("data", [])
                for report in reports:
                    report_title = report.get("attributes", {}).get("title", "")
                    if cve_id in report_title and target in report_title:
                        return True
            return False
        except Exception as e:
            logger.warning(f"Duplicate check failed: {str(e)}")
            return False

    async def get_submission_status(self, submission_id: str) -> Dict[str, Any]:
        """Get status of H1 report."""
        if not self.authenticated:
            return {"status": "unknown", "error": "Not authenticated"}

        try:
            response = await self.session.get(f"{self.api_url}/reports/{submission_id}")
            if response.status_code == 200:
                report_data = response.json().get("data", {})
                attributes = report_data.get("attributes", {})
                return {
                    "state": attributes.get("state"),
                    "severity": attributes.get("severity_rating"),
                    "createdAt": attributes.get("created_at"),
                }
            return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_programs(self) -> list[Dict[str, Any]]:
        """List H1 programs."""
        if not self.authenticated:
            return []

        try:
            response = await self.session.get(f"{self.api_url}/programs")
            if response.status_code == 200:
                data = response.json()
                programs = []
                for prog in data.get("data", []):
                    attributes = prog.get("attributes", {})
                    programs.append({
                        "name": attributes.get("name"),
                        "handle": attributes.get("handle"),
                    })
                return programs
            return []
        except Exception as e:
            logger.warning(f"Failed to list programs: {str(e)}")
            return []

    async def get_program_details(self, handle: str) -> Optional[Dict[str, Any]]:
        """Get full program details including scope and guidelines."""
        if not self.authenticated:
            return None

        try:
            response = await self.session.get(f"{self.api_url}/programs/{handle}")
            if response.status_code == 200:
                res_json = response.json()
                data = res_json.get("data") if "data" in res_json else res_json
                attributes = data.get("attributes", {})
                relationships = data.get("relationships", {})
                
                # Format structured scopes to match the GraphQL output
                # for compatibility with the orchestrator.
                edges = []
                scopes = relationships.get("structured_scopes", {}).get("data", [])
                for scope in scopes:
                    scope_attrs = scope.get("attributes", {})
                    edges.append({
                        "node": {
                            "asset_identifier": scope_attrs.get("asset_identifier"),
                            "asset_type": scope_attrs.get("asset_type"),
                            "instruction": scope_attrs.get("instruction"),
                            "availability_requirement": scope_attrs.get("availability_requirement"),
                        }
                    })
                
                return {
                    "name": attributes.get("name"),
                    "handle": attributes.get("handle"),
                    "policy": attributes.get("policy"),
                    "structured_scopes": {
                        "edges": edges
                    }
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get program details for {handle}: {e}")
            return None

    @staticmethod
    def _extract_h1_program(target_url: str) -> str:
        """Extract H1 program handle from target URL."""
        # H1 programs map: shopify, facebook, google, microsoft, etc.
        for program in ["shopify", "google", "microsoft", "facebook", "github", "gitlab"]:
            if program in target_url:
                return program
        return "target"

    @staticmethod
    def _map_severity_to_h1(severity: str) -> str:
        """Map K1 severity to H1 severity values."""
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }
        return mapping.get(severity.lower(), "medium")
