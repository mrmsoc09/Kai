"""
Platform-specific rate limiting middleware.
Enforces rate limits for HackerOne, Bugcrowd, and Intigriti APIs.
Prevents IP bans and WAF blocks through intelligent request throttling.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timedelta, timezone
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a platform."""

    platform: str
    requests_per_minute: int
    burst_size: int = 5
    backoff_factor: float = 1.5
    max_retries: int = 3
    timeout_seconds: int = 60

    @property
    def request_interval_ms(self) -> int:
        """Minimum milliseconds between requests."""
        return int((60000 / self.requests_per_minute))


# Platform-specific rate limit configurations
PLATFORM_RATE_LIMITS = {
    "hackerone": RateLimitConfig(
        platform="hackerone",
        requests_per_minute=30,
        burst_size=5,
        backoff_factor=1.5,
    ),
    "bugcrowd": RateLimitConfig(
        platform="bugcrowd",
        requests_per_minute=10,
        burst_size=2,
        backoff_factor=2.0,
    ),
    "intigriti": RateLimitConfig(
        platform="intigriti",
        requests_per_minute=20,
        burst_size=4,
        backoff_factor=1.5,
    ),
}


@dataclass
class RequestWindow:
    """Sliding window for rate limiting."""

    platform: str
    config: RateLimitConfig
    requests: deque = field(default_factory=deque)
    throttled_until: Optional[float] = None
    backoff_count: int = 0

    async def should_throttle(self) -> bool:
        """Check if request should be throttled."""
        now = time.time()

        # Check if in backoff period
        if self.throttled_until and now < self.throttled_until:
            return True

        # Remove requests outside the window
        window_start = now - 60

        while self.requests and self.requests[0] < window_start:
            self.requests.popleft()

        # Check if at limit
        return len(self.requests) >= self.config.requests_per_minute

    async def record_request(self) -> None:
        """Record a successful request."""
        self.requests.append(time.time())
        self.backoff_count = 0
        logger.debug(
            f"Recorded request for {self.platform}. "
            f"Total in window: {len(self.requests)}"
        )

    async def record_rate_limit_hit(self) -> None:
        """Record rate limit hit and apply backoff."""
        self.backoff_count += 1
        backoff_seconds = (
            self.config.backoff_factor ** self.backoff_count
        )
        self.throttled_until = time.time() + backoff_seconds
        logger.warning(
            f"Rate limit hit for {self.platform}. "
            f"Backoff: {backoff_seconds:.1f}s"
        )

    async def wait_if_needed(self) -> None:
        """Wait until request can be made."""
        if await self.should_throttle():
            await self.calculate_wait_time()

    async def calculate_wait_time(self) -> float:
        """Calculate wait time before next request."""
        now = time.time()

        # Check backoff period
        if self.throttled_until and now < self.throttled_until:
            wait = self.throttled_until - now
            logger.debug(
                f"Waiting {wait:.2f}s for {self.platform} (backoff)"
            )
            await asyncio.sleep(wait)
            return wait

        # Check rate limit window
        window_start = now - 60

        if self.requests:
            oldest_request = self.requests[0]
            if oldest_request > window_start:
                wait = oldest_request - window_start + 1
                logger.debug(
                    f"Waiting {wait:.2f}s for {self.platform} "
                    f"(rate limit window)"
                )
                await asyncio.sleep(wait)
                return wait

        return 0


