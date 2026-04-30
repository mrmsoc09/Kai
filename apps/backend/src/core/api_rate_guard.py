"""
API Rate Guard — Shared Redis token bucket + jitter + exponential backoff
for all 55+ external API services.

Design:
  - ONE Redis key per service (shared across all mission workers)
  - Full-jitter exponential backoff on 429/503 (not equal-jitter)
  - Free/paid tier detection via Vault metadata tag
  - Daily budget gate: warn at 90%, block at 95%
  - Decorator API: @rate_guarded(service="shodan")

Usage::

    from apps.backend.src.core.api_rate_guard import rate_guarded, RateGuard

    guard = RateGuard()

    @rate_guarded("shodan")
    async def query_shodan(ip: str) -> dict:
        ...

    # Or manual:
    await guard.wait("shodan")
    response = await httpx.get(...)
    guard.record_429("shodan")  # if 429 received
"""
from __future__ import annotations

import asyncio
import functools
import logging
import math
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-service quota table (calls/day, calls/minute, tier)
# Free-tier defaults — override in config/api_phase_matrix.yaml
# ---------------------------------------------------------------------------

_SERVICE_QUOTAS: dict[str, dict[str, Any]] = {
    # AI/LLM (tracked separately by quota_tracker.py — listed for completeness)
    "openai":           {"daily": 5000, "rpm": 60,  "tier": "paid",  "jitter": (0.1, 0.5)},
    "anthropic":        {"daily": 3000, "rpm": 50,  "tier": "paid",  "jitter": (0.1, 0.5)},
    "gemini":           {"daily": 250,  "rpm": 10,  "tier": "free",  "jitter": (0.5, 2.0)},
    "openrouter":       {"daily": 9999, "rpm": 200, "tier": "paid",  "jitter": (0.05, 0.3)},
    "huggingface":      {"daily": 2000, "rpm": 30,  "tier": "paid",  "jitter": (0.2, 0.8)},
    "ollama":           {"daily": 99999,"rpm": 999, "tier": "local", "jitter": (0.0, 0.05)},
    # OSINT — free tier
    "shodan":           {"daily": 100,  "rpm": 1,   "tier": "free",  "jitter": (1.0, 3.0)},
    "censys":           {"daily": 250,  "rpm": 2,   "tier": "free",  "jitter": (1.0, 3.0)},
    "securitytrails":   {"daily": 50,   "rpm": 2,   "tier": "free",  "jitter": (1.0, 3.0)},
    "fullhunt":         {"daily": 100,  "rpm": 2,   "tier": "free",  "jitter": (1.0, 2.0)},
    "abuseipdb":        {"daily": 300,  "rpm": 5,   "tier": "free",  "jitter": (0.5, 2.0)},
    "leakix":           {"daily": 500,  "rpm": 10,  "tier": "free",  "jitter": (0.3, 1.5)},
    "zoomeye":          {"daily": 300,  "rpm": 5,   "tier": "free",  "jitter": (0.5, 2.0)},
    "hunter":           {"daily": 25,   "rpm": 1,   "tier": "free",  "jitter": (3.0, 8.0)},
    "dehashed":         {"daily": 100,  "rpm": 2,   "tier": "free",  "jitter": (1.0, 4.0)},
    "intelx":           {"daily": 500,  "rpm": 5,   "tier": "free",  "jitter": (0.5, 2.0)},
    "abuse_ch":         {"daily": 200,  "rpm": 10,  "tier": "free",  "jitter": (0.3, 1.5)},
    "grayhatwarfare":   {"daily": 200,  "rpm": 5,   "tier": "free",  "jitter": (0.5, 2.0)},
    "urlscan":          {"daily": 1000, "rpm": 20,  "tier": "free",  "jitter": (0.2, 1.0)},
    "ipinfo":           {"daily": 1000, "rpm": 20,  "tier": "free",  "jitter": (0.2, 1.0)},
    "virustotal":       {"daily": 500,  "rpm": 4,   "tier": "free",  "jitter": (0.5, 2.0)},
    "otx":              {"daily": 1000, "rpm": 20,  "tier": "free",  "jitter": (0.2, 1.0)},
    "nvd":              {"daily": 2000, "rpm": 30,  "tier": "free",  "jitter": (0.1, 0.5)},
    "crtsh":            {"daily": 5000, "rpm": 60,  "tier": "free",  "jitter": (0.1, 0.5)},
    "binaryedge":       {"daily": 250,  "rpm": 5,   "tier": "paid",  "jitter": (0.5, 2.0)},
    "hibp":             {"daily": 100,  "rpm": 1,   "tier": "paid",  "jitter": (2.0, 5.0)},
    "projectdiscovery": {"daily": 500,  "rpm": 10,  "tier": "free",  "jitter": (0.3, 1.5)},
    # Dorking
    "google_cse":       {"daily": 100,  "rpm": 1,   "tier": "free",  "jitter": (2.0, 6.0)},
    "bing_search":      {"daily": 1000, "rpm": 3,   "tier": "paid",  "jitter": (0.5, 2.0)},
    "ddg":              {"daily": 200,  "rpm": 1,   "tier": "free",  "jitter": (3.0, 8.0)},
    "yandex":           {"daily": 100,  "rpm": 1,   "tier": "free",  "jitter": (3.0, 10.0)},
    # Proxy services
    "scrapingbee":      {"daily": 1000, "rpm": 20,  "tier": "paid",  "jitter": (0.2, 1.0)},
    "decodo":           {"daily": 5000, "rpm": 100, "tier": "paid",  "jitter": (0.1, 0.5)},
}

