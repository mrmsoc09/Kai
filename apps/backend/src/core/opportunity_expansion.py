from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .exploit_graph import build_exploit_chains
from .intelligence_memory import MemoryManager, MemoryType, ValidationStatus, get_memory_manager
from .report_engine import ReportEngine, get_report_engine
from .scope_guardrails import (
    ScopeDecision,
    ScopePolicy,
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)
from .target_similarity_engine import SimilaritySource, TargetSimilarityEngine


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_target(value: Any) -> str:
    raw = _normalize_text(value).lower()
    if not raw:
        return ""
    if "://" in raw:
        from urllib.parse import urlparse

        parsed = urlparse(raw)
        raw = parsed.hostname or parsed.path or raw
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw.strip(".")


def _risk_rank(value: str) -> int:
    mapping = {"low": 0, "medium": 1, "high": 2}
    return mapping.get(value, 1)


@dataclass(frozen=True)
class ExpansionSource:
    source_type: str
    source_object_id: str
    vuln_type: str
    source_target: str = ""
    confidence: float = 0.6
    risk_band: str = "medium"
    tech_stack: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    endpoint_shapes: list[str] = field(default_factory=list)
    pattern_tags: list[str] = field(default_factory=list)
    service_fingerprints: list[str] = field(default_factory=list)
    exploit_chain: dict[str, Any] | None = None
    expected_yield: float = 1.0
    tenant_id: str | None = None

    def to_similarity_source(self) -> SimilaritySource:
        return SimilaritySource(
            source_type=self.source_type,
            source_object_id=self.source_object_id,
            vuln_type=self.vuln_type,
            source_target=self.source_target,
            confidence=self.confidence,
            tech_stack=self.tech_stack,
            headers=self.headers,
            endpoint_shapes=self.endpoint_shapes,
            pattern_tags=self.pattern_tags,
            service_fingerprints=self.service_fingerprints,
        )


@dataclass(frozen=True)
class ExpansionCandidate:
    target: str
    similarity_score: float
    confidence: float
    memory_match_strength: float
    duplicate_risk: float
    target_importance: float
    expected_report_quality: float
    expansion_score: float
    estimated_yield: float
    risk_band: str
    matching_factors: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "similarity_score": round(self.similarity_score, 4),
            "confidence": round(self.confidence, 4),
            "memory_match_strength": round(self.memory_match_strength, 4),
            "duplicate_risk": round(self.duplicate_risk, 4),
            "target_importance": round(self.target_importance, 4),
            "expected_report_quality": round(self.expected_report_quality, 4),
            "expansion_score": round(self.expansion_score, 4),
            "estimated_yield": round(self.estimated_yield, 4),
            "risk_band": self.risk_band,
            "matching_factors": list(self.matching_factors),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class TargetBatch:
    batch_id: str
    targets: list[str]
    expected_yield: float
    risk_band: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "targets": list(self.targets),
            "expected_yield": round(self.expected_yield, 4),
            "risk_band": self.risk_band,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class OpportunityExpansionResult:
    source_type: str
    source_object_id: str
    source_vuln_type: str
    source_target: str
    expansion_candidates: list[ExpansionCandidate]
    target_batches: list[TargetBatch]
    blocked_targets: list[dict[str, str]]
    expansion_score: float
    expected_yield: float
    duplicate_risk: float
    confidence: float
    expected_report_quality: float
    recommended_execution_order: list[str]
    expansion_rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_object_id": self.source_object_id,
            "source_vuln_type": self.source_vuln_type,
            "source_target": self.source_target,
            "expansion_candidates": [row.to_dict() for row in self.expansion_candidates],
            "target_batches": [row.to_dict() for row in self.target_batches],
            "blocked_targets": [dict(row) for row in self.blocked_targets],
            "expansion_score": round(self.expansion_score, 4),
            "expected_yield": round(self.expected_yield, 4),
            "duplicate_risk": round(self.duplicate_risk, 4),
            "confidence": round(self.confidence, 4),
            "expected_report_quality": round(self.expected_report_quality, 4),
            "recommended_execution_order": list(self.recommended_execution_order),
            "expansion_rationale": self.expansion_rationale,
        }