class PlatformRateLimiter:
    """
    Manages rate limiting across multiple bug bounty platforms.
    Enforces per-platform rate limits and backoff strategies.
    """

    def __init__(self):
        """Initialize rate limiter."""
        self.windows: Dict[str, RequestWindow] = {}

        # Initialize windows for each platform
        for platform, config in PLATFORM_RATE_LIMITS.items():
            self.windows[platform] = RequestWindow(
                platform=platform, config=config
            )

        logger.info(
            f"Initialized rate limiter for {len(self.windows)} platforms"
        )

    async def acquire(
        self, platform: str, timeout_seconds: int = 60
    ) -> bool:
        """
        Acquire permission to make API request.

        Args:
            platform: Target platform
            timeout_seconds: Max time to wait for permission

        Returns:
            True if request can be made, False if timeout
        """
        if platform not in self.windows:
            logger.error(f"Unknown platform: {platform}")
            return False

        window = self.windows[platform]
        start_time = time.time()

        while True:
            if not await window.should_throttle():
                await window.record_request()
                logger.debug(f"Acquired rate limit slot for {platform}")
                return True

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                logger.warning(
                    f"Timeout waiting for rate limit slot on {platform}"
                )
                return False

            # Wait before retrying
            await window.wait_if_needed()

    async def record_api_error(
        self, platform: str, status_code: Optional[int] = None
    ) -> None:
        """
        Record API error and adjust rate limiting.

        Args:
            platform: Target platform
            status_code: HTTP status code (if applicable)
        """
        if platform not in self.windows:
            return

        window = self.windows[platform]

        if status_code == 429:  # Too Many Requests
            await window.record_rate_limit_hit()
            logger.warning(
                f"Platform {platform} returned 429. "
                f"Activating backoff."
            )

        elif status_code in (503, 502, 500):  # Server errors
            # Slightly less aggressive backoff for server errors
            logger.warning(
                f"Platform {platform} returned {status_code}. "
                f"May be under load."
            )

    async def get_status(self) -> Dict[str, any]:
        """Get rate limiter status."""
        status = {}

        for platform, window in self.windows.items():
            now = time.time()
            window_start = now - 60

            # Count requests in current window
            active_requests = sum(
                1 for t in window.requests if t > window_start
            )

            status[platform] = {
                "config": {
                    "requests_per_minute": (
                        window.config.requests_per_minute
                    ),
                    "burst_size": window.config.burst_size,
                },
                "current_state": {
                    "requests_in_window": active_requests,
                    "capacity_remaining": max(
                        0,
                        window.config.requests_per_minute - active_requests,
                    ),
                    "is_throttled": await window.should_throttle(),
                    "backoff_level": window.backoff_count,
                    "throttled_until": (
                        window.throttled_until - now
                        if window.throttled_until
                        else None
                    ),
                },
            }

        return {"platforms": status, "timestamp": datetime.now(
            timezone.utc
        ).isoformat()}

    async def reset_backoff(self, platform: str) -> None:
        """Reset backoff for a platform (e.g., after successful period)."""
        if platform in self.windows:
            self.windows[platform].backoff_count = 0
            self.windows[platform].throttled_until = None
            logger.info(f"Reset backoff for {platform}")

    async def reset_all(self) -> None:
        """Reset all rate limit state."""
        for window in self.windows.values():
            window.requests.clear()
            window.throttled_until = None
            window.backoff_count = 0

        logger.info("Reset all rate limit windows")

    async def get_wait_time(self, platform: str) -> float:
        """
        Get estimated wait time before next request.

        Args:
            platform: Target platform

        Returns:
            Wait time in seconds
        """
        if platform not in self.windows:
            return 0

        window = self.windows[platform]

        if not await window.should_throttle():
            return 0

        now = time.time()

        # Check backoff
        if window.throttled_until:
            return max(0, window.throttled_until - now)

        # Check window
        if window.requests:
            oldest = window.requests[0]
            window_age = now - oldest
            if window_age < 60:
                return 60 - window_age

        return 0


# Global rate limiter instance
_global_rate_limiter: Optional[PlatformRateLimiter] = None


async def get_rate_limiter() -> PlatformRateLimiter:
    """Get or create global rate limiter instance."""
    global _global_rate_limiter

    if _global_rate_limiter is None:
        _global_rate_limiter = PlatformRateLimiter()

    return _global_rate_limiter


async def apply_rate_limit(
    platform: str, timeout_seconds: int = 60
) -> bool:
    """
    Apply rate limit before making platform API call.

    Args:
        platform: Target platform
        timeout_seconds: Max wait time

    Returns:
        True if request allowed
    """
    limiter = await get_rate_limiter()
    return await limiter.acquire(platform, timeout_seconds)


async def record_api_error(
    platform: str, status_code: Optional[int] = None
) -> None:
    """
    Record API error for rate limit adjustment.

    Args:
        platform: Target platform
        status_code: HTTP status code
    """
    limiter = await get_rate_limiter()
    await limiter.record_api_error(platform, status_code)