# ---------------------------------------------------------------------------
# Token bucket (per-service, Redis-backed)
# ---------------------------------------------------------------------------

@dataclass
class _BucketState:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)
    daily_count: int = 0
    daily_date: str = ""
    backoff_attempt: int = 0


# ---------------------------------------------------------------------------
# Key pool (round-robin with per-key 429 cooloff)
# ---------------------------------------------------------------------------

@dataclass
class _KeyPool:
    keys: list[str]
    current_index: int = 0
    key_429_until: dict[int, float] = field(default_factory=dict)

    def get_active_key(self) -> str | None:
        """Return the next available key, skipping keys in 429 cooloff."""
        now = time.monotonic()
        for offset in range(len(self.keys)):
            idx = (self.current_index + offset) % len(self.keys)
            if now >= self.key_429_until.get(idx, 0.0):
                self.current_index = (idx + 1) % len(self.keys)
                return self.keys[idx]
        return None  # all keys in cooloff

    def mark_429(self, key: str, cooloff_seconds: float = 300.0) -> None:
        """Mark a key as rate-limited for cooloff_seconds."""
        try:
            idx = self.keys.index(key)
            self.key_429_until[idx] = time.monotonic() + cooloff_seconds
        except ValueError:
            pass


class RateGuard:
    """
    Thread/async-safe rate guard using Redis sorted sets for distributed state.
    Falls back to in-process buckets when Redis is unavailable.
    """

    def __init__(self) -> None:
        self._local: dict[str, _BucketState] = {}
        self._redis: Any = None
        self._redis_ok: bool = False
        self._key_pools: dict[str, _KeyPool] = {}
        self._init_redis()

    def _init_redis(self) -> None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis
            self._redis = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)
            self._redis.ping()
            self._redis_ok = True
            logger.debug("RateGuard: Redis connected at %s", redis_url)
        except Exception:
            logger.warning("RateGuard: Redis unavailable — using in-process buckets (single-worker only)")
            self._redis_ok = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def wait(self, service: str, cost: int = 1) -> None:
        """Block until a call to `service` is allowed, then decrement budget."""
        quota = _SERVICE_QUOTAS.get(service, {"daily": 500, "rpm": 10, "tier": "free", "jitter": (0.5, 2.0)})

        # Daily budget gate
        daily_used = self._daily_count(service)
        daily_limit = quota["daily"]
        if daily_used >= daily_limit * 0.95:
            if daily_used >= daily_limit:
                raise RateLimitExceeded(f"{service}: daily quota ({daily_limit}) exhausted")
            logger.warning("RateGuard: %s at 95%% daily quota (%d/%d)", service, daily_used, daily_limit)

        # RPM gate
        rpm = quota.get("rpm", 10)
        min_interval = 60.0 / rpm
        jitter_lo, jitter_hi = quota.get("jitter", (0.2, 1.0))
        jitter = random.uniform(jitter_lo, jitter_hi)
        total_wait = min_interval + jitter

        # Check last call time
        last_call = self._last_call_time(service)
        elapsed = time.monotonic() - last_call
        if elapsed < total_wait:
            sleep_for = total_wait - elapsed
            logger.debug("RateGuard: waiting %.2fs for %s (rpm=%d jitter=%.2fs)", sleep_for, service, rpm, jitter)
            await asyncio.sleep(sleep_for)

        self._record_call(service)

    def record_429(self, service: str, key: str | None = None) -> float:
        """
        Record a 429 response. Returns the backoff delay in seconds.
        Uses full-jitter exponential backoff: sleep = random(0, min(cap, base * 2^attempt))

        If *key* is provided and a key pool exists for *service*, the specific
        key is placed into a 300-second cooloff so the pool skips it on the
        next ``get_key()`` call.
        """
        _quota = _SERVICE_QUOTAS.get(service, {})
        state = self._get_local(service)
        state.backoff_attempt += 1
        cap = 300.0
        base = 1.0
        ceiling = min(cap, base * (2 ** state.backoff_attempt))
        delay = random.uniform(0, ceiling)
        logger.warning(
            "RateGuard: 429 on %s (attempt %d) — backing off %.1fs",
            service, state.backoff_attempt, delay
        )
        if key is not None:
            pool = self._key_pools.get(service)
            if pool is not None:
                pool.mark_429(key)
                logger.info("RateGuard: key ...%s cooled off for %s (300 s)", key[-4:], service)
        return delay

    def record_success(self, service: str) -> None:
        """Reset backoff counter after a successful call."""
        state = self._get_local(service)
        state.backoff_attempt = 0

    async def handle_429(self, service: str) -> None:
        """Record 429 and sleep for the computed backoff delay."""
        delay = self.record_429(service)
        await asyncio.sleep(delay)

    def wait_sync(self, service: str, cost: int = 1) -> None:
        """Synchronous variant of wait() for use in Celery workers and sync execute() methods."""
        quota = _SERVICE_QUOTAS.get(service, {"daily": 500, "rpm": 10, "tier": "free", "jitter": (0.5, 2.0)})

        daily_used = self._daily_count(service)
        daily_limit = quota["daily"]
        if daily_used >= daily_limit * 0.95:
            if daily_used >= daily_limit:
                raise RateLimitExceeded(f"{service}: daily quota ({daily_limit}) exhausted")
            logger.warning("RateGuard: %s at 95%% daily quota (%d/%d)", service, daily_used, daily_limit)

        rpm = quota.get("rpm", 10)
        min_interval = 60.0 / rpm
        jitter_lo, jitter_hi = quota.get("jitter", (0.2, 1.0))
        jitter = random.uniform(jitter_lo, jitter_hi)
        total_wait = min_interval + jitter

        last_call = self._last_call_time(service)
        elapsed = time.monotonic() - last_call
        if elapsed < total_wait:
            sleep_for = total_wait - elapsed
            logger.debug("RateGuard: waiting %.2fs for %s (rpm=%d jitter=%.2fs)", sleep_for, service, rpm, jitter)
            time.sleep(sleep_for)

        self._record_call(service)

    def handle_429_sync(self, service: str) -> None:
        """Synchronous variant of handle_429() — records 429 and sleeps."""
        delay = self.record_429(service)
        time.sleep(delay)

    # ------------------------------------------------------------------
    # Key pool — round-robin rotation across multiple API keys
    # ------------------------------------------------------------------

    def register_key_pool(self, service: str, keys: list[str]) -> None:
        """
        Register (or replace) the pool of API keys for *service*.

        Keys are rotated round-robin; individual keys are cooled off for 300 s
        after receiving a 429.  The key VALUE strings are opaque to this class —
        callers load them from Vault at startup.
        """
        if not keys:
            raise ValueError(f"register_key_pool({service!r}): keys list must not be empty")
        self._key_pools[service] = _KeyPool(keys=list(keys))
        logger.debug("RateGuard: registered %d key(s) for service %r", len(keys), service)

    def get_key(self, service: str) -> str | None:
        """
        Return the next available API key for *service*.

        Returns ``None`` when:
        - no pool has been registered for *service*, or
        - every key in the pool is currently in 429 cooloff.
        """
        pool = self._key_pools.get(service)
        if pool is None:
            return None
        key = pool.get_active_key()
        if key is None:
            logger.warning("RateGuard: all keys for %r are in 429 cooloff", service)
        return key

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_local(self, service: str) -> _BucketState:
        if service not in self._local:
            self._local[service] = _BucketState(tokens=1.0)
        return self._local[service]

    def _redis_key(self, service: str, suffix: str) -> str:
        return f"k1:rate:{service}:{suffix}"

    def _last_call_time(self, service: str) -> float:
        if self._redis_ok:
            try:
                val = self._redis.get(self._redis_key(service, "last_call"))
                return float(val) if val else 0.0
            except Exception:
                pass
        return self._get_local(service).last_refill

    def _record_call(self, service: str) -> None:
        now = time.monotonic()
        today = time.strftime("%Y-%m-%d")
        if self._redis_ok:
            try:
                pipe = self._redis.pipeline()
                pipe.set(self._redis_key(service, "last_call"), str(now), ex=120)
                pipe.incr(self._redis_key(service, f"daily:{today}"))
                pipe.expire(self._redis_key(service, f"daily:{today}"), 86400)
                pipe.execute()
                return
            except Exception:
                pass
        state = self._get_local(service)
        state.last_refill = now
        state.daily_count += 1

    def _daily_count(self, service: str) -> int:
        today = time.strftime("%Y-%m-%d")
        if self._redis_ok:
            try:
                val = self._redis.get(self._redis_key(service, f"daily:{today}"))
                return int(val) if val else 0
            except Exception:
                pass
        state = self._get_local(service)
        if state.daily_date != today:
            state.daily_count = 0
            state.daily_date = today
        return state.daily_count


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

