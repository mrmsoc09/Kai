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

H1_API_URL = "https://api.hackerone.com/v1/graphql"


class HackerOneClient(BasePlatformClient):
    """HackerOne GraphQL API client."""

    def __init__(self, api_key: str, api_secret: str):
        """Initialize with H1 API credentials."""
        super().__init__(api_key, H1_API_URL)
        self.api_secret = api_secret
        self.authenticated = False

    async def authenticate(self) -> bool:
        """Authenticate with H1 GraphQL API."""
        try:
            self.session = httpx.AsyncClient(
                auth=(self.api_key, self.api_secret),
                timeout=self.timeout,
            )
            # Test authentication with simple query
            query = """
            query {
              viewer {
                username
              }
            }
            """
            response = await self.session.post(self.api_url, json={"query": query})
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
            # Build H1 report submission
            mutation = """
            mutation CreateReport($input: CreateReportInput!) {
              createReport(input: $input) {
                report {
                  id
                  number
                  url
                }
                errors {
                  message
                }
              }
            }
            """

            variables = {
                "input": {
                    "programHandle": self._extract_h1_program(payload.target_url),
                    "title": payload.title,
                    "description": payload.description,
                    "vulnerabilityTypes": [payload.vulnerability_type],
                    "severity": self._map_severity_to_h1(payload.severity),
                    "affectedUrl": payload.target_url,
                    "proofOfConcept": payload.proof_of_concept,
                }
            }

            response = await self.session.post(
                self.api_url, json={"query": mutation, "variables": variables}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("createReport", {}).get("report"):
                    report = data["data"]["createReport"]["report"]
                    return SubmissionResult(
                        success=True,
                        platform_submission_id=report.get("id"),
                        submission_url=report.get("url"),
                        message="Report submitted successfully",
                        submitted_at=self._get_current_timestamp(),
                    )
                else:
                    errors = data.get("data", {}).get("createReport", {}).get("errors", [])
                    return SubmissionResult(
                        success=False,
                        message=f"H1 submission failed: {errors}",
                        error_code="SUBMISSION_ERROR",
                    )
            else:
                return SubmissionResult(
                    success=False,
                    message=f"H1 API error: {response.status_code}",
                    error_code=f"HTTP_{response.status_code}",
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
            query = """
            query {
              me {
                reports(first: 100, filter: "scope") {
                  edges {
                    node {
                      title
                      url
                    }
                  }
                }
              }
            }
            """

            response = await self.session.post(self.api_url, json={"query": query})
            if response.status_code == 200:
                data = response.json()
                reports = data.get("data", {}).get("me", {}).get("reports", {}).get("edges", [])
                for edge in reports:
                    report_title = edge.get("node", {}).get("title", "")
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
            query = f"""
            query {{
              report(id: "{submission_id}") {{
                state
                severity
                createdAt
              }}
            }}
            """

            response = await self.session.post(self.api_url, json={"query": query})
            if response.status_code == 200:
                return response.json().get("data", {}).get("report", {})
            return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_programs(self) -> list[Dict[str, Any]]:
        """List H1 programs."""
        if not self.authenticated:
            return []

        try:
            query = """
            query {
              me {
                programs(first: 100) {
                  edges {
                    node {
                      name
                      handle
                    }
                  }
                }
              }
            }
            """

            response = await self.session.post(self.api_url, json={"query": query})
            if response.status_code == 200:
                data = response.json()
                programs = []
                for edge in (
                    data.get("data", {})
                    .get("me", {})
                    .get("programs", {})
                    .get("edges", [])
                ):
                    programs.append(edge.get("node", {}))
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
            query = f"""
            query {{
              program(handle: "{handle}") {{
                name
                handle
                policy
                structured_scopes(first: 100) {{
                  edges {{
                    node {{
                      asset_identifier
                      asset_type
                      instruction
                      availability_requirement
                    }}
                  }}
                }}
              }}
            }}
            """
            response = await self.session.post(self.api_url, json={"query": query})
            if response.status_code == 200:
                return response.json().get("data", {}).get("program")
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
