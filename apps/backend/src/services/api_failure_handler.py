"""Graceful degradation handler for API outages.

When external APIs (Vault, H1, Intigriti) are down, scans continue
with reduced capability rather than failing completely.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, TypeVar, Coroutine

logger = logging.getLogger(__name__)

T = TypeVar("T")


class APIFailureHandler:
    """Handle API failures gracefully - scan continues without that API.

    Different failures have different impacts:
    - Vault down → authenticated scans disabled, use unauthenticated only
    - H1 API down → can't submit findings to H1, queue them locally
    - Intigriti API down → can't submit to Intigriti, queue them locally
    """

    def handle_vault_down(self, scan_id: Optional[str] = None) -> dict[str, Any]:
        """Vault is down - can't get credentials.

        Impact: Authenticated scans disabled
        Action: Continue with unauthenticated scanning only

        Args:
            scan_id: Optional scan ID for logging

        Returns:
            Dict with available modes and impact
        """
        logger.error("Vault unreachable - authenticated scans disabled")

        return {
            "vault_available": False,
            "impact": "Authenticated scans unavailable",
            "action": "Continue with unauthenticated scanning only",
            "scanning_modes": ["unauthenticated"],
            "queued_credentials": False,
        }

    async def handle_vault_down_async(self, scan_id: Optional[str] = None) -> dict[str, Any]:
        """Async compatibility wrapper for orchestration call sites."""
        return self.handle_vault_down(scan_id=scan_id)

    def handle_h1_api_down(self, program_id: Optional[str] = None) -> dict[str, Any]:
        """H1 API is down - can't submit findings yet.

        Impact: Cannot submit findings to H1
        Action: Queue findings locally, will submit when API recovers

        Args:
            program_id: Optional program ID for logging

        Returns:
            Dict with impact and action
        """
        logger.warning(f"H1 API unavailable for {program_id or 'all programs'}")

        return {
            "h1_available": False,
            "platform": "h1",
            "impact": "Cannot submit findings to H1",
            "action": "Queue findings locally, will submit when API recovers",
            "queued_findings": True,
        }

    async def handle_h1_api_down_async(self, program_id: Optional[str] = None) -> dict[str, Any]:
        """Async compatibility wrapper for orchestration call sites."""
        return self.handle_h1_api_down(program_id=program_id)

    def handle_intigriti_api_down(self, program_id: Optional[str] = None) -> dict[str, Any]:
        """Intigriti API is down - can't submit findings yet.

        Impact: Cannot submit to Intigriti
        Action: Queue findings locally, will submit when API recovers

        Args:
            program_id: Optional program ID for logging

        Returns:
            Dict with impact and action
        """
        logger.warning(f"Intigriti API unavailable for {program_id or 'all programs'}")

        return {
            "intigriti_available": False,
            "platform": "intigriti",
            "impact": "Cannot submit findings to Intigriti",
            "action": "Queue findings locally, will submit when API recovers",
            "queued_findings": True,
        }

    async def handle_intigriti_api_down_async(
        self, program_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Async compatibility wrapper for orchestration call sites."""
        return self.handle_intigriti_api_down(program_id=program_id)

    def handle_database_down(self) -> dict[str, Any]:
        """Database is down - cannot continue.

        Impact: Cannot store findings or track scan state
        Action: Abort scan (cannot continue without DB)

        Returns:
            Dict with impact and action
        """
        logger.error("Database unavailable - cannot continue")

        return {
            "database_available": False,
            "impact": "Cannot store findings or track scan state",
            "action": "Abort scan - cannot continue without database",
            "recoverable": False,
        }

    async def safe_call(
        self,
        coro: Coroutine[Any, Any, T],
        fallback_value: T,
        error_context: str = "",
        timeout_seconds: float = 10.0,
    ) -> T:
        """Generic try/except wrapper for optional API calls.

        If the call fails or times out, returns fallback value instead
        of crashing the scan.

        Args:
            coro: Async coroutine to execute
            fallback_value: Value to return if call fails
            error_context: Context string for logging
            timeout_seconds: Timeout before giving up

        Returns:
            Result from coro, or fallback_value on error/timeout
        """
        try:
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
            return result

        except asyncio.TimeoutError:
            logger.error(f"{error_context}: Timeout after {timeout_seconds}s, using fallback")
            return fallback_value

        except Exception as e:
            logger.error(f"{error_context}: {type(e).__name__}: {e}, using fallback")
            return fallback_value

    def check_required_services(self) -> dict[str, Any]:
        """Check which services are required for scan to continue.

        Returns:
            Dict with required vs optional services
        """
        return {
            "required": [
                "database",  # Cannot continue without DB
            ],
            "optional": [
                "vault",  # Can scan unauthenticated without Vault
                "h1_api",  # Can queue findings locally without H1 API
                "intigriti_api",  # Can queue findings locally without Intigriti API
            ],
            "recommendation": "Scan can continue if database is available, "
            "even if Vault or platform APIs are down",
        }
