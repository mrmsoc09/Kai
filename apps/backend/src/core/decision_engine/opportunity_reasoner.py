from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _mean(values: Sequence[float]) -> float:
    rows = [float(row) for row in values]
    if not rows:
        return 0.0
    return _clamp(sum(rows) / len(rows))


class OpportunityAmbiguityResolver(Protocol):
    """
    Optional LLM-assisted resolver.
    Returns confidence adjustments keyed by opportunity_id.
    """

    def __call__(self, opportunities: list["ReasonedOpportunity"]) -> Mapping[str, float]:
        ...


@dataclass(frozen=True)
class OpportunitySignal:
    source_memory_id: str
    source_pattern_id: str | None
    vuln_type: str
    candidate_targets: list[str]
    target_scores: dict[str, float]
    pattern_signature_strength: float
    repeated_findings: int
    tech_stack_similarity: float
    duplicate_risk: float


@dataclass(frozen=True)
class ReasonedOpportunity:
    opportunity_id: str
    source_memory_id: str
    source_pattern_id: str | None
    vuln_type: str
    candidate_targets: list[str]
    target_scores: dict[str, float] = field(default_factory=dict)
    confidence_score: float = 0.0
    estimated_yield: float = 0.0
    duplicate_risk: float = 0.0
    status: str = "proposed"
    reasoning_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "source_memory_id": self.source_memory_id,
            "source_pattern_id": self.source_pattern_id,
            "vuln_type": self.vuln_type,
            "candidate_targets": list(self.candidate_targets),
            "target_scores": {key: round(value, 4) for key, value in self.target_scores.items()},
            "confidence_score": round(self.confidence_score, 4),
            "estimated_yield": round(self.estimated_yield, 4),
            "duplicate_risk": round(self.duplicate_risk, 4),
            "status": self.status,
            "reasoning_summary": self.reasoning_summary,
        }


class OpportunityReasoner:
    """
    Deterministic-first opportunity generation from pattern and targeting signals.
    """

    def generate(
        self,
        signals: Sequence[OpportunitySignal],
        *,
        min_confidence: float = 0.30,
        ambiguity_resolver: OpportunityAmbiguityResolver | None = None,
    ) -> list[ReasonedOpportunity]:
        opportunities: list[ReasonedOpportunity] = []
        for signal in signals:
            if not signal.candidate_targets:
                continue
            confidence = self._score_confidence(signal)
            if confidence < min_confidence:
                continue
            estimated_yield = self._estimate_yield(signal, confidence)
            fingerprint = (
                f"{signal.vuln_type}|{signal.source_memory_id}|"
                f"{'|'.join(sorted(signal.candidate_targets))}"
            )
            opportunity_id = f"opp-{hashlib.sha1(fingerprint.encode('utf-8')).hexdigest()[:12]}"
            reasoning_summary = (
                f"pattern={signal.pattern_signature_strength:.2f} "
                f"target_match={_mean(signal.target_scores.values()):.2f} "
                f"tech={signal.tech_stack_similarity:.2f} "
                f"repeat={min(signal.repeated_findings, 20)} "
                f"dup={signal.duplicate_risk:.2f}"
            )
            opportunities.append(
                ReasonedOpportunity(
                    opportunity_id=opportunity_id,
                    source_memory_id=signal.source_memory_id,
                    source_pattern_id=signal.source_pattern_id,
                    vuln_type=signal.vuln_type,
                    candidate_targets=list(signal.candidate_targets),
                    target_scores={key: _clamp(value) for key, value in signal.target_scores.items()},
                    confidence_score=round(confidence, 4),
                    estimated_yield=round(estimated_yield, 4),
                    duplicate_risk=round(_clamp(signal.duplicate_risk), 4),
                    reasoning_summary=reasoning_summary,
                )
            )

        opportunities.sort(
            key=lambda row: (row.estimated_yield, row.confidence_score),
            reverse=True,
        )
        if ambiguity_resolver and self._is_ambiguous(opportunities):
            adjustments = ambiguity_resolver(opportunities)
            opportunities = self._apply_adjustments(opportunities, adjustments)
        return opportunities

    def _score_confidence(self, signal: OpportunitySignal) -> float:
        target_match = _mean(signal.target_scores.values())
        repetition_strength = _clamp((max(0, signal.repeated_findings) - 1) / 5.0)
        base = _clamp(signal.pattern_signature_strength) * (0.65 + (0.35 * target_match))
        context_bonus = (
            0.10 * _clamp(signal.tech_stack_similarity)
            + 0.10 * repetition_strength
            - (0.25 * _clamp(signal.duplicate_risk))
        )
        return _clamp(base + context_bonus)

    def _estimate_yield(self, signal: OpportunitySignal, confidence: float) -> float:
        candidate_count = len(signal.candidate_targets)
        novelty_factor = 1.0 - (0.9 * _clamp(signal.duplicate_risk))
        return max(0.0, candidate_count * confidence * novelty_factor)

    def _is_ambiguous(self, opportunities: Sequence[ReasonedOpportunity]) -> bool:
        if len(opportunities) < 2:
            return False
        return abs(opportunities[0].confidence_score - opportunities[1].confidence_score) <= 0.05

    def _apply_adjustments(
        self,
        opportunities: Sequence[ReasonedOpportunity],
        adjustments: Mapping[str, float],
    ) -> list[ReasonedOpportunity]:
        updated: list[ReasonedOpportunity] = []
        for row in opportunities:
            delta = float(adjustments.get(row.opportunity_id, 0.0))
            updated.append(
                ReasonedOpportunity(
                    opportunity_id=row.opportunity_id,
                    source_memory_id=row.source_memory_id,
                    source_pattern_id=row.source_pattern_id,
                    vuln_type=row.vuln_type,
                    candidate_targets=row.candidate_targets,
                    target_scores=row.target_scores,
                    confidence_score=round(_clamp(row.confidence_score + delta), 4),
                    estimated_yield=row.estimated_yield,
                    duplicate_risk=row.duplicate_risk,
                    status=row.status,
                    reasoning_summary=row.reasoning_summary,
                )
            )
        updated.sort(key=lambda item: (item.estimated_yield, item.confidence_score), reverse=True)
        return updated
