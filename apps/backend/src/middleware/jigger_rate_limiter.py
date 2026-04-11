"""
Advanced Jigger Rate Limiter.
Implements adaptive jitter and non-linear delays to mimic human interaction patterns.
Prevents WAF/bot detection while maintaining efficient API usage.
"""

from __future__ import annotations

import logging
import asyncio
import random
import time
import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class InteractionPattern(str, Enum):
    """Human interaction patterns."""

    CAUTIOUS = "cautious"  # Long pauses between requests
    NORMAL = "normal"  # Typical browsing behavior
    AGGRESSIVE = "aggressive"  # Faster, riskier pattern


@dataclass
class JiggerProfile:
    """Jigger profile for adaptive timing."""

    platform: str
    base_delay_ms: float  # Base delay in milliseconds
    jitter_range_ms: float  # +/- jitter range
    burst_delay_ms: float  # Delay within bursts
    burst_size: int  # Requests per burst
    backoff_multiplier: float  # Backoff on errors
    pattern: InteractionPattern = InteractionPattern.NORMAL

    def get_delay_ms(self) -> float:
        """Calculate next delay with jitter."""
        base = self.base_delay_ms
        jitter = random.uniform(
            -self.jitter_range_ms, self.jitter_range_ms
        )
        delay = base + jitter
        return max(100, delay)  # Minimum 100ms


# Platform-specific jigger profiles
JIGGER_PROFILES = {
    "hackerone": JiggerProfile(
        platform="hackerone",
        base_delay_ms=2000,
        jitter_range_ms=500,
        burst_delay_ms=500,
        burst_size=5,
        backoff_multiplier=1.5,
        pattern=InteractionPattern.NORMAL,
    ),
    "bugcrowd": JiggerProfile(
        platform="bugcrowd",
        base_delay_ms=4000,
        jitter_range_ms=1000,
        burst_delay_ms=800,
        burst_size=3,
        backoff_multiplier=2.0,
        pattern=InteractionPattern.CAUTIOUS,
    ),
    "intigriti": JiggerProfile(
        platform="intigriti",
        base_delay_ms=3000,
        jitter_range_ms=750,
        burst_delay_ms=600,
        burst_size=4,
        backoff_multiplier=1.75,
        pattern=InteractionPattern.NORMAL,
    ),
}


