"""
Multi-Tier Intelligence Memory System
========================================
First-class memory subsystem for cross-mission learning and structured recall.

Memory Tiers (strict separation):
  SHORT_TERM  — scoped to current execution node/phase; ephemeral; in-process only
  MID_TERM    — scoped to mission/workflow; persisted to artifacts/intelligence/mid/
  LONG_TERM   — global cross-mission; persisted to artifacts/intelligence/long/
  STRATEGIC   — curated high-value; append-only; artifacts/intelligence/strategic/

Each entry is a MemoryEntry with:
  - Structured metadata (not raw blobs)
  - Encrypted payload (via intelligence_encryption)
  - Typed (finding, exploit_pattern, endpoint_behavior, tool_sequence, tech_stack)
  - Relationships to other entries (linked via memory_id)
  - Promotion rules (short → mid → long → strategic)

Promotion criteria:
  - confidence_score ≥ 0.6  for short → mid
  - confidence_score ≥ 0.75 for mid → long
  - confidence_score ≥ 0.9  AND validation_status == "confirmed" for long → strategic

Ingestion:
  - Only accepts entries above minimum confidence thresholds
  - Rejects unvalidated data from entering LONG_TERM or STRATEGIC
  - Deduplicates by content_hash before writing
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from .intelligence_encryption import encrypt_payload, decrypt_payload, derive_content_hash

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MemoryScope(str, Enum):
    SHORT_TERM = "short"
    MID_TERM = "mid"
    LONG_TERM = "long"
    STRATEGIC = "strategic"


class MemoryType(str, Enum):
    FINDING = "finding"
    EXPLOIT_PATTERN = "exploit_pattern"
    ENDPOINT_BEHAVIOR = "endpoint_behavior"
    TOOL_SEQUENCE = "tool_sequence"
    TECH_STACK = "tech_stack"
    VULN_CLASS = "vuln_class"
    OPPORTUNITY_SIGNAL = "opportunity_signal"
    PATTERN_SIGNATURE = "pattern_signature"


class ValidationStatus(str, Enum):
    UNVALIDATED = "unvalidated"
    PARTIAL = "partial"      # some evidence but not confirmed
    CONFIRMED = "confirmed"  # validated by VulnerabilityValidator or exploit attempt
    REJECTED = "rejected"    # false positive


# ---------------------------------------------------------------------------
# Promotion thresholds
# ---------------------------------------------------------------------------

_PROMOTION_THRESHOLDS: dict[tuple[MemoryScope, MemoryScope], float] = {
    (MemoryScope.SHORT_TERM, MemoryScope.MID_TERM): 0.60,
    (MemoryScope.MID_TERM, MemoryScope.LONG_TERM): 0.75,
    (MemoryScope.LONG_TERM, MemoryScope.STRATEGIC): 0.90,
}

_INGESTION_MIN_CONFIDENCE: dict[MemoryScope, float] = {
    MemoryScope.SHORT_TERM: 0.0,   # accept anything — ephemeral
    MemoryScope.MID_TERM: 0.30,
    MemoryScope.LONG_TERM: 0.60,
    MemoryScope.STRATEGIC: 0.90,
}

_LONG_TERM_REQUIRES_VALIDATION = {MemoryScope.LONG_TERM, MemoryScope.STRATEGIC}


# ---------------------------------------------------------------------------
# Memory entry
# ---------------------------------------------------------------------------


@dataclass
class TargetFingerprint:
    domain: str = ""
    ip: str | None = None
    tech_stack: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    cdn: str | None = None

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "ip": self.ip,
            "tech_stack": self.tech_stack,
            "services": self.services,
            "cdn": self.cdn,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TargetFingerprint":
        return cls(
            domain=d.get("domain", ""),
            ip=d.get("ip"),
            tech_stack=d.get("tech_stack", []),
            services=d.get("services", []),
            cdn=d.get("cdn"),
        )


@dataclass
class MemoryEntry:
    """A single intelligence memory record."""

    memory_id: str
    memory_type: MemoryType
    scope: MemoryScope
    target_fingerprint: TargetFingerprint
    tags: list[str]                   # vuln_type, tech, risk level, etc.
    confidence_score: float           # 0.0–1.0
    validation_status: ValidationStatus
    source_mission_id: str
    created_at: float                 # UNIX timestamp
    relationships: list[str]          # other memory_ids
    encrypted_payload: dict[str, str] # {"enc": ..., "alg": ..., "kid": ...}
    content_hash: str                 # for deduplication
    promoted_from: MemoryScope | None = None  # set when promoted
    promotion_count: int = 0
    tenant_id: str | None = None
    mission_phase: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type.value,
            "scope": self.scope.value,
            "target_fingerprint": self.target_fingerprint.to_dict(),
            "tags": self.tags,
            "confidence_score": round(self.confidence_score, 4),
            "validation_status": self.validation_status.value,
            "source_mission_id": self.source_mission_id,
            "created_at": self.created_at,
            "relationships": self.relationships,
            "encrypted_payload": self.encrypted_payload,
            "content_hash": self.content_hash,
            "promoted_from": self.promoted_from.value if self.promoted_from else None,
            "promotion_count": self.promotion_count,
            "tenant_id": self.tenant_id,
            "mission_phase": self.mission_phase,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        return cls(
            memory_id=d["memory_id"],
            memory_type=MemoryType(d["memory_type"]),
            scope=MemoryScope(d["scope"]),
            target_fingerprint=TargetFingerprint.from_dict(d.get("target_fingerprint", {})),
            tags=d.get("tags", []),
            confidence_score=d.get("confidence_score", 0.0),
            validation_status=ValidationStatus(d.get("validation_status", "unvalidated")),
            source_mission_id=d.get("source_mission_id", ""),
            created_at=d.get("created_at", time.time()),
            relationships=d.get("relationships", []),
            encrypted_payload=d.get("encrypted_payload", {}),
            content_hash=d.get("content_hash", ""),
            promoted_from=MemoryScope(d["promoted_from"]) if d.get("promoted_from") else None,
            promotion_count=d.get("promotion_count", 0),
            tenant_id=d.get("tenant_id"),
            mission_phase=d.get("mission_phase"),
        )

    def decrypt(self) -> Any:
        """Decrypt and return the payload."""
        return decrypt_payload(self.encrypted_payload, self.tenant_id)

    def can_promote(self, to_scope: MemoryScope) -> bool:
        """Check if this entry meets promotion criteria."""
        threshold = _PROMOTION_THRESHOLDS.get((self.scope, to_scope), 1.1)
        if self.confidence_score < threshold:
            return False
        if to_scope in _LONG_TERM_REQUIRES_VALIDATION:
            if self.validation_status != ValidationStatus.CONFIRMED:
                return False
        return True


# ---------------------------------------------------------------------------
# Memory store — file-backed per tier
# ---------------------------------------------------------------------------


def _artifacts_root() -> Path:
    env = os.getenv("K1_ARTIFACTS_ROOT", "").strip()
    return Path(env) if env else Path("artifacts")


def _tier_dir(scope: MemoryScope) -> Path:
    return _artifacts_root() / "intelligence" / scope.value


class MemoryStore:
    """
    Persistent, thread-safe store for a single memory tier.

    Storage format: one JSON file per memory_id in artifacts/intelligence/<scope>/
    Index file: artifacts/intelligence/<scope>/.index.jsonl (append-only)
    """

    def __init__(self, scope: MemoryScope) -> None:
        self.scope = scope
        self._dir = _tier_dir(scope)
        self._lock = threading.Lock()
        self._index: dict[str, str] = {}  # memory_id → file path
        self._content_hashes: set[str] = set()  # for dedup
        self._dir.mkdir(parents=True, exist_ok=True)
        self._load_index()

    def _load_index(self) -> None:
        index_path = self._dir / ".index.jsonl"
        if not index_path.exists():
            return
        with open(index_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    self._index[rec["memory_id"]] = rec["path"]
                    self._content_hashes.add(rec.get("content_hash", ""))
                except (json.JSONDecodeError, KeyError):
                    continue

    def _append_index(self, entry: MemoryEntry) -> None:
        index_path = self._dir / ".index.jsonl"
        record = {
            "memory_id": entry.memory_id,
            "path": str(self._entry_path(entry.memory_id)),
            "content_hash": entry.content_hash,
            "memory_type": entry.memory_type.value,
            "created_at": entry.created_at,
        }
        with open(index_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def _entry_path(self, memory_id: str) -> Path:
        # Shard by first 2 chars of memory_id to avoid filesystem limits
        shard = memory_id[:2] if len(memory_id) >= 2 else "00"
        shard_dir = self._dir / shard
        shard_dir.mkdir(exist_ok=True)
        return shard_dir / f"{memory_id}.json"

    def write(self, entry: MemoryEntry) -> bool:
        """
        Write a memory entry. Returns False if duplicate (same content_hash).
        """
        with self._lock:
            if entry.content_hash and entry.content_hash in self._content_hashes:
                logger.debug("memory_store.duplicate_skipped hash=%s", entry.content_hash)
                return False

            path = self._entry_path(entry.memory_id)
            data = json.dumps(entry.to_dict(), indent=None)
            # Atomic write via temp file
            tmp = path.with_suffix(".tmp")
            try:
                tmp.write_text(data, encoding="utf-8")
                tmp.replace(path)
            except OSError as e:
                logger.error("memory_store.write_failed entry=%s err=%s", entry.memory_id, e)
                return False

            self._index[entry.memory_id] = str(path)
            if entry.content_hash:
                self._content_hashes.add(entry.content_hash)
            self._append_index(entry)
            return True

    def read(self, memory_id: str) -> MemoryEntry | None:
        with self._lock:
            path_str = self._index.get(memory_id)
        if not path_str:
            return None
        try:
            data = Path(path_str).read_text(encoding="utf-8")
            return MemoryEntry.from_dict(json.loads(data))
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning("memory_store.read_failed id=%s err=%s", memory_id, e)
            return None

    def iter_all(self) -> Iterator[MemoryEntry]:
        """Iterate over all entries in this tier."""
        with self._lock:
            ids = list(self._index.keys())
        for mid in ids:
            entry = self.read(mid)
            if entry:
                yield entry

    def count(self) -> int:
        with self._lock:
            return len(self._index)

    def has_content_hash(self, h: str) -> bool:
        with self._lock:
            return h in self._content_hashes


# ---------------------------------------------------------------------------
# Short-term memory (in-process only — not persisted)
# ---------------------------------------------------------------------------


class ShortTermMemory:
    """
    Ephemeral in-process memory for the current execution phase.
    Keyed by (mission_id, phase) → list of MemoryEntry.
    Auto-evicts when a mission phase ends.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[MemoryEntry]] = {}  # key → entries
        self._lock = threading.Lock()

    def _key(self, mission_id: str, phase: str) -> str:
        return f"{mission_id}:{phase}"

    def write(self, entry: MemoryEntry) -> None:
        key = self._key(entry.source_mission_id, entry.mission_phase or "")
        with self._lock:
            if key not in self._store:
                self._store[key] = []
            # Simple dedup by content_hash
            existing_hashes = {e.content_hash for e in self._store[key]}
            if entry.content_hash not in existing_hashes:
                self._store[key].append(entry)

    def get(self, mission_id: str, phase: str) -> list[MemoryEntry]:
        key = self._key(mission_id, phase)
        with self._lock:
            return list(self._store.get(key, []))

    def evict(self, mission_id: str, phase: str) -> list[MemoryEntry]:
        """Remove and return entries for a completed phase (for promotion consideration)."""
        key = self._key(mission_id, phase)
        with self._lock:
            return self._store.pop(key, [])

    def count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._store.values())