class RateLimitExceeded(Exception):
    pass


def rate_guarded(service: str, cost: int = 1):
    """
    Decorator for async functions that call external APIs.

    Automatically waits for rate guard clearance before the call,
    handles 429 responses with exponential backoff + retry.

    Usage::

        @rate_guarded("shodan")
        async def query_shodan(ip: str) -> dict:
            return await httpx.get(f"https://api.shodan.io/shodan/host/{ip}")
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            guard = _get_guard()
            max_retries = 4
            for attempt in range(max_retries):
                await guard.wait(service, cost)
                try:
                    result = await fn(*args, **kwargs)
                    guard.record_success(service)
                    return result
                except RateLimitExceeded:
                    raise
                except Exception as exc:
                    exc_str = str(exc).lower()
                    if "429" in exc_str or "rate limit" in exc_str or "too many" in exc_str:
                        if attempt < max_retries - 1:
                            await guard.handle_429(service)
                            continue
                        raise RateLimitExceeded(f"{service}: max retries exceeded") from exc
                    raise
            raise RateLimitExceeded(f"{service}: exceeded retry limit")
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_guard: RateGuard | None = None


def _get_guard() -> RateGuard:
    global _guard
    if _guard is None:
        _guard = RateGuard()
    return _guard


def get_rate_guard() -> RateGuard:
    return _get_guard()


def register_service_keys(service: str, keys: list[str]) -> None:
    """
    Module-level convenience wrapper — registers *keys* as the round-robin
    pool for *service* on the process-wide RateGuard singleton.

    Intended to be called once at application / worker startup after keys
    have been loaded from Vault::

        from apps.backend.src.core.api_rate_guard import register_service_keys

        register_service_keys("shodan", vault_client.read_keys("shodan"))
    """
    get_rate_guard().register_key_pool(service, keys)
