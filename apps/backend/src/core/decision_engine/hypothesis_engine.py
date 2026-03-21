from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .evidence_scorer import EvidenceScoreInput, EvidenceScorer


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


class HypothesisAmbiguityResolver(Protocol):
    """
    Optional LLM-assisted resolver.
    Returns confidence adjustments keyed by hypothesis_id.
    """

    def __call__(self, hypotheses: list["Hypothesis"]) -> Mapping[str, float]:
        ...


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    vuln_type: str
    confidence: float
    evidence_ids: list[str]
    reasoning_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "vuln_type": self.vuln_type,
            "confidence": round(self.confidence, 4),
            "evidence_ids": list(self.evidence_ids),
            "reasoning_summary": self.reasoning_summary,
        }


class HypothesisEngine:
    def __init__(self, scorer: EvidenceScorer | None = None) -> None:
        self._scorer = scorer or EvidenceScorer()

    def generate_hypotheses(
        self,
        *,
        findings: Sequence[Mapping[str, Any]],
        clusters: Sequence[Mapping[str, Any]],
        memory_hits: Sequence[Mapping[str, Any]],
        min_confidence: float = 0.30,
        ambiguity_resolver: HypothesisAmbiguityResolver | None = None,
    ) -> list[Hypothesis]:
        grouped = self._group_by_vuln_type(findings=findings, clusters=clusters, memory_hits=memory_hits)
        hypotheses: list[Hypothesis] = []

        for vuln_type, rows in grouped.items():
            evidence_ids = sorted({row["evidence_id"] for row in rows if row["evidence_id"]})
            if not evidence_ids:
                continue

            validation_present = any(row["validated"] for row in rows)
            repetition_strength = _clamp((len(rows) - 1) / 4.0)
            response_similarity = _mean(row["response_similarity"] for row in rows)
            memory_match_strength = _mean(row["memory_match"] for row in rows)
            confidence = self._scorer.score(
                EvidenceScoreInput(
                    validation_present=validation_present,
                    repetition_ratio=repetition_strength,
                    response_similarity=response_similarity,
                    memory_match_strength=memory_match_strength,
                )
            )
            if confidence < min_confidence:
                continue

            fingerprint = f"{vuln_type}|{'|'.join(evidence_ids)}"
            hypothesis_id = f"hyp-{hashlib.sha1(fingerprint.encode('utf-8')).hexdigest()[:12]}"
            reasoning_summary = (
                f"validated={int(validation_present)} "
                f"repeat={repetition_strength:.2f} "
                f"similarity={response_similarity:.2f} "
                f"memory={memory_match_strength:.2f}"
            )
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=hypothesis_id,
                    vuln_type=vuln_type,
                    confidence=confidence,
                    evidence_ids=evidence_ids,
                    reasoning_summary=reasoning_summary,
                )
            )

        hypotheses.sort(key=lambda row: row.confidence, reverse=True)
        if ambiguity_resolver and self._is_ambiguous(hypotheses):
            adjustments = ambiguity_resolver(hypotheses)
            hypotheses = self._apply_adjustments(hypotheses, adjustments)
        return hypotheses

    def _group_by_vuln_type(
        self,
        *,
        findings: Sequence[Mapping[str, Any]],
        clusters: Sequence[Mapping[str, Any]],
        memory_hits: Sequence[Mapping[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}

        for finding in findings:
            vuln_type = _normalize_vuln_type(finding.get("vuln_type"))
            if not vuln_type:
                continue
            grouped.setdefault(vuln_type, []).append(
                {
                    "evidence_id": str(finding.get("finding_id") or finding.get("id") or ""),
                    "validated": bool(
                        finding.get("validated_vulnerability")
                        or finding.get("validated")
                        or finding.get("validation_present")
                    ),
                    "response_similarity": _clamp(float(finding.get("response_similarity", 0.0))),
                    "memory_match": _clamp(float(finding.get("memory_match_strength", 0.0))),
                }
            )

        for cluster in clusters:
            vuln_type = _normalize_vuln_type(cluster.get("vuln_type"))
            if not vuln_type:
                continue
            cluster_count = max(1, int(cluster.get("count", 1)))
            grouped.setdefault(vuln_type, []).append(
                {
                    "evidence_id": str(cluster.get("cluster_id") or cluster.get("id") or ""),
                    "validated": bool(cluster.get("validated")),
                    "response_similarity": _clamp(float(cluster.get("response_similarity", 0.5))),
                    "memory_match": _clamp(min(1.0, 0.15 * cluster_count)),
                }
            )

        for memory_hit in memory_hits:
            vuln_type = _normalize_vuln_type(
                memory_hit.get("vuln_type")
                or memory_hit.get("type")
                or memory_hit.get("memory_type")
            )
            if not vuln_type:
                continue
            grouped.setdefault(vuln_type, []).append(
                {
                    "evidence_id": str(memory_hit.get("memory_id") or memory_hit.get("id") or ""),
                    "validated": bool(memory_hit.get("confirmed") or memory_hit.get("validated")),
                    "response_similarity": _clamp(float(memory_hit.get("response_similarity", 0.5))),
                    "memory_match": _clamp(float(memory_hit.get("match_strength", memory_hit.get("score", 0.0)))),
                }
            )

        return grouped

    def _is_ambiguous(self, hypotheses: Sequence[Hypothesis]) -> bool:
        if len(hypotheses) < 2:
            return False
        return abs(hypotheses[0].confidence - hypotheses[1].confidence) <= 0.05

    def _apply_adjustments(
        self,
        hypotheses: Sequence[Hypothesis],
        adjustments: Mapping[str, float],
    ) -> list[Hypothesis]:
        adjusted: list[Hypothesis] = []
        for hypothesis in hypotheses:
            delta = float(adjustments.get(hypothesis.hypothesis_id, 0.0))
            adjusted.append(
                Hypothesis(
                    hypothesis_id=hypothesis.hypothesis_id,
                    vuln_type=hypothesis.vuln_type,
                    confidence=round(_clamp(hypothesis.confidence + delta), 4),
                    evidence_ids=hypothesis.evidence_ids,
                    reasoning_summary=hypothesis.reasoning_summary,
                )
            )
        adjusted.sort(key=lambda row: row.confidence, reverse=True)
        return adjusted


def _normalize_vuln_type(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "_")


def _mean(values: Sequence[float]) -> float:
    rows = [float(value) for value in values]
    if not rows:
        return 0.0
    return _clamp(sum(rows) / len(rows))
