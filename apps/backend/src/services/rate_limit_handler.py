"""Rate limit detection and graceful backoff handler.

Detects 429 (Too Many Requests) and 503 (Service Unavailable) responses,
backs off exponentially, and signals for retry. Does NOT abort scan —
allows graceful degradation.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RateLimitHandler:
    """Detects rate limits and backs off gracefully.

    Does NOT fail the scan - just pauses and indicates retry needed.
    This is graceful degradation - the scan continues with reduced capability.
    """

    def __init__(self):
        self.backoff_seconds = 1.0
        self.rate_limit_hits = 0
        self.service_unavailable_hits = 0
        self.max_backoff_seconds = 300  # 5 minutes max

    async def handle_response(
        self, response: Any, request_details: Optional[dict[str, Any]] = None
    ) -> bool:
        """Check if response indicates rate limit or service issue.

        Args:
            response: HTTP response object with status_code and headers
            request_details: Optional dict with request details for logging

        Returns:
            True if should retry (caller should re-issue request)
            False if proceed normally
        """
        if response.status_code == 429:
            # Rate limit detected
            return await self._handle_rate_limit(response, request_details)

        elif response.status_code == 503:
            # Service unavailable - also back off
            return await self._handle_service_unavailable(response, request_details)

        else:
            # Normal response - reset backoff
            self.backoff_seconds = 1.0
            return False

    async def _handle_rate_limit(
        self, response: Any, request_details: Optional[dict[str, Any]] = None
    ) -> bool:
        """Handle 429 response with exponential backoff."""
        self.rate_limit_hits += 1

        # Try to get Retry-After header
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                wait_seconds = int(retry_after)
            except (ValueError, TypeError):
                wait_seconds = self.backoff_seconds
        else:
            wait_seconds = self.backoff_seconds

        # Log the event
        request_info = f" ({request_details})" if request_details else ""
        logger.warning(
            f"Rate limit detected (429). Backing off for {wait_seconds} seconds. "
            f"Rate limit hit #{self.rate_limit_hits}{request_info}"
        )

        # Wait (non-blocking)
        await asyncio.sleep(wait_seconds)

        # Exponential backoff for next time (capped at 5 minutes)
        self.backoff_seconds = min(self.backoff_seconds * 2, self.max_backoff_seconds)

        return True  # Indicate retry

    async def _handle_service_unavailable(
        self, response: Any, request_details: Optional[dict[str, Any]] = None
    ) -> bool:
        """Handle 503 response with exponential backoff."""
        self.service_unavailable_hits += 1

        request_info = f" ({request_details})" if request_details else ""
        logger.warning(
            f"Service unavailable (503). Backing off for {self.backoff_seconds} seconds. "
            f"Unavailable hit #{self.service_unavailable_hits}{request_info}"
        )

        # Wait (non-blocking)
        await asyncio.sleep(self.backoff_seconds)

        # Exponential backoff (capped at 5 minutes)
        self.backoff_seconds = min(self.backoff_seconds * 2, self.max_backoff_seconds)

        return True  # Indicate retry

    def reset(self) -> None:
        """Reset backoff to initial state."""
        self.backoff_seconds = 1.0

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiting statistics."""
        return {
            "rate_limit_hits": self.rate_limit_hits,
            "service_unavailable_hits": self.service_unavailable_hits,
            "current_backoff_seconds": self.backoff_seconds,
            "total_backoff_hits": self.rate_limit_hits + self.service_unavailable_hits,
        }
