"""
Intelligence Cache Layer — Fast Retrieval for Active Missions
===============================================================
In-memory LRU cache with TTL-based eviction on top of the MemoryStore.

Purpose:
  - Fast lookups during active mission execution (avoid disk reads)
  - Domain/vuln-type/tech-stack/endpoint-pattern indexed access
  - Promotion trigger logic (short → mid → long → strategic)

Cache keys:
  domain:<domain>          → list[memory_id]
  vuln:<vuln_type>         → list[memory_id]
  tech:<tech_stack_item>   → list[memory_id]
  endpoint:<pattern>       → list[memory_id]

TTL policy:
  - Strategic entries: no eviction (permanent cache)
  - Long-term entries: 24h TTL
  - Mid-term entries: 1h TTL
  - Short-term: 5 min TTL (usually evicted by phase completion)

Promotion triggers:
  - Cache miss on LONG_TERM for a known mid-term entry → auto-promote candidate
  - Strategic entries always pre-warmed into cache on startup

Cache metrics tracked:
  - hits, misses, evictions, promotions_triggered
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from .intelligence_memory import (
    MemoryEntry,
    MemoryManager,
    MemoryScope,
    MemoryType,
    ValidationStatus,
    get_memory_manager,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTL per scope (seconds)
# ---------------------------------------------------------------------------

_SCOPE_TTL: dict[MemoryScope, float] = {
    MemoryScope.SHORT_TERM: 300.0,      # 5 minutes
    MemoryScope.MID_TERM: 3600.0,       # 1 hour
    MemoryScope.LONG_TERM: 86400.0,     # 24 hours
    MemoryScope.STRATEGIC: float("inf"),  # permanent
}

_DEFAULT_CACHE_CAPACITY = 2000  # max entries per index key bucket


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------


@dataclass
class CacheEntry:
    memory_id: str
    scope: MemoryScope
    memory_type: MemoryType
    tags: list[str]
    confidence_score: float
    inserted_at: float = field(default_factory=time.time)
    hit_count: int = 0

    def is_expired(self) -> bool:
        ttl = _SCOPE_TTL[self.scope]
        if ttl == float("inf"):
            return False
        return (time.time() - self.inserted_at) > ttl


# ---------------------------------------------------------------------------
# Index bucket (one per key type)
# ---------------------------------------------------------------------------


class _IndexBucket:
    """
    Thread-safe list of CacheEntries for a given index key.
    Evicts expired entries on access.
    """

    def __init__(self, capacity: int = _DEFAULT_CACHE_CAPACITY) -> None:
        self._entries: list[CacheEntry] = []
        self._lock = threading.Lock()
        self._capacity = capacity

    def add(self, entry: CacheEntry) -> None:
        with self._lock:
            # Avoid duplicates
            existing_ids = {e.memory_id for e in self._entries}
            if entry.memory_id in existing_ids:
                return
            self._entries.append(entry)
            # Evict oldest if over capacity
            if len(self._entries) > self._capacity:
                self._entries = self._entries[-self._capacity:]

    def get_valid(self) -> list[CacheEntry]:
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if not e.is_expired()]
            evicted = before - len(self._entries)
            for e in self._entries:
                e.hit_count += 1
            return list(self._entries), evicted

    def count(self) -> int:
        with self._lock:
            return len(self._entries)


# ---------------------------------------------------------------------------
# Intelligence Cache
# ---------------------------------------------------------------------------


class IntelligenceCache:
    """
    Multi-index in-memory cache for the intelligence memory system.

    Indexes:
      - by domain
      - by vuln_type (from tags)
      - by tech_stack (from target_fingerprint.tech_stack)
      - by endpoint pattern (from tags or target_fingerprint.services)

    Usage::

        cache = IntelligenceCache()
        cache.index_entry(entry)

        results = cache.lookup_by_domain("example.com")
        results = cache.lookup_by_vuln_type("sqli")
        results = cache.lookup_by_tech_stack("nginx")
    """

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or get_memory_manager()
        self._domain_idx: dict[str, _IndexBucket] = {}
        self._vuln_idx: dict[str, _IndexBucket] = {}
        self._tech_idx: dict[str, _IndexBucket] = {}
        self._endpoint_idx: dict[str, _IndexBucket] = {}
        self._lock = threading.Lock()
        self._metrics: dict[str, int] = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "promotions_triggered": 0,
            "indexed": 0,
        }

    # -- Indexing --------------------------------------------------------------

    def index_entry(self, entry: MemoryEntry) -> None:
        """Add a memory entry to all applicable indexes."""
        ce = CacheEntry(
            memory_id=entry.memory_id,
            scope=entry.scope,
            memory_type=entry.memory_type,
            tags=entry.tags,
            confidence_score=entry.confidence_score,
        )

        domain = entry.target_fingerprint.domain
        tech_stack = entry.target_fingerprint.tech_stack
        services = entry.target_fingerprint.services
        tags = entry.tags

        with self._lock:
            if domain:
                bucket = self._domain_idx.setdefault(domain, _IndexBucket())
                bucket.add(ce)

            # vuln_type tags
            for tag in tags:
                if any(tag.startswith(prefix) for prefix in ("xss", "sqli", "ssrf", "rce", "lfi", "ssti", "idor", "xxe")):
                    bucket = self._vuln_idx.setdefault(tag, _IndexBucket())
                    bucket.add(ce)
                # endpoint patterns from tags like "endpoint:/api/v2/..."
                if tag.startswith("endpoint:"):
                    ep = tag[len("endpoint:"):]
                    bucket = self._endpoint_idx.setdefault(ep, _IndexBucket())
                    bucket.add(ce)

            for tech in tech_stack:
                bucket = self._tech_idx.setdefault(tech.lower(), _IndexBucket())
                bucket.add(ce)

            for svc in services:
                bucket = self._endpoint_idx.setdefault(svc, _IndexBucket())
                bucket.add(ce)

            self._metrics["indexed"] += 1

    def index_entries(self, entries: list[MemoryEntry]) -> None:
        for e in entries:
            self.index_entry(e)

    # -- Lookup ----------------------------------------------------------------

    def lookup_by_domain(self, domain: str) -> list[CacheEntry]:
        return self._lookup(self._domain_idx, domain)

    def lookup_by_vuln_type(self, vuln_type: str) -> list[CacheEntry]:
        return self._lookup(self._vuln_idx, vuln_type.lower())

    def lookup_by_tech_stack(self, tech: str) -> list[CacheEntry]:
        return self._lookup(self._tech_idx, tech.lower())

    def lookup_by_endpoint(self, endpoint_pattern: str) -> list[CacheEntry]:
        return self._lookup(self._endpoint_idx, endpoint_pattern)

    def _lookup(self, idx: dict[str, _IndexBucket], key: str) -> list[CacheEntry]:
        with self._lock:
            bucket = idx.get(key)
        if not bucket:
            with self._lock:
                self._metrics["misses"] += 1
            return []
        entries, evicted = bucket.get_valid()
        with self._lock:
            self._metrics["evictions"] += evicted
            if entries:
                self._metrics["hits"] += 1
            else:
                self._metrics["misses"] += 1
        return entries

    # -- Full entry resolution --------------------------------------------------

    def resolve(self, cache_entries: list[CacheEntry]) -> list[MemoryEntry]:
        """Resolve CacheEntries to full MemoryEntry objects via the MemoryManager."""
        resolved: list[MemoryEntry] = []
        for ce in cache_entries:
            entry = self._manager.get(ce.memory_id)
            if entry:
                resolved.append(entry)
        return resolved

    # -- Promotion triggers -----------------------------------------------------

    def check_promotion_candidates(self) -> list[str]:
        """
        Identify mid-term entries that should be promoted to long-term.
        Returns list of memory_ids eligible for promotion.
        """
        candidates: list[str] = []
        # Look at high-confidence, high-hit mid-term entries
        with self._lock:
            all_buckets = list(self._domain_idx.values()) + list(self._vuln_idx.values())

        for bucket in all_buckets:
            with bucket._lock:
                for ce in bucket._entries:
                    if (
                        ce.scope == MemoryScope.MID_TERM
                        and ce.confidence_score >= 0.75
                        and ce.hit_count >= 3  # accessed at least 3 times
                    ):
                        candidates.append(ce.memory_id)

        with self._lock:
            self._metrics["promotions_triggered"] += len(candidates)
        return list(set(candidates))

    # -- Warm-up ---------------------------------------------------------------

    def warm_from_manager(
        self,
        scope: MemoryScope = MemoryScope.STRATEGIC,
        limit: int = 500,
    ) -> int:
        """Pre-warm cache from persisted memory store (e.g. at mission start)."""
        entries = self._manager.query(scope=scope, limit=limit)
        for entry in entries:
            self.index_entry(entry)
        logger.info("intelligence_cache.warmed scope=%s count=%d", scope.value, len(entries))
        return len(entries)

    # -- Metrics ---------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            m = dict(self._metrics)
        m["domain_index_size"] = sum(b.count() for b in self._domain_idx.values())
        m["vuln_index_size"] = sum(b.count() for b in self._vuln_idx.values())
        m["tech_index_size"] = sum(b.count() for b in self._tech_idx.values())
        total_lookups = m["hits"] + m["misses"]
        m["hit_rate"] = round(m["hits"] / total_lookups, 4) if total_lookups > 0 else 0.0
        return m

    def clear(self) -> None:
        with self._lock:
            self._domain_idx.clear()
            self._vuln_idx.clear()
            self._tech_idx.clear()
            self._endpoint_idx.clear()
            self._metrics = {k: 0 for k in self._metrics}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cache_instance: IntelligenceCache | None = None
_cache_lock = threading.Lock()


def get_intelligence_cache() -> IntelligenceCache:
    global _cache_instance
    with _cache_lock:
        if _cache_instance is None:
            _cache_instance = IntelligenceCache()
        return _cache_instance
