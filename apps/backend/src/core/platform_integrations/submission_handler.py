"""
Platform submission handler with factory pattern.
Orchestrates submission workflow across HackerOne, Bugcrowd, and Intigriti.
"""

from __future__ import annotations

import logging
from typing import Optional
from enum import Enum
from .base_platform_client import BasePlatformClient, SubmissionPayload, SubmissionResult
from .hackerone_client import HackerOneClient
from .bugcrowd_client import BugcrowdClient
from .intigriti_client import IntigrityClient

logger = logging.getLogger(__name__)


class PlatformType(str, Enum):
    """Supported bug bounty platforms."""

    HACKERONE = "hackerone"
    BUGCROWD = "bugcrowd"
    INTIGRITI = "intigriti"


def get_platform_client(
    platform: PlatformType | str, api_key: str, api_secret: Optional[str] = None
) -> BasePlatformClient:
    """
    Factory function to get platform-specific client.

    Args:
        platform: Platform type (hackerone, bugcrowd, intigriti)
        api_key: Platform API key
        api_secret: Optional API secret (required for HackerOne)

    Returns:
        Platform-specific client instance

    Raises:
        ValueError: If platform is unsupported or credentials missing
    """
    platform_str = platform.lower() if isinstance(platform, str) else platform.value

    if platform_str == PlatformType.HACKERONE.value:
        if not api_secret:
            raise ValueError(
                "HackerOne requires both api_key and api_secret credentials"
            )
        return HackerOneClient(api_key=api_key, api_secret=api_secret)

    elif platform_str == PlatformType.BUGCROWD.value:
        return BugcrowdClient(api_key=api_key)

    elif platform_str == PlatformType.INTIGRITI.value:
        return IntigrityClient(api_key=api_key)

    else:
        raise ValueError(
            f"Unsupported platform: {platform_str}. "
            f"Supported: {', '.join(p.value for p in PlatformType)}"
        )


class SubmissionHandler:
    """
    Orchestrates vulnerability submissions across multiple platforms.
    Handles deduplication, rate limiting, and submission lifecycle.
    """

    def __init__(self):
        """Initialize submission handler with platform clients."""
        self.clients: dict[str, BasePlatformClient] = {}
        self.authenticated_platforms: set[str] = set()

    async def initialize(
        self, credentials: dict[str, dict[str, str]]
    ) -> dict[str, bool]:
        """
        Initialize and authenticate with specified platforms.

        Args:
            credentials: Dict of platform credentials
                {
                    "hackerone": {"api_key": "...", "api_secret": "..."},
                    "bugcrowd": {"api_key": "..."},
                    "intigriti": {"api_key": "..."}
                }

        Returns:
            Dict mapping platform name to authentication success
        """
        auth_results = {}

        for platform, creds in credentials.items():
            try:
                platform_type = PlatformType(platform)
                api_key = creds.get("api_key")
                api_secret = creds.get("api_secret")

                if not api_key:
                    logger.error(f"Missing api_key for {platform}")
                    auth_results[platform] = False
                    continue

                client = get_platform_client(
                    platform_type, api_key=api_key, api_secret=api_secret
                )
                authenticated = await client.authenticate()

                self.clients[platform] = client
                if authenticated:
                    self.authenticated_platforms.add(platform)
                    logger.info(f"✓ Initialized {platform}")

                auth_results[platform] = authenticated

            except ValueError as e:
                logger.error(f"Configuration error for {platform}: {str(e)}")
                auth_results[platform] = False
            except Exception as e:
                logger.error(f"Authentication error for {platform}: {str(e)}")
                auth_results[platform] = False

        return auth_results

    async def submit_to_platform(
        self, platform: str, payload: SubmissionPayload
    ) -> SubmissionResult:
        """
        Submit vulnerability to specific platform.

        Args:
            platform: Target platform (hackerone, bugcrowd, intigriti)
            payload: Submission payload

        Returns:
            Submission result with status and details
        """
        if platform not in self.clients:
            return SubmissionResult(
                success=False,
                message=f"Platform '{platform}' not initialized",
                error_code="NOT_INITIALIZED",
            )

        if platform not in self.authenticated_platforms:
            return SubmissionResult(
                success=False,
                message=f"Not authenticated with {platform}",
                error_code="NOT_AUTHENTICATED",
            )

        client = self.clients[platform]
        return await client.submit_finding(payload)

    async def submit_to_all_platforms(
        self, payload: SubmissionPayload, skip_platforms: Optional[list[str]] = None
    ) -> dict[str, SubmissionResult]:
        """
        Submit vulnerability to all authenticated platforms.

        Args:
            payload: Submission payload
            skip_platforms: Optional list of platforms to skip

        Returns:
            Dict mapping platform name to submission result
        """
        skip_platforms = skip_platforms or []
        results = {}

        for platform in self.authenticated_platforms:
            if platform in skip_platforms:
                logger.info(f"Skipping {platform} as requested")
                continue

            logger.info(f"Submitting to {platform}...")
            result = await self.submit_to_platform(platform, payload)
            results[platform] = result

            if result.success:
                logger.info(f"✓ Successfully submitted to {platform}")
            else:
                logger.error(
                    f"✗ Failed to submit to {platform}: {result.message}"
                )

        return results

    async def check_duplicates(
        self, target_url: str, cve_id: str
    ) -> dict[str, bool]:
        """
        Check for duplicate submissions across authenticated platforms.

        Args:
            target_url: Target URL
            cve_id: CVE identifier

        Returns:
            Dict mapping platform name to duplicate status
        """
        duplicates = {}

        for platform in self.authenticated_platforms:
            client = self.clients[platform]
            try:
                is_dup = await client.check_duplicate(target_url, cve_id)
                duplicates[platform] = is_dup
                if is_dup:
                    logger.warning(
                        f"Found duplicate {cve_id} on {platform} for {target_url}"
                    )
            except Exception as e:
                logger.error(
                    f"Error checking duplicates on {platform}: {str(e)}"
                )
                duplicates[platform] = False

        return duplicates

    async def get_submission_status(
        self, platform: str, submission_id: str
    ) -> dict:
        """
        Get submission status from specific platform.

        Args:
            platform: Target platform
            submission_id: Submission ID from platform

        Returns:
            Submission status details
        """
        if platform not in self.clients:
            return {"status": "error", "message": f"Platform '{platform}' unknown"}

        client = self.clients[platform]
        return await client.get_submission_status(submission_id)

    async def list_available_programs(
        self, platform: str
    ) -> list[dict[str, any]]:
        """
        List available bug bounty programs on platform.

        Args:
            platform: Target platform

        Returns:
            List of program details
        """
        if platform not in self.clients:
            return []

        client = self.clients[platform]
        return await client.list_programs()

    async def close_all(self) -> None:
        """Close all platform client sessions."""
        for platform, client in self.clients.items():
            try:
                await client.close()
                logger.info(f"Closed {platform} client")
            except Exception as e:
                logger.warning(f"Error closing {platform} client: {str(e)}")

    def get_status(self) -> dict[str, any]:
        """Get submission handler status."""
        return {
            "authenticated_platforms": list(self.authenticated_platforms),
            "initialized_platforms": list(self.clients.keys()),
            "total_platforms": len(self.clients),
        }
