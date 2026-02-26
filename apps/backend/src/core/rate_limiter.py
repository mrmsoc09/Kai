"""
Rate Limiting Module
Implements in-memory rate limiting for development and testing.
For production, this should be replaced with Redis-backed rate limiting.
"""

import time
from typing import Dict, List, Tuple
from collections import defaultdict


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.

    Tracks requests per key and enforces rate limits.
    Perfect for development and testing.
    """

    def __init__(self):
        """Initialize the rate limiter."""
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(
        self,
        key: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> bool:
        """
        Check if request is allowed under rate limit.

        Uses sliding window algorithm:
        1. Remove requests older than window
        2. Check if we're under limit
        3. Add current request if allowed

        Args:
            key: Unique identifier (user_id, IP address, endpoint, etc.)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = time.time()
        window_start = now - window_seconds

        # Get existing requests for this key
        request_times = self.requests[key]

        # Remove old requests (older than window)
        request_times[:] = [
            req_time for req_time in request_times
            if req_time > window_start
        ]

        # Check if under limit
        if len(request_times) < max_requests:
            # Add current request
            request_times.append(now)
            return True

        # Over limit
        return False

    def get_reset_time(self, key: str, window_seconds: int = 60) -> float:
        """
        Get time (in seconds) until rate limit resets for this key.

        Returns:
            Seconds until oldest request falls out of window, or 0 if no active requests
        """
        if key not in self.requests or not self.requests[key]:
            return 0

        oldest_request = self.requests[key][0]
        reset_time = (oldest_request + window_seconds) - time.time()
        return max(0, reset_time)

    def clear_key(self, key: str) -> None:
        """Clear all tracked requests for a key."""
        if key in self.requests:
            del self.requests[key]

    def clear_all(self) -> None:
        """Clear all tracked requests (useful for testing)."""
        self.requests.clear()

    def get_stats(self, key: str) -> Dict[str, any]:
        """Get current stats for a key."""
        request_times = self.requests.get(key, [])
        return {
            "key": key,
            "request_count": len(request_times),
            "oldest_request": request_times[0] if request_times else None,
            "newest_request": request_times[-1] if request_times else None,
        }


# Global instance
rate_limiter = InMemoryRateLimiter()


# Default rate limits per endpoint pattern
DEFAULT_RATE_LIMITS = {
    # Authentication endpoints (very strict)
    "/auth/login": (5, 300),  # 5 requests per 5 minutes (360 seconds)
    "/auth/logout": (20, 60),  # 20 requests per minute
    "/auth/refresh": (20, 60),  # 20 requests per minute

    # Heavy compute endpoints (restrictive)
    "/planner": (10, 60),  # 10 per minute
    "/orchestrator/queue_scan": (5, 60),  # 5 per minute
    "/patches/suggest": (10, 60),  # 10 per minute

    # Standard endpoints (moderate)
    "/reports/validate": (50, 60),  # 50 per minute
    "/reports/render": (50, 60),  # 50 per minute
    "/findings/validate": (50, 60),  # 50 per minute
    "/embeddings/search": (50, 60),  # 50 per minute

    # Read-only endpoints (lenient)
    "/findings": (200, 60),  # 200 per minute
    "/programs": (200, 60),  # 200 per minute
    "/knowledge": (200, 60),  # 200 per minute

    # Health/status (no limit)
    # These are handled separately in middleware
}


def get_rate_limit_for_endpoint(path: str) -> Tuple[int, int]:
    """
    Get rate limit (max_requests, window_seconds) for an endpoint.

    Returns:
        (max_requests, window_seconds) or default (100, 60) if not found
    """
    for pattern, limit in DEFAULT_RATE_LIMITS.items():
        if pattern in path:
            return limit

    # Default fallback
    return (100, 60)
