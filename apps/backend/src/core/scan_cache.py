"""
Redis-backed scan cache with in-process LRU fallback.

Caches Vault secret fetches, MISP/Cortex enrichment, Shodan/Censys/VirusTotal
API responses, and NVD CVE data so each scan minimises redundant external calls.

Usage:
    from .scan_cache import get_scan_cache, cached_call

    cache = get_scan_cache()
    value = cache.get("misp", ioc_value)
    if value is None:
        value = await _fetch_from_misp(ioc_value)
        cache.set("misp", ioc_value, value)

    # Or with the decorator helper:
    result = await cached_call("shodan", target, _fetch_shodan, target)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL table (seconds) — 0 means no caching for that namespace
# ---------------------------------------------------------------------------
CACHE_TTL: dict[str, int] = {
    "vault":       1800,   # 30 min — Vault secret fetches
    "misp":        3600,   # 1 hr  — MISP IOC enrichment / event lookups
    "cortex":      3600,   # 1 hr  — Cortex analyzer results
    "wazuh":        300,   # 5 min — Wazuh alert / anomaly queries
    "shodan":       900,   # 15 min — Shodan queries
    "censys":       900,   # 15 min — Censys queries
    "virustotal":   900,   # 15 min — VirusTotal lookups
    "nvd":         3600,   # 1 hr  — NVD CVE data
    "thehive":      300,   # 5 min — TheHive case lists
    "shuffle":      120,   # 2 min — Shuffle status checks
    "llm":            0,   # disabled by default — LLM completions not cached
}

_DEFAULT_TTL = 900  # fallback for unknown namespaces


# ---------------------------------------------------------------------------
# In-process LRU (fallback when Redis is unavailable)
# ---------------------------------------------------------------------------

class _LRUFallback:
    """Thread-safe LRU cache with per-entry TTL, used when Redis is down."""

    def __init__(self, maxsize: int = 2048) -> None:
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        value, expires = self._store[key]
        if expires and time.monotonic() > expires:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.monotonic() + ttl if ttl else 0.0)
        if len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def flush_prefix(self, prefix: str) -> None:
        to_del = [k for k in self._store if k.startswith(prefix)]
        for k in to_del:
            del self._store[k]


# ---------------------------------------------------------------------------
# Main cache service
# ---------------------------------------------------------------------------

class ScanCacheService:
    """
    Scan-scoped cache backed by Redis with automatic in-process LRU fallback.

    Key structure: ``k1:scan_cache:{namespace}:{sha256_prefix}``
    """

    _KEY_PREFIX = "k1:scan_cache:"

    def __init__(self) -> None:
        self._redis: Optional[Any] = None
        self._fallback = _LRUFallback()
        self._redis_dead = False
        self._connect_redis()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _connect_redis(self) -> None:
        try:
            import redis as _r

            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            password = os.getenv("REDIS_PASSWORD") or None
            db = int(os.getenv("REDIS_DB", "0"))

            if password:
                url = f"redis://:{password}@{host}:{port}/{db}"
            else:
                url = f"redis://{host}:{port}/{db}"

            client = _r.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._redis = client
            logger.info("ScanCacheService: Redis connected (%s:%s db=%s)", host, port, db)
        except Exception as exc:
            logger.warning(
                "ScanCacheService: Redis unavailable (%s) — using in-process LRU", exc
            )
            self._redis_dead = True

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _make_key(self, namespace: str, raw_key: str) -> str:
        h = hashlib.sha256(raw_key.encode()).hexdigest()[:24]
        return f"{self._KEY_PREFIX}{namespace}:{h}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, namespace: str, raw_key: str) -> Optional[Any]:
        """Return cached value or None."""
        key = self._make_key(namespace, raw_key)
        if self._redis and not self._redis_dead:
            try:
                raw = self._redis.get(key)
                if raw is not None:
                    return json.loads(raw)
                return None
            except Exception as exc:
                logger.debug("ScanCache Redis.get failed: %s — falling back", exc)
                self._redis_dead = True
        return self._fallback.get(key)

    def set(
        self,
        namespace: str,
        raw_key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Store value. Uses namespace TTL table if *ttl* not specified."""
        if ttl is None:
            ttl = CACHE_TTL.get(namespace, _DEFAULT_TTL)
        if ttl == 0:
            return  # caching disabled for this namespace

        key = self._make_key(namespace, raw_key)
        serialized = json.dumps(value, default=str)

        if self._redis and not self._redis_dead:
            try:
                self._redis.setex(key, ttl, serialized)
                return
            except Exception as exc:
                logger.debug("ScanCache Redis.set failed: %s — falling back", exc)
                self._redis_dead = True
        self._fallback.set(key, value, ttl)

    def invalidate(self, namespace: str, raw_key: str) -> None:
        """Remove a single cache entry."""
        key = self._make_key(namespace, raw_key)
        if self._redis and not self._redis_dead:
            try:
                self._redis.delete(key)
                return
            except Exception as exc:
                logger.debug("ScanCache Redis.delete failed: %s", exc)
        self._fallback.delete(key)

    def invalidate_namespace(self, namespace: str) -> None:
        """Purge all keys for a namespace (e.g. at mission end)."""
        prefix = f"{self._KEY_PREFIX}{namespace}:"
        if self._redis and not self._redis_dead:
            try:
                cursor: Any = 0
                while True:
                    cursor, keys = self._redis.scan(
                        cursor=cursor, match=f"{prefix}*", count=200
                    )
                    if keys:
                        self._redis.delete(*keys)
                    if cursor == 0:
                        break
                return
            except Exception as exc:
                logger.debug("ScanCache Redis.scan failed: %s", exc)
        self._fallback.flush_prefix(prefix)

    def ping(self) -> bool:
        """Returns True if Redis backend is reachable."""
        if self._redis and not self._redis_dead:
            try:
                self._redis.ping()
                return True
            except Exception:
                self._redis_dead = True
        return False


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------

async def cached_call(
    namespace: str,
    raw_key: str,
    fn: Callable,
    *args: Any,
    ttl: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    """
    Call *fn* with *args*/*kwargs*, caching the result under *namespace*:*raw_key*.
    Supports both sync and async callables.
    """
    import asyncio

    cache = get_scan_cache()
    cached = cache.get(namespace, raw_key)
    if cached is not None:
        return cached

    if asyncio.iscoroutinefunction(fn):
        result = await fn(*args, **kwargs)
    else:
        result = fn(*args, **kwargs)

    if result is not None:
        cache.set(namespace, raw_key, result, ttl=ttl)
    return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_CACHE: Optional[ScanCacheService] = None


def get_scan_cache() -> ScanCacheService:
    """Return the process-level ScanCacheService singleton."""
    global _CACHE
    if _CACHE is None:
        _CACHE = ScanCacheService()
    return _CACHE


def reset_scan_cache() -> None:
    """Force re-initialisation (for tests)."""
    global _CACHE
    _CACHE = None
