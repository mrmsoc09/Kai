"""
Intelligence Query Interface
==============================
Structured query layer for the intelligence memory system.

Supports:
  - "find similar endpoints"
  - "find previous vulnerability of this type"
  - "find targets with similar tech stack"
  - "find exploit patterns for vulnerability X"
  - "find high-confidence exploit chains"
  - "what have we seen on this domain before?"

Returns structured QueryResult objects — not raw blobs.

Integration:
  Used by:
    - EvidenceAnalyst executor (check prior art before validating)
    - ExploitAssessmentAgent (what exploit patterns exist for this type?)
    - ReportSynthesisAgent (check for similar historical findings)
    - Strategy learner (what worked before on similar targets?)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .intelligence_memory import (
    MemoryEntry,
    MemoryManager,
    MemoryScope,
    MemoryType,
    ValidationStatus,
    TargetFingerprint,
    get_memory_manager,
)
from .intelligence_cache import IntelligenceCache, get_intelligence_cache
from .intelligence_graph import IntelligenceGraph, EdgeType, get_intelligence_graph
from .memory_access_control import AccessPolicy, AgentClass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query result types
# ---------------------------------------------------------------------------


@dataclass
class SimilarEndpointResult:
    memory_id: str
    domain: str
    endpoint_tags: list[str]
    vuln_type: str
    confidence: float
    validation_status: str
    source_mission_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "domain": self.domain,
            "endpoint_tags": self.endpoint_tags,
            "vuln_type": self.vuln_type,
            "confidence": round(self.confidence, 4),
            "validation_status": self.validation_status,
            "source_mission_id": self.source_mission_id,
        }


@dataclass
class PriorVulnResult:
    memory_id: str
    vuln_type: str
    domain: str
    confidence: float
    validation_status: str
    source_mission_id: str
    tags: list[str]
    exploit_chain_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "vuln_type": self.vuln_type,
            "domain": self.domain,
            "confidence": round(self.confidence, 4),
            "validation_status": self.validation_status,
            "source_mission_id": self.source_mission_id,
            "tags": self.tags,
            "exploit_chain_ids": self.exploit_chain_ids,
        }


@dataclass
class TechStackResult:
    memory_id: str
    domain: str
    tech_stack: list[str]
    memory_type: str
    confidence: float
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "domain": self.domain,
            "tech_stack": self.tech_stack,
            "memory_type": self.memory_type,
            "confidence": round(self.confidence, 4),
            "tags": self.tags,
        }


@dataclass
class ExploitPatternResult:
    memory_id: str
    vuln_type: str
    confidence: float
    tool_sequence_ids: list[str]
    occurrence_count: int
    sample_payloads: list[str]
    affected_domains: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "vuln_type": self.vuln_type,
            "confidence": round(self.confidence, 4),
            "tool_sequence_ids": self.tool_sequence_ids,
            "occurrence_count": self.occurrence_count,
            "sample_payloads": self.sample_payloads[:5],
            "affected_domains": self.affected_domains[:10],
        }


@dataclass
class QueryStats:
    query_type: str
    duration_ms: float
    total_candidates: int
    returned: int
    cache_hit: bool = False


# ---------------------------------------------------------------------------
# Query engine
# ---------------------------------------------------------------------------


class IntelligenceQueryEngine:
    """
    Structured query interface over the intelligence memory system.

    All queries go through access policy enforcement — agents only see
    what their policy allows.

    Usage::

        engine = IntelligenceQueryEngine()
        policy = AccessPolicy.for_agent(AgentClass.EXPLOIT)

        results = engine.find_prior_vuln("sqli", domain="example.com", policy=policy)
        patterns = engine.find_exploit_patterns("xss", policy=policy)
    """

    def __init__(
        self,
        manager: MemoryManager | None = None,
        cache: IntelligenceCache | None = None,
        graph: IntelligenceGraph | None = None,
    ) -> None:
        self._manager = manager or get_memory_manager()
        self._cache = cache or get_intelligence_cache()
        self._graph = graph or get_intelligence_graph()

    # -- Query: similar endpoints -----------------------------------------------

    def find_similar_endpoints(
        self,
        domain: str,
        policy: AccessPolicy,
        min_confidence: float = 0.5,
        limit: int = 20,
    ) -> tuple[list[SimilarEndpointResult], QueryStats]:
        """
        Find memory entries for endpoints similar to the given domain.

        Checks cache first, falls back to full memory query.
        """
        start = time.monotonic()
        # Cache lookup
        cache_entries = self._cache.lookup_by_domain(domain)
        cache_hit = bool(cache_entries)
        if cache_entries:
            full_entries = self._cache.resolve(cache_entries)
        else:
            full_entries = self._manager.query(
                memory_type=MemoryType.ENDPOINT_BEHAVIOR,
                domain=domain,
                min_confidence=min_confidence,
                limit=limit * 2,
            )

        allowed = policy.filter(full_entries)
        results = [
            SimilarEndpointResult(
                memory_id=e.memory_id,
                domain=e.target_fingerprint.domain,
                endpoint_tags=[t for t in e.tags if t.startswith("endpoint:")],
                vuln_type=_tag_vuln_type(e.tags),
                confidence=e.confidence_score,
                validation_status=e.validation_status.value,
                source_mission_id=e.source_mission_id,
            )
            for e in allowed
            if e.confidence_score >= min_confidence
        ]
        results = sorted(results, key=lambda r: r.confidence, reverse=True)[:limit]

        stats = QueryStats(
            query_type="similar_endpoints",
            duration_ms=(time.monotonic() - start) * 1000,
            total_candidates=len(full_entries),
            returned=len(results),
            cache_hit=cache_hit,
        )
        return results, stats

    # -- Query: prior vulnerabilities -------------------------------------------

    def find_prior_vuln(
        self,
        vuln_type: str,
        domain: str | None = None,
        policy: AccessPolicy | None = None,
        min_confidence: float = 0.6,
        limit: int = 20,
    ) -> tuple[list[PriorVulnResult], QueryStats]:
        """
        Find previous validated vulnerabilities of the given type.

        Optionally filtered to a specific domain.
        Includes exploit chain information from the graph.
        """
        start = time.monotonic()
        policy = policy or AccessPolicy.for_agent(AgentClass.ANALYST)

        # Try cache first
        cache_entries = self._cache.lookup_by_vuln_type(vuln_type)
        cache_hit = bool(cache_entries)
        if cache_entries:
            full_entries = self._cache.resolve(cache_entries)
        else:
            full_entries = self._manager.query(
                memory_type=MemoryType.FINDING,
                tags=[vuln_type, f"vuln_type:{vuln_type}"],
                min_confidence=min_confidence,
                limit=limit * 3,
            )

        if domain:
            full_entries = [e for e in full_entries if e.target_fingerprint.domain == domain]

        allowed = policy.filter(full_entries)

        results: list[PriorVulnResult] = []
        for e in allowed:
            if e.confidence_score < min_confidence:
                continue
            # Get exploit chain from graph
            chains = self._graph.find_exploit_chain(e.memory_id, max_depth=2)
            chain_ids = [path[-1] for path in chains][:3]
            results.append(
                PriorVulnResult(
                    memory_id=e.memory_id,
                    vuln_type=_tag_vuln_type(e.tags) or vuln_type,
                    domain=e.target_fingerprint.domain,
                    confidence=e.confidence_score,
                    validation_status=e.validation_status.value,
                    source_mission_id=e.source_mission_id,
                    tags=e.tags,
                    exploit_chain_ids=chain_ids,
                )
            )

        results = sorted(results, key=lambda r: r.confidence, reverse=True)[:limit]

        stats = QueryStats(
            query_type="prior_vuln",
            duration_ms=(time.monotonic() - start) * 1000,
            total_candidates=len(full_entries),
            returned=len(results),
            cache_hit=cache_hit,
        )
        return results, stats

    # -- Query: tech stack targets -----------------------------------------------

    def find_targets_by_tech(
        self,
        tech_stack: list[str],
        policy: AccessPolicy | None = None,
        min_confidence: float = 0.4,
        limit: int = 30,
    ) -> tuple[list[TechStackResult], QueryStats]:
        """
        Find memory entries for targets running the given tech stack.

        Useful for: "show me all endpoints we've seen running nginx+php-fpm".
        """
        start = time.monotonic()
        policy = policy or AccessPolicy.for_agent(AgentClass.ANALYST)

        all_entries: list[MemoryEntry] = []
        cache_hit = False
        for tech in tech_stack:
            cache_entries = self._cache.lookup_by_tech_stack(tech)
            if cache_entries:
                cache_hit = True
                all_entries.extend(self._cache.resolve(cache_entries))
            else:
                entries = self._manager.query(
                    tech_stack=[tech],
                    min_confidence=min_confidence,
                    limit=limit,
                )
                all_entries.extend(entries)

        # Dedup
        seen: set[str] = set()
        unique: list[MemoryEntry] = []
        for e in all_entries:
            if e.memory_id not in seen:
                seen.add(e.memory_id)
                unique.append(e)

        allowed = policy.filter(unique)
        results = [
            TechStackResult(
                memory_id=e.memory_id,
                domain=e.target_fingerprint.domain,
                tech_stack=e.target_fingerprint.tech_stack,
                memory_type=e.memory_type.value,
                confidence=e.confidence_score,
                tags=e.tags,
            )
            for e in allowed
        ]
        results = sorted(results, key=lambda r: r.confidence, reverse=True)[:limit]

        stats = QueryStats(
            query_type="tech_stack",
            duration_ms=(time.monotonic() - start) * 1000,
            total_candidates=len(unique),
            returned=len(results),
            cache_hit=cache_hit,
        )
        return results, stats

    # -- Query: exploit patterns --------------------------------------------------

    def find_exploit_patterns(
        self,
        vuln_type: str,
        policy: AccessPolicy | None = None,
        min_confidence: float = 0.7,
        limit: int = 10,
    ) -> tuple[list[ExploitPatternResult], QueryStats]:
        """
        Find exploit patterns and signatures for a given vulnerability type.

        Returns patterns from STRATEGIC and LONG_TERM memory that match
        the vuln_type — including tool sequences that trigger them.
        """
        start = time.monotonic()
        policy = policy or AccessPolicy.for_agent(AgentClass.EXPLOIT)

        entries = self._manager.query(
            memory_type=MemoryType.EXPLOIT_PATTERN,
            tags=[f"vuln_type:{vuln_type}", vuln_type],
            min_confidence=min_confidence,
            validation_status=ValidationStatus.CONFIRMED,
            limit=limit * 2,
        )
        # Also check pattern signatures
        sigs = self._manager.query(
            memory_type=MemoryType.PATTERN_SIGNATURE,
            tags=[f"vuln_type:{vuln_type}"],
            min_confidence=min_confidence,
            limit=limit,
        )
        entries = entries + sigs

        allowed = policy.filter(entries)

        results: list[ExploitPatternResult] = []
        for e in allowed:
            # Get linked tool sequences via graph
            tool_seq_edges = self._graph.get_neighbors(e.memory_id, EdgeType.EXPLOIT_TO_TOOL_SEQ)
            tool_seq_ids = [ed.target_id for ed in tool_seq_edges]

            # Try to decrypt for payload details (best-effort)
            payload_data: dict = {}
            try:
                payload_data = e.decrypt() or {}
            except Exception:
                pass

            results.append(
                ExploitPatternResult(
                    memory_id=e.memory_id,
                    vuln_type=vuln_type,
                    confidence=e.confidence_score,
                    tool_sequence_ids=tool_seq_ids[:5],
                    occurrence_count=payload_data.get("occurrence_count", 1),
                    sample_payloads=payload_data.get("sample_payloads", [])[:5],
                    affected_domains=payload_data.get("endpoint_patterns", [])[:10],
                )
            )

        results = sorted(results, key=lambda r: r.confidence, reverse=True)[:limit]

        stats = QueryStats(
            query_type="exploit_patterns",
            duration_ms=(time.monotonic() - start) * 1000,
            total_candidates=len(entries),
            returned=len(results),
            cache_hit=False,
        )
        return results, stats

    # -- Query: domain history -----------------------------------------------

    def what_do_we_know_about(
        self,
        domain: str,
        policy: AccessPolicy | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Aggregate everything known about a domain from all memory tiers.

        Returns a structured summary suitable for mission briefing.
        """
        policy = policy or AccessPolicy.for_agent(AgentClass.ORCHESTRATOR)
        all_entries = self._manager.query(domain=domain, limit=limit)
        allowed = policy.filter(all_entries)

        vulns = [e for e in allowed if e.memory_type == MemoryType.FINDING]
        patterns = [e for e in allowed if e.memory_type == MemoryType.PATTERN_SIGNATURE]
        tech = [e for e in allowed if e.memory_type == MemoryType.TECH_STACK]
        endpoints = [e for e in allowed if e.memory_type == MemoryType.ENDPOINT_BEHAVIOR]

        tech_stack = list({
            t for e in tech for t in e.target_fingerprint.tech_stack
        })
        vuln_types = list({_tag_vuln_type(e.tags) for e in vulns if _tag_vuln_type(e.tags)})
        high_conf_vulns = [e for e in vulns if e.confidence_score >= 0.8]

        return {
            "domain": domain,
            "known_vuln_types": vuln_types,
            "finding_count": len(vulns),
            "high_confidence_findings": len(high_conf_vulns),
            "pattern_signatures": len(patterns),
            "tech_stack": tech_stack,
            "endpoint_count": len(endpoints),
            "source_missions": list({e.source_mission_id for e in allowed}),
            "recommendation": _generate_recommendation(vuln_types, high_conf_vulns, tech_stack),
        }

    # -- Cross-mission reuse metrics ------------------------------------------

    def get_cross_mission_reuse_stats(self) -> dict[str, Any]:
        """
        Calculate how often intelligence from prior missions is being reused.
        """
        metrics = self._manager.get_metrics()
        cache_metrics = self._cache.get_metrics()
        graph_summary = self._graph.to_summary()

        return {
            "memory_metrics": metrics,
            "cache_metrics": cache_metrics,
            "graph_summary": graph_summary,
            "cross_mission_reuse_rate": cache_metrics.get("hit_rate", 0.0),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tag_vuln_type(tags: list[str]) -> str:
    """Extract vuln_type from tags."""
    for tag in tags:
        if tag.startswith("vuln_type:"):
            return tag[len("vuln_type:"):]
    return ""


def _generate_recommendation(
    vuln_types: list[str],
    high_conf_findings: list[MemoryEntry],
    tech_stack: list[str],
) -> str:
    """Generate a brief intelligence recommendation string."""
    if not vuln_types and not high_conf_findings:
        return "No prior intelligence — start with passive recon"
    parts = []
    if high_conf_findings:
        parts.append(f"Prioritize validation of {len(high_conf_findings)} known high-confidence findings")
    if vuln_types:
        parts.append(f"Known vuln classes: {', '.join(vuln_types[:5])}")
    if tech_stack:
        parts.append(f"Tech stack: {', '.join(tech_stack[:5])}")
    return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine_instance: IntelligenceQueryEngine | None = None
import threading as _threading
_engine_lock = _threading.Lock()


def get_query_engine() -> IntelligenceQueryEngine:
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = IntelligenceQueryEngine()
        return _engine_instance
