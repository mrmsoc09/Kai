"""
Inference Engine — Opportunity Detection
=========================================
Converts a single confirmed vulnerability into cross-target exploitation
opportunities by pattern matching against intelligence memory.

Core concept:
  "We found it once → we find it everywhere it exists."

Workflow:
  1. Pull confirmed FINDING or PATTERN_SIGNATURE entries from memory
  2. Match against candidate targets using opportunity_targeting.py
  3. Rank opportunities by expected yield and duplicate risk
  4. Emit InferenceOpportunity objects for operator review / approval

Critical constraints:
  - Only patterns with ValidationStatus.CONFIRMED feed opportunities
  - Opportunities never expand beyond authorized scope
  - Duplicate detection prevents re-scanning already confirmed targets
  - min_confidence gates prevent noise-based opportunity generation

Integration:
  - IntelligenceQueryEngine  — source of confirmed patterns
  - IntelligenceGraph        — exploit chain traversal
  - MemoryManager            — read confirmed findings
  - ToolSequenceTracker      — recommend tool sequences for exploitation
  - opportunity_targeting.py — rank candidate targets
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .intelligence_memory import (
    MemoryEntry,
    MemoryManager,
    MemoryScope,
    MemoryType,
    ValidationStatus,
    get_memory_manager,
)
from .intelligence_query import IntelligenceQueryEngine, get_query_engine
from .intelligence_graph import IntelligenceGraph, EdgeType, get_intelligence_graph
from .memory_access_control import AccessPolicy, AgentClass
from .decision_engine.opportunity_reasoner import OpportunityReasoner, OpportunitySignal
from .exploit_graph import build_exploit_chains
from .opportunity_expansion import ExpansionSource, OpportunityExpansionEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class OpportunityStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


# ---------------------------------------------------------------------------
# Core dataclass
# ---------------------------------------------------------------------------


@dataclass
class InferenceOpportunity:
    """
    A hypothesis that a known vulnerability pattern exists on N candidate targets.

    Fields:
      opportunity_id      — unique stable ID
      source_memory_id    — the MemoryEntry (FINDING or PATTERN_SIGNATURE) that triggered this
      vuln_type           — vulnerability class (sqli, xss, ssrf, ...)
      pattern_signature_id— optional: the compressed PATTERN_SIGNATURE backing this inference
      candidate_targets   — list of domain strings ranked by expected yield
      target_scores       — per-target match scores (domain → float)
      confidence_score    — how confident we are this pattern applies to candidates
      estimated_yield     — expected number of confirmed vulns if we probe all candidates
      duplicate_risk      — 0.0–1.0; proportion of candidates we may have already confirmed
      recommended_tools   — tool sequence IDs from ToolSequenceTracker
      status              — lifecycle state
      created_at          — unix timestamp
      updated_at          — unix timestamp
      notes               — free-form annotation
    """

    opportunity_id: str
    source_memory_id: str
    vuln_type: str
    candidate_targets: list[str]
    confidence_score: float
    estimated_yield: float
    duplicate_risk: float
    status: OpportunityStatus = OpportunityStatus.PROPOSED
    pattern_signature_id: str | None = None
    source_type: str = "memory_pattern"
    source_object_id: str | None = None
    target_scores: dict[str, float] = field(default_factory=dict)
    recommended_tools: list[str] = field(default_factory=list)
    expansion_candidates: list[dict[str, Any]] = field(default_factory=list)
    approved_targets: list[str] = field(default_factory=list)
    rejected_targets: list[str] = field(default_factory=list)
    target_batches: list[dict[str, Any]] = field(default_factory=list)
    blocked_targets: list[dict[str, str]] = field(default_factory=list)
    expansion_rationale: str = ""
    expansion_score: float = 0.0
    expected_report_quality: float = 0.0
    recommended_execution_order: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "source_memory_id": self.source_memory_id,
            "vuln_type": self.vuln_type,
            "pattern_signature_id": self.pattern_signature_id,
            "candidate_targets": self.candidate_targets,
            "target_scores": self.target_scores,
            "confidence_score": round(self.confidence_score, 4),
            "estimated_yield": round(self.estimated_yield, 2),
            "duplicate_risk": round(self.duplicate_risk, 4),
            "recommended_tools": self.recommended_tools,
            "status": self.status.value,
            "source_type": self.source_type,
            "source_object_id": self.source_object_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expansion_candidates": self.expansion_candidates,
            "approved_targets": self.approved_targets,
            "rejected_targets": self.rejected_targets,
            "target_batches": self.target_batches,
            "blocked_targets": self.blocked_targets,
            "expansion_rationale": self.expansion_rationale,
            "expansion_score": round(self.expansion_score, 4),
            "expected_report_quality": round(self.expected_report_quality, 4),
            "recommended_execution_order": self.recommended_execution_order,
            "notes": self.notes,
        }

    def approve(self) -> None:
        if self.status != OpportunityStatus.PROPOSED:
            raise ValueError(f"Cannot approve opportunity in state {self.status.value}")
        self.status = OpportunityStatus.APPROVED
        self.updated_at = time.time()

    def reject(self, reason: str = "") -> None:
        self.status = OpportunityStatus.REJECTED
        self.notes = reason
        self.updated_at = time.time()

    def mark_executing(self) -> None:
        if self.status != OpportunityStatus.APPROVED:
            raise ValueError(f"Cannot execute opportunity in state {self.status.value}")
        self.status = OpportunityStatus.EXECUTING
        self.updated_at = time.time()

    def mark_completed(self, notes: str = "") -> None:
        self.status = OpportunityStatus.COMPLETED
        self.notes = notes
        self.updated_at = time.time()


# ---------------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------------


@dataclass
class DetectionResult:
    """Output of a single opportunity detection run."""

    opportunities: list[InferenceOpportunity]
    patterns_evaluated: int
    candidates_evaluated: int
    duplicates_suppressed: int
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_count": len(self.opportunities),
            "patterns_evaluated": self.patterns_evaluated,
            "candidates_evaluated": self.candidates_evaluated,
            "duplicates_suppressed": self.duplicates_suppressed,
            "duration_ms": round(self.duration_ms, 2),
            "opportunities": [o.to_dict() for o in self.opportunities],
        }


# ---------------------------------------------------------------------------
# Opportunity engine
# ---------------------------------------------------------------------------


class OpportunityEngine:
    """
    Detects and ranks cross-target exploitation opportunities from intelligence memory.

    Usage::

        engine = OpportunityEngine()
        result = engine.detect(allowed_domains=["example.com", "target.org"])
        for opp in result.opportunities:
            print(opp.vuln_type, opp.candidate_targets, opp.estimated_yield)
    """

    def __init__(
        self,
        manager: MemoryManager | None = None,
        query_engine: IntelligenceQueryEngine | None = None,
        graph: IntelligenceGraph | None = None,
    ) -> None:
        self._manager = manager or get_memory_manager()
        self._query = query_engine or get_query_engine()
        self._graph = graph or get_intelligence_graph()

    # -- Primary entry point --------------------------------------------------

    def detect(
        self,
        allowed_domains: list[str],
        min_confidence: float = 0.70,
        min_occurrence_count: int = 2,
        max_opportunities: int = 20,
        deduplicate: bool = True,
    ) -> DetectionResult:
        """
        Scan intelligence memory for repeatable patterns and generate opportunities
        against the provided allowed_domains list.

        Args:
            allowed_domains:       Domains we may probe (scope-bounded by caller).
            min_confidence:        Minimum pattern confidence to create an opportunity.
            min_occurrence_count:  Minimum times a pattern must have been seen before
                                   we propagate it to new targets.
            max_opportunities:     Cap on returned opportunities.
            deduplicate:           Skip opportunities where duplicate_risk > 0.85.

        Returns:
            DetectionResult with ranked InferenceOpportunity list.
        """
        start = time.monotonic()

        if not allowed_domains:
            return DetectionResult(
                opportunities=[],
                patterns_evaluated=0,
                candidates_evaluated=0,
                duplicates_suppressed=0,
                duration_ms=0.0,
            )

        # Use ANALYST policy — read all confirmed findings across scopes
        analyst_policy = AccessPolicy.for_agent(AgentClass.ANALYST)

        # Pull confirmed pattern signatures (compressed multi-occurrence patterns)
        pattern_entries = self._manager.query(
            memory_type=MemoryType.PATTERN_SIGNATURE,
            validation_status=ValidationStatus.CONFIRMED,
            min_confidence=min_confidence,
            limit=100,
        )

        # Also pull high-confidence confirmed findings (single-target but actionable)
        finding_entries = self._manager.query(
            memory_type=MemoryType.FINDING,
            validation_status=ValidationStatus.CONFIRMED,
            min_confidence=min_confidence + 0.05,  # slightly higher bar for raw findings
            limit=200,
        )

        pattern_entries = analyst_policy.filter(pattern_entries)
        finding_entries = analyst_policy.filter(finding_entries)

        all_source_entries = pattern_entries + finding_entries
        patterns_evaluated = len(all_source_entries)

        # Collect all confirmed domains we already have findings for (for dedup)
        confirmed_domains: set[str] = {
            e.target_fingerprint.domain
            for e in all_source_entries
            if e.target_fingerprint.domain and e.validation_status == ValidationStatus.CONFIRMED
        }

        # Import here to avoid circular at module level
        from .opportunity_targeting import OpportunityTargeter

        targeter = OpportunityTargeter(self._manager, self._query)
        reasoner = OpportunityReasoner()
        expansion_engine = OpportunityExpansionEngine(manager=self._manager)

        opportunities: list[InferenceOpportunity] = []
        duplicates_suppressed = 0
        candidates_evaluated = 0

        # Group entries by vuln_type to avoid redundant processing
        by_vuln: dict[str, list[MemoryEntry]] = {}
        for entry in all_source_entries:
            vtype = _extract_vuln_type(entry)
            if not vtype:
                continue
            by_vuln.setdefault(vtype, []).append(entry)

        for vuln_type, entries in by_vuln.items():
            # Use the highest-confidence entry as the source for this vuln type
            source_entry = max(entries, key=lambda e: e.confidence_score)

            # Skip single-occurrence raw findings with low confidence
            is_pattern = source_entry.memory_type == MemoryType.PATTERN_SIGNATURE
            occurrence_count = _get_occurrence_count(source_entry)
            if not is_pattern and occurrence_count < min_occurrence_count:
                continue

            # Find candidate targets from allowed_domains that match this pattern
            matches = targeter.find_targets(
                source_entry=source_entry,
                allowed_domains=allowed_domains,
                vuln_type=vuln_type,
                min_score=0.30,
            )
            candidates_evaluated += len(matches)

            # Exclude source domain(s) from candidates (already confirmed there)
            source_domain = source_entry.target_fingerprint.domain
            novel_matches = [m for m in matches if m.domain != source_domain]

            if not novel_matches:
                continue

            # Calculate duplicate risk: what fraction are already confirmed
            already_confirmed = sum(1 for m in novel_matches if m.domain in confirmed_domains)
            dup_risk = already_confirmed / len(novel_matches) if novel_matches else 0.0

            if deduplicate and dup_risk > 0.85:
                duplicates_suppressed += 1
                continue

            # Pattern signature ID (if source is a pattern)
            pat_sig_id = source_entry.memory_id if is_pattern else None
            if not is_pattern:
                # Look for a pattern signature in the graph covering this finding
                pattern_edges = self._graph.get_neighbors(
                    source_entry.memory_id, EdgeType.PATTERN_COVERS
                )
                if pattern_edges:
                    pat_sig_id = pattern_edges[0].target_id

            reasoned_rows = reasoner.generate(
                [
                    OpportunitySignal(
                        source_memory_id=source_entry.memory_id,
                        source_pattern_id=pat_sig_id,
                        vuln_type=vuln_type,
                        candidate_targets=[m.domain for m in novel_matches],
                        target_scores={m.domain: round(m.score, 4) for m in novel_matches},
                        pattern_signature_strength=float(source_entry.confidence_score),
                        repeated_findings=max(1, len(entries)),
                        tech_stack_similarity=sum(m.tech_score for m in novel_matches) / len(novel_matches),
                        duplicate_risk=dup_risk,
                    )
                ],
                min_confidence=min_confidence,
            )
            if not reasoned_rows:
                continue

            reasoned = reasoned_rows[0]
            chain_findings = _chain_findings_for_opportunity(
                entries=entries,
                candidate_targets=reasoned.candidate_targets,
                vuln_type=vuln_type,
            )
            chains = build_exploit_chains(chain_findings, [], [])
            chain_bonus = max((chain.score for chain in chains), default=0.0)
            chain_confidence = max((chain.confidence_score for chain in chains), default=0.0)
            boosted_confidence = min(
                0.99,
                reasoned.confidence_score + (0.10 * chain_bonus) + (0.05 * chain_confidence),
            )
            boosted_yield = reasoned.estimated_yield * (1.0 + (0.25 * chain_bonus))

            # Recommend tool sequences from graph
            tool_seq_ids = _get_recommended_tools(self._graph, source_entry.memory_id)
            if chains:
                chain_ids = [chain.chain_id for chain in chains[:3]]
            else:
                chain_ids = []

            source_type = "pattern_signature" if is_pattern else "validated_finding"
            chain_payload = chains[0].to_dict() if chains else None
            expansion = expansion_engine.expand(
                source=ExpansionSource(
                    source_type=source_type,
                    source_object_id=source_entry.memory_id,
                    vuln_type=vuln_type,
                    source_target=source_domain or "",
                    confidence=float(source_entry.confidence_score),
                    risk_band="high" if vuln_type in {"rce", "sqli", "auth_bypass"} else "medium",
                    tech_stack=list(source_entry.target_fingerprint.tech_stack),
                    endpoint_shapes=[tag[len("endpoint:"):] for tag in source_entry.tags if tag.startswith("endpoint:")],
                    pattern_tags=list(source_entry.tags),
                    service_fingerprints=list(source_entry.target_fingerprint.services),
                    exploit_chain=chain_payload,
                    expected_yield=boosted_yield,
                    tenant_id=source_entry.tenant_id,
                ),
                candidate_targets=[m.domain for m in novel_matches],
                max_candidates=25,
                max_batch_size=5,
            )
            expanded_targets = [row.target for row in expansion.expansion_candidates] or reasoned.candidate_targets
            expanded_target_scores = {row.target: round(row.similarity_score, 4) for row in expansion.expansion_candidates}
            if not expanded_target_scores:
                expanded_target_scores = reasoned.target_scores

            opp = InferenceOpportunity(
                opportunity_id=reasoned.opportunity_id,
                source_memory_id=source_entry.memory_id,
                vuln_type=vuln_type,
                pattern_signature_id=pat_sig_id,
                source_type=source_type,
                source_object_id=source_entry.memory_id,
                candidate_targets=expanded_targets,
                target_scores=expanded_target_scores,
                confidence_score=max(boosted_confidence, expansion.confidence),
                estimated_yield=max(boosted_yield, expansion.expected_yield),
                duplicate_risk=max(reasoned.duplicate_risk, expansion.duplicate_risk),
                recommended_tools=tool_seq_ids[:5],
                expansion_candidates=[row.to_dict() for row in expansion.expansion_candidates],
                target_batches=[row.to_dict() for row in expansion.target_batches],
                blocked_targets=[dict(row) for row in expansion.blocked_targets],
                expansion_rationale=expansion.expansion_rationale,
                expansion_score=expansion.expansion_score,
                expected_report_quality=expansion.expected_report_quality,
                recommended_execution_order=expansion.recommended_execution_order,
                notes=(
                    f"{reasoned.reasoning_summary};"
                    f"chain_count={len(chains)};chain_bonus={chain_bonus:.2f};chain_ids={','.join(chain_ids)};"
                    f"expansion_candidates={len(expansion.expansion_candidates)};blocked={len(expansion.blocked_targets)}"
                ),
            )
            opportunities.append(opp)

        # Rank by estimated yield descending, then confidence
        opportunities.sort(key=lambda o: (o.estimated_yield, o.confidence_score), reverse=True)
        opportunities = opportunities[:max_opportunities]

        logger.info(
            "opportunity_engine.detect patterns=%d candidates=%d opportunities=%d dups_suppressed=%d",
            patterns_evaluated,
            candidates_evaluated,
            len(opportunities),
            duplicates_suppressed,
        )

        return DetectionResult(
            opportunities=opportunities,
            patterns_evaluated=patterns_evaluated,
            candidates_evaluated=candidates_evaluated,
            duplicates_suppressed=duplicates_suppressed,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    # -- Detect for a specific vuln type -------------------------------------

    def detect_for_vuln_type(
        self,
        vuln_type: str,
        allowed_domains: list[str],
        min_confidence: float = 0.65,
    ) -> list[InferenceOpportunity]:
        """
        Focused detection for a single vulnerability class.

        Faster than full detect() when you know what you're looking for.
        """
        analyst_policy = AccessPolicy.for_agent(AgentClass.ANALYST)

        # Pull patterns and findings for this specific vuln type
        pattern_results, _ = self._query.find_exploit_patterns(
            vuln_type=vuln_type,
            policy=analyst_policy,
            min_confidence=min_confidence,
            limit=20,
        )
        finding_results, _ = self._query.find_prior_vuln(
            vuln_type=vuln_type,
            policy=analyst_policy,
            min_confidence=min_confidence + 0.05,
            limit=50,
        )

        if not pattern_results and not finding_results:
            return []

        # Use full detect with a filtered scope
        result = self.detect(
            allowed_domains=allowed_domains,
            min_confidence=min_confidence,
            max_opportunities=10,
        )
        return [o for o in result.opportunities if o.vuln_type == vuln_type]

    # -- Feedback loop --------------------------------------------------------

    def record_outcome(
        self,
        opportunity: InferenceOpportunity,
        confirmed_domains: list[str],
        failed_domains: list[str],
    ) -> None:
        """
        Record actual outcome of opportunity execution back into intelligence.

        Updates graph edges to strengthen or weaken future pattern matching.
        Used by the strategy learning feedback loop.
        """
        success_rate = len(confirmed_domains) / max(1, len(opportunity.candidate_targets))

        # Log outcome for strategy learner
        logger.info(
            "opportunity_engine.outcome opp=%s vuln=%s candidates=%d confirmed=%d failed=%d yield=%.2f",
            opportunity.opportunity_id,
            opportunity.vuln_type,
            len(opportunity.candidate_targets),
            len(confirmed_domains),
            len(failed_domains),
            success_rate,
        )

        # Add graph edges for newly confirmed targets
        for domain in confirmed_domains:
            # Find or create a memory entry ID for this domain (best effort)
            existing = self._manager.query(
                memory_type=MemoryType.FINDING,
                domain=domain,
                min_confidence=0.5,
                limit=1,
            )
            if existing and opportunity.pattern_signature_id:
                self._graph.add_edge(
                    opportunity.pattern_signature_id,
                    existing[0].memory_id,
                    EdgeType.PATTERN_COVERS,
                    weight=0.9,
                )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_vuln_type(entry: MemoryEntry) -> str:
    for tag in entry.tags:
        if tag.startswith("vuln_type:"):
            return tag[len("vuln_type:"):]
    return ""


def _get_occurrence_count(entry: MemoryEntry) -> int:
    """Extract occurrence count from pattern signature payload (best-effort)."""
    try:
        data = entry.decrypt()
        if isinstance(data, dict):
            return int(data.get("occurrence_count", 1))
    except Exception:
        pass
    return 1


def _get_recommended_tools(graph: IntelligenceGraph, memory_id: str) -> list[str]:
    """Get tool sequence IDs linked from this memory entry via graph."""
    edges = graph.get_neighbors(memory_id, EdgeType.EXPLOIT_TO_TOOL_SEQ)
    return [e.target_id for e in edges[:5]]


def _chain_findings_for_opportunity(
    *,
    entries: list[MemoryEntry],
    candidate_targets: list[str],
    vuln_type: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        rows.append(
            {
                "finding_id": entry.memory_id,
                "vuln_type": vuln_type,
                "target": entry.target_fingerprint.domain,
                "severity": "high" if entry.validation_status == ValidationStatus.CONFIRMED else "medium",
                "validated": entry.validation_status == ValidationStatus.CONFIRMED,
                "confidence_score": entry.confidence_score,
                "technologies": list(entry.target_fingerprint.tech_stack),
                "duplicate_risk": 0.0,
            }
        )
    for index, domain in enumerate(candidate_targets, start=1):
        rows.append(
            {
                "finding_id": f"candidate:{vuln_type}:{index}:{domain}",
                "vuln_type": vuln_type,
                "target": domain,
                "severity": "medium",
                "validated": False,
                "confidence_score": 0.55,
                "duplicate_risk": 0.1,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

import threading as _threading

_engine_instance: OpportunityEngine | None = None
_engine_lock = _threading.Lock()


def get_opportunity_engine() -> OpportunityEngine:
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = OpportunityEngine()
        return _engine_instance
