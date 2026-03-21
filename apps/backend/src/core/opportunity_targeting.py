"""
Opportunity Targeting — Target Match Ranking
=============================================
Given a confirmed vulnerability pattern, find which allowed domains
are most likely to be affected.

Matching signals (ranked by weight):
  1. Tech stack overlap (0.40)  — same frameworks = same attack surface
  2. Endpoint patterns   (0.25) — similar URL structures = same code paths
  3. Historical findings (0.20) — prior confirmed vulns on domain
  4. Service fingerprint (0.15) — open ports / service banners

Output:
  Ranked list of TargetMatch objects (domain + score + evidence).
  Caller filters by scope before using.

Integration:
  Called exclusively by OpportunityEngine.detect().
  Uses IntelligenceQueryEngine and MemoryManager.
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field
from typing import Any

from .intelligence_memory import (
    MemoryEntry,
    MemoryManager,
    MemoryType,
    ValidationStatus,
    get_memory_manager,
)
from .intelligence_query import IntelligenceQueryEngine, get_query_engine
from .memory_access_control import AccessPolicy, AgentClass

logger = logging.getLogger(__name__)

# Signal weights (must sum to 1.0)
_W_TECH = 0.40
_W_ENDPOINT = 0.25
_W_HISTORY = 0.20
_W_SERVICE = 0.15


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class TargetMatch:
    """A candidate domain ranked by how well it matches a vulnerability pattern."""

    domain: str
    score: float                    # 0.0–1.0 composite match score
    tech_score: float               # tech stack similarity
    endpoint_score: float           # endpoint pattern similarity
    history_score: float            # historical finding overlap
    service_score: float            # service fingerprint overlap
    matching_tech: list[str] = field(default_factory=list)
    matching_endpoints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "score": round(self.score, 4),
            "tech_score": round(self.tech_score, 4),
            "endpoint_score": round(self.endpoint_score, 4),
            "history_score": round(self.history_score, 4),
            "service_score": round(self.service_score, 4),
            "matching_tech": self.matching_tech,
            "matching_endpoints": self.matching_endpoints,
        }


# ---------------------------------------------------------------------------
# Targeter
# ---------------------------------------------------------------------------


class OpportunityTargeter:
    """
    Matches a confirmed vulnerability pattern against a list of candidate domains.

    Usage::

        targeter = OpportunityTargeter()
        matches = targeter.find_targets(
            source_entry=entry,
            allowed_domains=["a.com", "b.com"],
            vuln_type="sqli",
        )
        for m in matches:
            print(m.domain, m.score)
    """

    def __init__(
        self,
        manager: MemoryManager | None = None,
        query_engine: IntelligenceQueryEngine | None = None,
    ) -> None:
        self._manager = manager or get_memory_manager()
        self._query = query_engine or get_query_engine()

    def find_targets(
        self,
        source_entry: MemoryEntry,
        allowed_domains: list[str],
        vuln_type: str,
        min_score: float = 0.25,
        limit: int = 50,
    ) -> list[TargetMatch]:
        """
        Return ranked TargetMatch list for all allowed_domains.

        Only domains with composite score >= min_score are returned.
        Result is sorted by score descending.
        """
        if not allowed_domains:
            return []

        analyst_policy = AccessPolicy.for_agent(AgentClass.ANALYST)

        # Gather intelligence context for scoring
        source_tech = set(source_entry.target_fingerprint.tech_stack)
        source_services = set(source_entry.target_fingerprint.services)
        source_endpoints = _extract_endpoint_tags(source_entry.tags)

        # Load known data for each candidate domain
        matches: list[TargetMatch] = []

        for domain in allowed_domains:
            if not domain:
                continue

            # Collect all memory for this domain
            domain_entries = self._manager.query(domain=domain, limit=100)
            domain_entries = analyst_policy.filter(domain_entries)

            tech_score = self._score_tech_overlap(source_tech, domain_entries)
            endpoint_score = self._score_endpoint_overlap(source_endpoints, domain_entries)
            history_score = self._score_history(vuln_type, domain_entries)
            service_score = self._score_service_overlap(source_services, domain_entries)

            composite = (
                _W_TECH * tech_score
                + _W_ENDPOINT * endpoint_score
                + _W_HISTORY * history_score
                + _W_SERVICE * service_score
            )

            if composite < min_score:
                continue

            matching_tech = _matching_tech(source_tech, domain_entries)
            matching_eps = _matching_endpoints(source_endpoints, domain_entries)

            matches.append(
                TargetMatch(
                    domain=domain,
                    score=min(1.0, composite),
                    tech_score=tech_score,
                    endpoint_score=endpoint_score,
                    history_score=history_score,
                    service_score=service_score,
                    matching_tech=matching_tech,
                    matching_endpoints=matching_eps,
                )
            )

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:limit]

    # -- Scoring signals -------------------------------------------------------

    def _score_tech_overlap(
        self,
        source_tech: set[str],
        domain_entries: list[MemoryEntry],
    ) -> float:
        """Jaccard similarity between source tech stack and domain tech stacks."""
        if not source_tech:
            return 0.5  # neutral when no source tech info

        domain_tech: set[str] = set()
        for e in domain_entries:
            domain_tech.update(t.lower() for t in e.target_fingerprint.tech_stack)

        if not domain_tech:
            return 0.0

        source_lower = {t.lower() for t in source_tech}
        intersection = source_lower & domain_tech
        union = source_lower | domain_tech
        return len(intersection) / len(union)

    def _score_endpoint_overlap(
        self,
        source_endpoints: list[str],
        domain_entries: list[MemoryEntry],
    ) -> float:
        """Sequence similarity between source endpoint patterns and domain endpoints."""
        if not source_endpoints:
            return 0.0

        domain_endpoints = _collect_endpoint_tags(domain_entries)
        if not domain_endpoints:
            return 0.0

        # Best match for each source endpoint against domain endpoints
        total = 0.0
        for sep in source_endpoints:
            best = max(
                (difflib.SequenceMatcher(None, sep, dep).ratio() for dep in domain_endpoints),
                default=0.0,
            )
            total += best

        return total / len(source_endpoints)

    def _score_history(
        self,
        vuln_type: str,
        domain_entries: list[MemoryEntry],
    ) -> float:
        """
        Score based on historical findings on this domain.

        Logic:
          - Has confirmed findings of ANY type → 0.3 base (domain is active/accessible)
          - Has findings of SAME vuln_type (even unconfirmed) → 0.7
          - Has CONFIRMED finding of SAME vuln_type → 0.95 (domain already known vulnerable)
        """
        vuln_tag = f"vuln_type:{vuln_type}"
        has_any = bool(domain_entries)
        has_same_type = any(vuln_tag in e.tags or vuln_type in e.tags for e in domain_entries)
        has_confirmed_same = any(
            (vuln_tag in e.tags or vuln_type in e.tags)
            and e.validation_status == ValidationStatus.CONFIRMED
            for e in domain_entries
        )

        if has_confirmed_same:
            return 0.95
        if has_same_type:
            return 0.70
        if has_any:
            return 0.30
        return 0.0

    def _score_service_overlap(
        self,
        source_services: set[str],
        domain_entries: list[MemoryEntry],
    ) -> float:
        """Jaccard overlap between source services and domain services."""
        if not source_services:
            return 0.5  # neutral

        domain_services: set[str] = set()
        for e in domain_entries:
            domain_services.update(e.target_fingerprint.services)

        if not domain_services:
            return 0.0

        intersection = source_services & domain_services
        union = source_services | domain_services
        return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_endpoint_tags(tags: list[str]) -> list[str]:
    return [t[len("endpoint:"):] for t in tags if t.startswith("endpoint:")]


def _collect_endpoint_tags(entries: list[MemoryEntry]) -> list[str]:
    eps: list[str] = []
    for e in entries:
        eps.extend(_extract_endpoint_tags(e.tags))
    return eps


def _matching_tech(source_tech: set[str], domain_entries: list[MemoryEntry]) -> list[str]:
    domain_tech: set[str] = set()
    for e in domain_entries:
        domain_tech.update(t.lower() for t in e.target_fingerprint.tech_stack)
    return sorted(source_tech & domain_tech)


def _matching_endpoints(source_endpoints: list[str], domain_entries: list[MemoryEntry]) -> list[str]:
    domain_eps = set(_collect_endpoint_tags(domain_entries))
    return [ep for ep in source_endpoints if ep in domain_eps]