class JiggerClient:
    """
    Adaptive request pacing client.
    Introduces human-like jitter and non-linear delays to avoid detection.
    """

    def __init__(self, platform: str = "hackerone"):
        """
        Initialize jigger client.

        Args:
            platform: Target platform
        """
        self.platform = platform
        self.profile = JIGGER_PROFILES.get(
            platform.lower(),
            JIGGER_PROFILES["hackerone"],
        )

        # State tracking
        self.request_count: int = 0
        self.burst_count: int = 0
        self.last_request_time: Optional[float] = None
        self.last_delay: float = 0
        self.backoff_level: int = 0
        self.error_count: int = 0

        # Cognitive delay simulation
        self.cognitive_pauses: int = 0
        self.thinking_delay_ms: float = 0

        logger.info(
            f"JiggerClient initialized for {platform} "
            f"with pattern: {self.profile.pattern.value}"
        )

    async def wait_before_request(self) -> float:
        """
        Wait appropriate amount of time before next request.

        Returns:
            Actual delay applied in milliseconds
        """
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return 0

        # Calculate delay
        delay_ms = self._calculate_delay()

        # Add cognitive thinking pause (5% chance)
        if random.random() < 0.05:
            self.cognitive_pauses += 1
            cognitive_delay = random.uniform(2000, 8000)
            delay_ms += cognitive_delay
            logger.debug(
                f"Added cognitive pause: {cognitive_delay:.0f}ms"
            )

        # Convert to seconds and sleep
        delay_seconds = delay_ms / 1000.0
        logger.debug(
            f"[{self.platform}] Waiting {delay_ms:.0f}ms "
            f"(burst {self.burst_count}/{self.profile.burst_size})"
        )

        await asyncio.sleep(delay_seconds)

        # Update state
        self.last_request_time = time.time()
        self.last_delay = delay_ms
        self.request_count += 1
        self.burst_count += 1

        # Burst reset
        if self.burst_count >= self.profile.burst_size:
            self.burst_count = 0

        return delay_ms

    def _calculate_delay(self) -> float:
        """Calculate next delay with adaptive logic."""
        if self.burst_count == 0:
            # First request in burst: use base delay
            return self.profile.get_delay_ms()
        elif self.burst_count < self.profile.burst_size:
            # Within burst: short inter-request delay
            return (
                self.profile.burst_delay_ms
                + random.uniform(-200, 200)
            )
        else:
            # After burst: longer pause with backoff
            return self._calculate_backoff_delay()

    def _calculate_backoff_delay(self) -> float:
        """Calculate exponential backoff delay."""
        # Exponential backoff: 2^backoff_level * base_delay
        exponent = min(self.backoff_level, 5)
        delay = (
            self.profile.base_delay_ms
            * (self.profile.backoff_multiplier ** exponent)
        )

        # Add random jitter
        jitter = random.uniform(-delay * 0.2, delay * 0.2)
        return max(1000, delay + jitter)

    def record_error(self) -> None:
        """Record an error and increase backoff."""
        self.error_count += 1
        self.backoff_level = min(self.backoff_level + 1, 5)
        logger.warning(
            f"Error recorded. Backoff level: {self.backoff_level}"
        )

    def record_success(self) -> None:
        """Record success and potentially reduce backoff."""
        if self.backoff_level > 0 and random.random() < 0.3:
            self.backoff_level = max(self.backoff_level - 1, 0)

    def record_rate_limit(self, retry_after_seconds: Optional[int] = None) -> float:
        """
        Record rate limit hit and calculate next retry delay.

        Args:
            retry_after_seconds: Server-provided retry-after header

        Returns:
            Delay until next retry in seconds
        """
        self.backoff_level = min(self.backoff_level + 2, 5)

        if retry_after_seconds:
            delay_seconds = retry_after_seconds + random.uniform(1, 5)
            logger.warning(
                f"Rate limit hit. Retrying in {delay_seconds:.1f}s "
                f"(server suggests {retry_after_seconds}s)"
            )
            return delay_seconds

        # Calculate own backoff
        backoff_seconds = (
            2 ** min(self.backoff_level, 4)
        ) + random.uniform(0, 10)
        logger.warning(
            f"Rate limit hit. Retrying in {backoff_seconds:.1f}s"
        )
        return backoff_seconds

    def get_status(self) -> Dict[str, any]:
        """Get current jigger status."""
        return {
            "platform": self.platform,
            "pattern": self.profile.pattern.value,
            "total_requests": self.request_count,
            "current_burst": self.burst_count,
            "backoff_level": self.backoff_level,
            "error_count": self.error_count,
            "last_delay_ms": self.last_delay,
            "cognitive_pauses": self.cognitive_pauses,
            "base_delay_ms": self.profile.base_delay_ms,
        }


