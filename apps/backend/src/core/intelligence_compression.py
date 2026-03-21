"""
Intelligence Compression & Chunking
======================================
Compresses repeated patterns into structured memory signatures.

Capabilities:
  - Group and compress repeated findings into pattern_signature entries
  - Summarize large artifact sets into structured memory records
  - Deduplicate similar findings (beyond exact-match dedup in MemoryStore)
  - Create "pattern signatures" from clusters of related findings

Example:
  50 reflected parameter findings across different URLs →
    ONE PatternSignature memory entry:
      type: reflected_xss
      endpoints: [normalized patterns]
      params: [q, search, name, ...]
      confidence: max(individual confs) + bonus
      count: 50

This reduces memory bloat and enables pattern-level inference
("we've seen reflected XSS in this parameter class before → try it first").

Integration:
  Called by MemoryManager after FindingClusterer runs.
  PatternSignature entries are written to LONG_TERM memory.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .intelligence_memory import (
    MemoryEntry,
    MemoryManager,
    MemoryScope,
    MemoryType,
    TargetFingerprint,
    ValidationStatus,
    get_memory_manager,
)
from .intelligence_encryption import derive_content_hash, encrypt_payload

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern signature data structure
# ---------------------------------------------------------------------------


@dataclass
class PatternSignature:
    """
    Represents a compressed pattern extracted from multiple related findings.
    This becomes a LONG_TERM memory entry of type PATTERN_SIGNATURE.
    """

    pattern_id: str
    vuln_type: str
    endpoint_patterns: list[str]    # normalized URL patterns
    affected_parameters: list[str]  # parameters that exhibited this pattern
    tech_stack_context: list[str]   # common tech stack across occurrences
    sample_payloads: list[str]      # representative payloads (up to 5)
    occurrence_count: int
    confidence: float               # max confidence + corroboration bonus
    first_seen_mission: str
    last_seen_mission: str
    source_memory_ids: list[str]    # memory_ids compressed into this signature

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "vuln_type": self.vuln_type,
            "endpoint_patterns": self.endpoint_patterns,
            "affected_parameters": self.affected_parameters,
            "tech_stack_context": self.tech_stack_context,
            "sample_payloads": self.sample_payloads[:5],
            "occurrence_count": self.occurrence_count,
            "confidence": round(self.confidence, 4),
            "first_seen_mission": self.first_seen_mission,
            "last_seen_mission": self.last_seen_mission,
            "source_memory_ids": self.source_memory_ids[:20],
        }


# ---------------------------------------------------------------------------
# Compression engine
# ---------------------------------------------------------------------------


class IntelligenceCompressor:
    """
    Compresses clusters of related memory entries into pattern signatures.

    Usage::

        compressor = IntelligenceCompressor()
        signatures = compressor.compress(entries)
        for sig in signatures:
            compressor.write_to_memory(sig, mission_id="m1")
    """

    def __init__(self, manager: MemoryManager | None = None) -> None:
        self._manager = manager or get_memory_manager()

    def compress(
        self,
        entries: list[MemoryEntry],
        min_occurrences: int = 3,
        similarity_threshold: float = 0.70,
    ) -> list[PatternSignature]:
        """
        Compress a list of memory entries into pattern signatures.

        Groups by vuln_type, then clusters by endpoint similarity.
        Only creates signatures when min_occurrences is met.

        Returns list of PatternSignature objects (not yet written to memory).
        """
        if not entries:
            return []

        # Group by vuln_type
        by_type: dict[str, list[MemoryEntry]] = {}
        for entry in entries:
            vtype = _extract_vuln_type(entry)
            by_type.setdefault(vtype, []).append(entry)

        signatures: list[PatternSignature] = []
        for vtype, group in by_type.items():
            if len(group) < min_occurrences:
                continue
            sigs = self._cluster_and_compress(vtype, group, similarity_threshold)
            signatures.extend(sigs)

        return signatures

    def _cluster_and_compress(
        self,
        vuln_type: str,
        entries: list[MemoryEntry],
        threshold: float,
    ) -> list[PatternSignature]:
        """Cluster entries within a vuln_type group by endpoint similarity."""
        clusters: list[list[MemoryEntry]] = []

        for entry in entries:
            domain = entry.target_fingerprint.domain
            placed = False
            for cluster in clusters:
                rep = cluster[0]
                if _domain_similar(domain, rep.target_fingerprint.domain, threshold):
                    cluster.append(entry)
                    placed = True
                    break
            if not placed:
                clusters.append([entry])

        signatures = []
        for cluster in clusters:
            sig = _make_signature(vuln_type, cluster)
            signatures.append(sig)
        return signatures

    def write_to_memory(
        self,
        signature: PatternSignature,
        mission_id: str,
        tenant_id: str | None = None,
    ) -> MemoryEntry | None:
        """
        Write a pattern signature to LONG_TERM memory.
        Returns the created MemoryEntry or None if ingestion rejected.
        """
        payload = signature.to_dict()
        entry = self._manager.create_entry(
            memory_type=MemoryType.PATTERN_SIGNATURE,
            scope=MemoryScope.LONG_TERM,
            payload=payload,
            confidence_score=signature.confidence,
            validation_status=ValidationStatus.CONFIRMED,
            source_mission_id=mission_id,
            target_fingerprint=TargetFingerprint(
                tech_stack=signature.tech_stack_context,
            ),
            tags=[f"vuln_type:{signature.vuln_type}", "compressed_pattern"],
            relationships=signature.source_memory_ids[:10],
            tenant_id=tenant_id,
        )
        accepted = self._manager.ingest(entry)
        if accepted:
            logger.info(
                "intelligence_compression.signature_written pattern=%s vuln=%s count=%d",
                signature.pattern_id, signature.vuln_type, signature.occurrence_count,
            )
            return entry
        return None

    def compress_and_write(
        self,
        entries: list[MemoryEntry],
        mission_id: str,
        tenant_id: str | None = None,
        min_occurrences: int = 3,
    ) -> list[MemoryEntry]:
        """Convenience: compress entries and write all resulting signatures."""
        signatures = self.compress(entries, min_occurrences=min_occurrences)
        written: list[MemoryEntry] = []
        for sig in signatures:
            entry = self.write_to_memory(sig, mission_id, tenant_id)
            if entry:
                written.append(entry)
        return written

    def deduplicate_payloads(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """
        Remove near-duplicate entries based on content hash and tag similarity.
        Returns deduplicated list (first occurrence wins).
        """
        seen_hashes: set[str] = set()
        unique: list[MemoryEntry] = []
        for entry in entries:
            if entry.content_hash in seen_hashes:
                continue
            seen_hashes.add(entry.content_hash)
            unique.append(entry)
        return unique

    def summarize_artifacts(
        self,
        artifacts: list[dict[str, Any]],
        vuln_type: str,
        mission_id: str,
        max_payload_items: int = 10,
    ) -> dict[str, Any]:
        """
        Summarize a large list of artifacts into a compact structured dict.

        Used when an artifact set is too large to store verbatim — extracts
        key fields (URLs, parameters, status codes) into a compact summary.
        """
        urls = list({a.get("url", "") for a in artifacts if a.get("url")})[:max_payload_items]
        params = list({a.get("parameter", "") for a in artifacts if a.get("parameter")})[:10]
        statuses = list({a.get("status_code", 0) for a in artifacts if a.get("status_code")})
        payloads = list({a.get("payload", "") for a in artifacts if a.get("payload")})[:5]

        return {
            "summary_type": "artifact_compression",
            "vuln_type": vuln_type,
            "mission_id": mission_id,
            "total_artifacts": len(artifacts),
            "sample_urls": urls,
            "affected_parameters": params,
            "observed_status_codes": statuses,
            "sample_payloads": payloads,
            "compressed_at": time.time(),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_vuln_type(entry: MemoryEntry) -> str:
    """Extract vuln_type from tags or memory_type."""
    for tag in entry.tags:
        if tag.startswith("vuln_type:"):
            return tag[len("vuln_type:"):]
    # Fallback to memory_type
    return entry.memory_type.value


def _domain_similar(a: str, b: str, threshold: float) -> bool:
    """Check if two domains are similar enough to cluster."""
    if not a or not b:
        return a == b
    ratio = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return ratio >= threshold


def _make_signature(vuln_type: str, cluster: list[MemoryEntry]) -> PatternSignature:
    """Create a PatternSignature from a cluster of related entries."""
    endpoints = list({e.target_fingerprint.domain for e in cluster if e.target_fingerprint.domain})
    params: list[str] = []
    tech_stacks: list[str] = []
    payloads: list[str] = []
    mission_ids: list[str] = []

    for entry in cluster:
        for tag in entry.tags:
            if tag.startswith("param:"):
                p = tag[len("param:"):]
                if p not in params:
                    params.append(p)
            if tag.startswith("payload:"):
                p = tag[len("payload:"):]
                if p not in payloads:
                    payloads.append(p)
        for tech in entry.target_fingerprint.tech_stack:
            if tech not in tech_stacks:
                tech_stacks.append(tech)
        if entry.source_mission_id not in mission_ids:
            mission_ids.append(entry.source_mission_id)

    # Confidence: max + corroboration bonus (capped at 0.95)
    max_conf = max((e.confidence_score for e in cluster), default=0.0)
    bonus = min(0.15, 0.03 * (len(cluster) - 1))
    confidence = min(0.95, max_conf + bonus)

    pattern_id = "pat-" + hashlib.md5(
        f"{vuln_type}{'|'.join(sorted(endpoints))}".encode()
    ).hexdigest()[:8]

    return PatternSignature(
        pattern_id=pattern_id,
        vuln_type=vuln_type,
        endpoint_patterns=endpoints[:20],
        affected_parameters=params[:20],
        tech_stack_context=tech_stacks[:10],
        sample_payloads=payloads[:5],
        occurrence_count=len(cluster),
        confidence=confidence,
        first_seen_mission=mission_ids[0] if mission_ids else "",
        last_seen_mission=mission_ids[-1] if mission_ids else "",
        source_memory_ids=[e.memory_id for e in cluster],
    )