# ---------------------------------------------------------------------------
# MemoryManager — the main API surface
# ---------------------------------------------------------------------------


class MemoryManager:
    """
    Central API for the intelligence memory system.

    Usage::

        mgr = MemoryManager()

        # Ingest a new finding memory
        entry = mgr.create_entry(
            memory_type=MemoryType.FINDING,
            scope=MemoryScope.MID_TERM,
            payload={"url": "...", "vuln": "sqli"},
            confidence_score=0.8,
            validation_status=ValidationStatus.CONFIRMED,
            ...
        )
        mgr.ingest(entry)

        # Promote when confidence grows
        promoted = mgr.promote(entry)

        # Retrieve
        entries = mgr.query_by_tags(["sqli"], scope=MemoryScope.LONG_TERM)
    """

    def __init__(self) -> None:
        self._short = ShortTermMemory()
        self._mid = MemoryStore(MemoryScope.MID_TERM)
        self._long = MemoryStore(MemoryScope.LONG_TERM)
        self._strategic = MemoryStore(MemoryScope.STRATEGIC)
        self._lock = threading.Lock()
        # Metrics
        self._metrics: dict[str, int] = {
            "entries_created": 0,
            "entries_promoted": 0,
            "duplicates_rejected": 0,
            "ingestion_rejected_confidence": 0,
            "ingestion_rejected_validation": 0,
        }

    def _store_for(self, scope: MemoryScope) -> MemoryStore | ShortTermMemory:
        return {
            MemoryScope.SHORT_TERM: self._short,
            MemoryScope.MID_TERM: self._mid,
            MemoryScope.LONG_TERM: self._long,
            MemoryScope.STRATEGIC: self._strategic,
        }[scope]

    def create_entry(
        self,
        memory_type: MemoryType,
        scope: MemoryScope,
        payload: Any,
        confidence_score: float,
        validation_status: ValidationStatus,
        source_mission_id: str,
        target_fingerprint: TargetFingerprint | None = None,
        tags: list[str] | None = None,
        relationships: list[str] | None = None,
        tenant_id: str | None = None,
        mission_phase: str | None = None,
    ) -> MemoryEntry:
        """Create (but do not yet ingest) a MemoryEntry."""
        content_hash = derive_content_hash(payload)
        encrypted = encrypt_payload(payload, tenant_id)
        return MemoryEntry(
            memory_id=str(uuid.uuid4()),
            memory_type=memory_type,
            scope=scope,
            target_fingerprint=target_fingerprint or TargetFingerprint(),
            tags=list(tags or []),
            confidence_score=confidence_score,
            validation_status=validation_status,
            source_mission_id=source_mission_id,
            created_at=time.time(),
            relationships=list(relationships or []),
            encrypted_payload=encrypted,
            content_hash=content_hash,
            tenant_id=tenant_id,
            mission_phase=mission_phase,
        )

    def ingest(self, entry: MemoryEntry) -> bool:
        """
        Ingest a memory entry into the appropriate tier store.

        Enforces:
          - minimum confidence per tier
          - validation requirement for LONG_TERM and STRATEGIC
          - content deduplication

        Returns True if accepted, False if rejected.
        """
        min_conf = _INGESTION_MIN_CONFIDENCE[entry.scope]
        if entry.confidence_score < min_conf:
            logger.debug(
                "memory_ingest.rejected_confidence scope=%s conf=%.3f min=%.3f",
                entry.scope, entry.confidence_score, min_conf,
            )
            with self._lock:
                self._metrics["ingestion_rejected_confidence"] += 1
            return False

        if entry.scope in _LONG_TERM_REQUIRES_VALIDATION:
            if entry.validation_status != ValidationStatus.CONFIRMED:
                logger.debug(
                    "memory_ingest.rejected_validation scope=%s status=%s",
                    entry.scope, entry.validation_status,
                )
                with self._lock:
                    self._metrics["ingestion_rejected_validation"] += 1
                return False

        store = self._store_for(entry.scope)
        if isinstance(store, ShortTermMemory):
            store.write(entry)
            accepted = True
        else:
            accepted = store.write(entry)

        if accepted:
            with self._lock:
                self._metrics["entries_created"] += 1
        else:
            with self._lock:
                self._metrics["duplicates_rejected"] += 1
        return accepted

    def promote(self, entry: MemoryEntry, force: bool = False) -> MemoryEntry | None:
        """
        Promote a memory entry to the next tier if promotion criteria are met.

        Returns the new entry in the higher tier, or None if promotion denied.
        """
        scope_order = [
            MemoryScope.SHORT_TERM,
            MemoryScope.MID_TERM,
            MemoryScope.LONG_TERM,
            MemoryScope.STRATEGIC,
        ]
        idx = scope_order.index(entry.scope)
        if idx >= len(scope_order) - 1:
            return None  # already at highest tier

        next_scope = scope_order[idx + 1]
        if not force and not entry.can_promote(next_scope):
            return None

        promoted = MemoryEntry(
            memory_id=str(uuid.uuid4()),
            memory_type=entry.memory_type,
            scope=next_scope,
            target_fingerprint=entry.target_fingerprint,
            tags=entry.tags,
            confidence_score=entry.confidence_score,
            validation_status=entry.validation_status,
            source_mission_id=entry.source_mission_id,
            created_at=time.time(),
            relationships=entry.relationships + [entry.memory_id],
            encrypted_payload=entry.encrypted_payload,  # reuse — same key
            content_hash=entry.content_hash,
            promoted_from=entry.scope,
            promotion_count=entry.promotion_count + 1,
            tenant_id=entry.tenant_id,
            mission_phase=entry.mission_phase,
        )
        accepted = self.ingest(promoted)
        if accepted:
            with self._lock:
                self._metrics["entries_promoted"] += 1
            return promoted
        return None

    def get(self, memory_id: str, scope: MemoryScope | None = None) -> MemoryEntry | None:
        """Retrieve a specific memory entry by ID."""
        scopes_to_check = [scope] if scope else [
            MemoryScope.SHORT_TERM,
            MemoryScope.MID_TERM,
            MemoryScope.LONG_TERM,
            MemoryScope.STRATEGIC,
        ]
        for s in scopes_to_check:
            store = self._store_for(s)
            if isinstance(store, ShortTermMemory):
                # linear scan short-term
                for entries in store._store.values():
                    for e in entries:
                        if e.memory_id == memory_id:
                            return e
            else:
                entry = store.read(memory_id)
                if entry:
                    return entry
        return None

    def query(
        self,
        scope: MemoryScope | None = None,
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
        min_confidence: float = 0.0,
        validation_status: ValidationStatus | None = None,
        domain: str | None = None,
        tech_stack: list[str] | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """
        Query memory entries across tiers with optional filters.
        """
        scopes = (
            [scope]
            if scope
            else [MemoryScope.MID_TERM, MemoryScope.LONG_TERM, MemoryScope.STRATEGIC]
        )
        results: list[MemoryEntry] = []
        for s in scopes:
            store = self._store_for(s)
            if isinstance(store, ShortTermMemory):
                candidates: list[MemoryEntry] = []
                with store._lock:
                    for entries in store._store.values():
                        candidates.extend(entries)
            else:
                candidates = list(store.iter_all())

            for entry in candidates:
                if tenant_id is not None and entry.tenant_id != tenant_id:
                    continue
                if memory_type and entry.memory_type != memory_type:
                    continue
                if entry.confidence_score < min_confidence:
                    continue
                if validation_status and entry.validation_status != validation_status:
                    continue
                if tags and not any(t in entry.tags for t in tags):
                    continue
                if domain and entry.target_fingerprint.domain != domain:
                    continue
                if tech_stack:
                    entry_tech = set(entry.target_fingerprint.tech_stack)
                    if not any(t in entry_tech for t in tech_stack):
                        continue
                results.append(entry)
                if len(results) >= limit:
                    return results

        return results

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            m = dict(self._metrics)
        m["short_term_count"] = self._short.count()
        m["mid_term_count"] = self._mid.count()
        m["long_term_count"] = self._long.count()
        m["strategic_count"] = self._strategic.count()
        total = m["mid_term_count"] + m["long_term_count"] + m["strategic_count"]
        m["high_value_ratio"] = (
            round(m["strategic_count"] / total, 4) if total > 0 else 0.0
        )
        return m

    def evict_short_term(self, mission_id: str, phase: str) -> list[MemoryEntry]:
        """Evict short-term entries for a completed phase (returns them for promotion)."""
        return self._short.evict(mission_id, phase)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager_instance: MemoryManager | None = None
_manager_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    """Return the module-level MemoryManager singleton."""
    global _manager_instance
    with _manager_lock:
        if _manager_instance is None:
            _manager_instance = MemoryManager()
        return _manager_instance