class OpportunityExpansionEngine:
    """
    Expands one validated source signal into ranked and batched target opportunities.
    """

    def __init__(
        self,
        *,
        similarity_engine: TargetSimilarityEngine | None = None,
        manager: MemoryManager | None = None,
        report_engine: ReportEngine | None = None,
        policy: ScopePolicy | None = None,
    ) -> None:
        self._similarity = similarity_engine or TargetSimilarityEngine()
        self._manager = manager or get_memory_manager()
        self._reports = report_engine or get_report_engine()
        self._policy = policy or load_scope_policy()

    def expand(
        self,
        *,
        source: ExpansionSource,
        candidate_targets: list[str],
        max_candidates: int = 25,
        max_batch_size: int = 5,
    ) -> OpportunityExpansionResult:
        allowed_targets, blocked_targets = self._scope_filter(candidate_targets)
        similarity_rows = self._similarity.rank_targets(
            source.to_similarity_source(),
            allowed_targets,
            min_similarity=0.20,
            limit=max_candidates,
        )

        chain_bonus = self._chain_bonus(source)
        candidates: list[ExpansionCandidate] = []
        for row in similarity_rows:
            duplicate_risk = self._duplicate_risk(source.vuln_type, row.target, row.memory_match_strength)
            expected_report_quality = self._expected_report_quality(row.expected_report_quality, row.similarity_score, source.confidence)
            expansion_score = self._expansion_score(
                source_confidence=source.confidence,
                chain_bonus=chain_bonus,
                memory_corroboration=row.memory_match_strength,
                similarity_strength=row.similarity_score,
                target_importance=row.target_importance,
                duplicate_risk=duplicate_risk,
                expected_report_quality=expected_report_quality,
            )
            estimated_yield = self._estimated_yield(
                expansion_score=expansion_score,
                duplicate_risk=duplicate_risk,
                source_expected_yield=max(0.1, float(source.expected_yield or 1.0)),
                target_importance=row.target_importance,
            )
            risk_band = self._candidate_risk_band(source.risk_band, duplicate_risk, expansion_score)
            rationale = (
                f"{row.rationale}; chain_bonus={chain_bonus:.2f}; "
                f"dup={duplicate_risk:.2f}; report_quality={expected_report_quality:.2f}"
            )
            candidates.append(
                ExpansionCandidate(
                    target=row.target,
                    similarity_score=row.similarity_score,
                    confidence=row.confidence,
                    memory_match_strength=row.memory_match_strength,
                    duplicate_risk=duplicate_risk,
                    target_importance=row.target_importance,
                    expected_report_quality=expected_report_quality,
                    expansion_score=expansion_score,
                    estimated_yield=estimated_yield,
                    risk_band=risk_band,
                    matching_factors=row.matching_factors,
                    rationale=rationale,
                )
            )

        candidates.sort(key=lambda row: (row.expansion_score, row.estimated_yield, row.confidence), reverse=True)
        batches = self._build_batches(candidates, max_batch_size=max_batch_size)
        ordered_batch_ids = [row.batch_id for row in batches]

        expected_yield = sum(row.estimated_yield for row in candidates)
        average_duplicate = self._mean([row.duplicate_risk for row in candidates])
        average_confidence = self._mean([row.confidence for row in candidates])
        average_report_quality = self._mean([row.expected_report_quality for row in candidates])
        expansion_score = self._mean([row.expansion_score for row in candidates])
        rationale = (
            f"candidates={len(candidates)} blocked={len(blocked_targets)} chain_bonus={chain_bonus:.2f} "
            f"avg_similarity={self._mean([row.similarity_score for row in candidates]):.2f} "
            f"avg_dup={average_duplicate:.2f}"
        )

        return OpportunityExpansionResult(
            source_type=source.source_type,
            source_object_id=source.source_object_id,
            source_vuln_type=source.vuln_type,
            source_target=source.source_target,
            expansion_candidates=candidates,
            target_batches=batches,
            blocked_targets=blocked_targets,
            expansion_score=expansion_score,
            expected_yield=expected_yield,
            duplicate_risk=average_duplicate,
            confidence=average_confidence,
            expected_report_quality=average_report_quality,
            recommended_execution_order=ordered_batch_ids,
            expansion_rationale=rationale,
        )

    def _scope_filter(self, targets: list[str]) -> tuple[list[str], list[dict[str, str]]]:
        allowed: list[str] = []
        blocked: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in targets:
            target = _normalize_target(row)
            if not target or target in seen:
                continue
            seen.add(target)
            decision: ScopeDecision = evaluate_target_scope(target, self._policy)
            audit_scope_decision(decision)
            if decision.allowed:
                allowed.append(target)
            else:
                blocked.append({"target": target, "reason": decision.reason})
        return allowed, blocked

    def _chain_bonus(self, source: ExpansionSource) -> float:
        if isinstance(source.exploit_chain, dict):
            explicit = _clamp(float(source.exploit_chain.get("confidence_score", source.exploit_chain.get("score", 0.7))))
            return max(0.3, explicit)

        related = self._manager.query(tags=[f"vuln_type:{source.vuln_type}"], min_confidence=0.5, limit=30)
        if len(related) < 2:
            return 0.0
        findings = [
            {
                "finding_id": row.memory_id,
                "vuln_type": source.vuln_type,
                "target": row.target_fingerprint.domain,
                "severity": "high" if row.validation_status == ValidationStatus.CONFIRMED else "medium",
                "validated": row.validation_status == ValidationStatus.CONFIRMED,
                "confidence_score": row.confidence_score,
                "technologies": list(row.target_fingerprint.tech_stack),
            }
            for row in related
            if row.target_fingerprint.domain
        ]
        chains = build_exploit_chains(findings, [], [])
        if not chains:
            return 0.0
        return _clamp(max(row.confidence_score for row in chains))

    def _duplicate_risk(self, vuln_type: str, target: str, memory_match_strength: float) -> float:
        confirmed = self._manager.query(
            memory_type=MemoryType.FINDING,
            tags=[f"vuln_type:{vuln_type}", vuln_type],
            validation_status=ValidationStatus.CONFIRMED,
            domain=target,
            limit=50,
        )
        report_rows = self._reports.list_reports(target=target)
        exact_reports = [row for row in report_rows if _normalize_text(getattr(row, "vulnerability_type", "")).lower() == vuln_type.lower()]
        exact_report_risk = min(1.0, len(exact_reports) / 3.0)
        confirmed_risk = min(1.0, len(confirmed) / 2.0)
        return _clamp((0.55 * confirmed_risk) + (0.30 * exact_report_risk) + (0.15 * memory_match_strength))

    def _expected_report_quality(self, historical: float, similarity: float, source_confidence: float) -> float:
        return _clamp((0.50 * historical) + (0.30 * similarity) + (0.20 * source_confidence))

    def _expansion_score(
        self,
        *,
        source_confidence: float,
        chain_bonus: float,
        memory_corroboration: float,
        similarity_strength: float,
        target_importance: float,
        duplicate_risk: float,
        expected_report_quality: float,
    ) -> float:
        return _clamp(
            0.22 * _clamp(source_confidence)
            + 0.14 * _clamp(chain_bonus)
            + 0.18 * _clamp(memory_corroboration)
            + 0.22 * _clamp(similarity_strength)
            + 0.12 * _clamp(target_importance)
            + 0.16 * _clamp(expected_report_quality)
            - 0.24 * _clamp(duplicate_risk)
        )

    def _estimated_yield(
        self,
        *,
        expansion_score: float,
        duplicate_risk: float,
        source_expected_yield: float,
        target_importance: float,
    ) -> float:
        novelty = max(0.15, 1.0 - duplicate_risk)
        return max(0.0, source_expected_yield * expansion_score * novelty * (0.7 + (0.6 * target_importance)))

    def _candidate_risk_band(self, source_risk_band: str, duplicate_risk: float, expansion_score: float) -> str:
        if source_risk_band == "high" or duplicate_risk >= 0.70:
            return "high"
        if duplicate_risk >= 0.45 or expansion_score >= 0.75:
            return "medium"
        return "low"

    def _build_batches(self, candidates: list[ExpansionCandidate], *, max_batch_size: int) -> list[TargetBatch]:
        if not candidates:
            return []
        max_batch_size = max(1, min(20, int(max_batch_size)))
        risk_limits = {
            "low": min(max_batch_size, 6),
            "medium": min(max_batch_size, 4),
            "high": min(max_batch_size, 2),
        }
        groups: dict[str, list[ExpansionCandidate]] = {"low": [], "medium": [], "high": []}
        for row in candidates:
            groups.setdefault(row.risk_band, []).append(row)
        for bucket in groups.values():
            bucket.sort(key=lambda row: (row.expansion_score, row.estimated_yield), reverse=True)

        batches: list[TargetBatch] = []
        for risk_band, rows in groups.items():
            limit = risk_limits.get(risk_band, max_batch_size)
            for index in range(0, len(rows), limit):
                chunk = rows[index: index + limit]
                if not chunk:
                    continue
                key = "|".join(row.target for row in chunk)
                batch_id = f"batch_{hashlib.sha1(key.encode('utf-8', errors='replace')).hexdigest()[:10]}"
                expected_yield = sum(row.estimated_yield for row in chunk)
                rationale = (
                    f"{risk_band} risk batch; size={len(chunk)}; "
                    f"avg_score={self._mean([row.expansion_score for row in chunk]):.2f}; "
                    f"avg_dup={self._mean([row.duplicate_risk for row in chunk]):.2f}"
                )
                batches.append(
                    TargetBatch(
                        batch_id=batch_id,
                        targets=[row.target for row in chunk],
                        expected_yield=expected_yield,
                        risk_band=risk_band,
                        rationale=rationale,
                    )
                )

        batches.sort(key=lambda row: (_risk_rank(row.risk_band), -row.expected_yield))
        return batches

    @staticmethod
    def _mean(values: list[float]) -> float:
        if not values:
            return 0.0
        return _clamp(sum(values) / len(values))
