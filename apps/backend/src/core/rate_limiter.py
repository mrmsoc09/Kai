"""
Rate Limiting Module
In-memory limiter for dev/test; Redis sliding-window limiter for production.
Automatically selects the Redis backend when REDIS_URL is configured.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List, Tuple


class InMemoryRateLimiter:
    """
    Sliding-window in-memory rate limiter.
    Suitable for single-process dev/test only — state is lost on restart.
    """

    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        now = time.time()
        window_start = now - window_seconds
        request_times = self.requests[key]
        request_times[:] = [t for t in request_times if t > window_start]
        if len(request_times) < max_requests:
            request_times.append(now)
            return True
        return False

    def get_reset_time(self, key: str, window_seconds: int = 60) -> float:
        if key not in self.requests or not self.requests[key]:
            return 0
        oldest = self.requests[key][0]
        return max(0, (oldest + window_seconds) - time.time())

    def get_count(self, key: str, window_seconds: int = 60) -> int:
        now = time.time()
        window_start = now - window_seconds
        return len([t for t in self.requests.get(key, []) if t > window_start])

    def clear_key(self, key: str) -> None:
        if key in self.requests:
            del self.requests[key]

    def clear_all(self) -> None:
        self.requests.clear()

    def get_stats(self, key: str) -> dict:
        request_times = self.requests.get(key, [])
        return {
            "key": key,
            "request_count": len(request_times),
            "oldest_request": request_times[0] if request_times else None,
            "newest_request": request_times[-1] if request_times else None,
        }


class RedisRateLimiter:
    """
    Distributed sliding-window rate limiter backed by Redis sorted sets.
    Safe for multi-instance deployments; state survives restarts.
    """

    def __init__(self, redis_url: str):
        import redis as _redis  # sync redis client
        self._redis = _redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)

    def is_allowed(self, key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        now = time.time()
        window_start = now - window_seconds
        rkey = f"rl:{key}"
        try:
            with self._redis.pipeline() as pipe:
                pipe.zremrangebyscore(rkey, 0, window_start)
                pipe.zcard(rkey)
                results = pipe.execute()
            count = results[1]
            if count >= max_requests:
                return False
            self._redis.zadd(rkey, {str(now): now})
            self._redis.expire(rkey, window_seconds + 10)
            return True
        except Exception:
            # Redis unavailable — fail open to avoid blocking all requests
            return True

    def get_reset_time(self, key: str, window_seconds: int = 60) -> float:
        rkey = f"rl:{key}"
        try:
            oldest = self._redis.zrange(rkey, 0, 0, withscores=True)
            if not oldest:
                return 0
            oldest_score: float = oldest[0][1]
            return max(0, (oldest_score + window_seconds) - time.time())
        except Exception:
            return 0

    def get_count(self, key: str, window_seconds: int = 60) -> int:
        now = time.time()
        rkey = f"rl:{key}"
        try:
            return self._redis.zcount(rkey, now - window_seconds, "+inf")
        except Exception:
            return 0

    def clear_key(self, key: str) -> None:
        try:
            self._redis.delete(f"rl:{key}")
        except Exception:
            pass

    def clear_all(self) -> None:
        pass  # not safe to implement for shared Redis


def _build_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            limiter = RedisRateLimiter(redis_url)
            # Smoke-test the connection
            limiter._redis.ping()
            return limiter
        except Exception:
            pass  # Fall through to in-memory
    return InMemoryRateLimiter()


# Global instance — auto-selects Redis when REDIS_URL is present
rate_limiter: InMemoryRateLimiter | RedisRateLimiter = _build_rate_limiter()


# Default rate limits per endpoint pattern
DEFAULT_RATE_LIMITS: dict[str, tuple[int, int]] = {
    # Authentication endpoints (very strict)
    "/auth/login": (5, 300),      # 5 requests per 5 minutes
    "/auth/token": (5, 300),      # 5 requests per 5 minutes — same as /auth/login
    "/auth/logout": (20, 60),     # 20 requests per minute
    "/auth/refresh": (20, 60),    # 20 requests per minute
    # Heavy compute endpoints (restrictive)
    "/planner": (10, 60),
    "/orchestrator/queue_scan": (5, 60),
    "/patches/suggest": (10, 60),
    # Standard endpoints (moderate)
    "/reports/validate": (50, 60),
    "/reports/render": (50, 60),
    "/findings/validate": (50, 60),
    "/embeddings/search": (50, 60),
    # Read-only endpoints (lenient)
    "/findings": (200, 60),
    "/programs": (200, 60),
    "/knowledge": (200, 60),
}


def get_rate_limit_for_endpoint(path: str) -> Tuple[int, int]:
    """Return (max_requests, window_seconds) for the given path."""
    for pattern, limit in DEFAULT_RATE_LIMITS.items():
        if pattern in path:
            return limit
    return (100, 60)