class AdaptiveJiggerShaper:
    """
    Manages multiple jigger clients across platforms.
    Adapts timing based on platform X-RateLimit headers.
    """

    def __init__(self):
        """Initialize adaptive shaper."""
        self.clients: Dict[str, JiggerClient] = {}

        # Load platform profiles
        for platform in JIGGER_PROFILES.keys():
            self.clients[platform] = JiggerClient(platform)

        logger.info("AdaptiveJiggerShaper initialized")

    async def wait_before_request(
        self, platform: str
    ) -> float:
        """
        Wait before platform request.

        Args:
            platform: Target platform

        Returns:
            Delay applied in milliseconds
        """
        if platform not in self.clients:
            logger.warning(f"Unknown platform: {platform}")
            return 0

        client = self.clients[platform]
        return await client.wait_before_request()

    def parse_rate_limit_headers(
        self, headers: Dict[str, str]
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Parse rate limit headers from response.

        Args:
            headers: Response headers

        Returns:
            Tuple of (limit, remaining, reset_seconds)
        """
        headers_lower = {k.lower(): v for k, v in headers.items()}

        limit = None
        remaining = None
        reset = None

        # Standard X-RateLimit headers
        if "x-ratelimit-limit" in headers_lower:
            try:
                limit = int(headers_lower["x-ratelimit-limit"])
            except ValueError:
                pass

        if "x-ratelimit-remaining" in headers_lower:
            try:
                remaining = int(
                    headers_lower["x-ratelimit-remaining"]
                )
            except ValueError:
                pass

        if "x-ratelimit-reset" in headers_lower:
            try:
                reset_timestamp = int(
                    headers_lower["x-ratelimit-reset"]
                )
                now = time.time()
                reset = max(
                    0, int(reset_timestamp - now)
                )
            except ValueError:
                pass

        return limit, remaining, reset

    def adapt_timing(
        self,
        platform: str,
        headers: Dict[str, str],
    ) -> None:
        """
        Adapt timing based on response headers.

        Args:
            platform: Target platform
            headers: Response headers
        """
        if platform not in self.clients:
            return

        limit, remaining, reset = self.parse_rate_limit_headers(
            headers
        )

        client = self.clients[platform]

        # Adapt if approaching limit
        if remaining is not None and limit is not None:
            usage_percent = (
                (limit - remaining) / limit * 100
            )

            if usage_percent > 80:
                logger.warning(
                    f"{platform}: {usage_percent:.0f}% of "
                    f"rate limit used, increasing delays"
                )
                client.backoff_level = min(
                    client.backoff_level + 1, 5
                )

            if remaining < 5:
                logger.error(
                    f"{platform}: Near rate limit ({remaining} "
                    f"remaining), reducing request intensity"
                )
                client.backoff_level = min(
                    client.backoff_level + 2, 5
                )

    def record_request_result(
        self,
        platform: str,
        status_code: int,
        headers: Dict[str, str],
    ) -> None:
        """
        Record request result for platform.

        Args:
            platform: Target platform
            status_code: HTTP status code
            headers: Response headers
        """
        if platform not in self.clients:
            return

        client = self.clients[platform]

        if status_code == 429:
            _, _, reset = self.parse_rate_limit_headers(
                headers
            )
            retry_after = reset or 60
            client.record_rate_limit(retry_after)

        elif status_code >= 500:
            client.record_error()

        elif status_code == 200:
            client.record_success()
            self.adapt_timing(platform, headers)

    def get_all_status(self) -> Dict[str, any]:
        """Get status of all jigger clients."""
        return {
            platform: client.get_status()
            for platform, client in self.clients.items()
        }


# Global adaptive shaper instance
_adaptive_shaper: Optional[AdaptiveJiggerShaper] = None


async def get_adaptive_shaper() -> AdaptiveJiggerShaper:
    """Get or create global adaptive shaper."""
    global _adaptive_shaper

    if _adaptive_shaper is None:
        _adaptive_shaper = AdaptiveJiggerShaper()

    return _adaptive_shaper


async def apply_jigger_wait(platform: str) -> float:
    """
    Apply jigger wait before request.

    Args:
        platform: Target platform

    Returns:
        Delay applied in milliseconds
    """
    shaper = await get_adaptive_shaper()
    return await shaper.wait_before_request(platform)


def record_jigger_result(
    platform: str, status_code: int, headers: Dict[str, str]
) -> None:
    """
    Record request result for jigger adaptation.

    Args:
        platform: Target platform
        status_code: HTTP status code
        headers: Response headers
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        shaper = loop.run_until_complete(get_adaptive_shaper())
        shaper.record_request_result(
            platform, status_code, headers
        )
    except RuntimeError:
        # Event loop not running
        pass
