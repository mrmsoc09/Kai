from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from .intelligence_memory import MemoryManager, MemoryType, ValidationStatus, get_memory_manager
from .intelligence_query import IntelligenceQueryEngine, get_query_engine
from .report_engine import ReportEngine, get_report_engine


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_target(value: Any) -> str:
    raw = _normalize_text(value).lower()
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.hostname or parsed.path or raw
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw.strip(".")


def _extract_endpoint_shape(value: str) -> str:
    row = value.strip().lower()
    if not row:
        return ""
    if "://" in row:
        parsed = urlparse(row)
        row = parsed.path or "/"
    row = row.split("?", 1)[0]
    parts = [segment for segment in row.strip("/").split("/") if segment]
    shaped: list[str] = []
    for segment in parts:
        if segment.isdigit():
            shaped.append("{id}")
        elif len(segment) >= 24 and all(ch in "0123456789abcdef" for ch in segment.lower()):
            shaped.append("{hex}")
        else:
            shaped.append(segment)
    return "/" + "/".join(shaped) if shaped else "/"


def _extract_entry_tags(entry_tags: list[str], prefix: str) -> set[str]:
    rows: set[str] = set()
    for tag in entry_tags:
        value = _normalize_text(tag)
        if value.startswith(prefix):
            rows.add(value[len(prefix):].strip().lower())
    return rows


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


@dataclass(frozen=True)
class SimilaritySource:
    source_type: str
    source_object_id: str
    vuln_type: str
    source_target: str = ""
    confidence: float = 0.5
    tech_stack: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    endpoint_shapes: list[str] = field(default_factory=list)
    pattern_tags: list[str] = field(default_factory=list)
    service_fingerprints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _NormalizedSource:
    source: SimilaritySource
    tech_stack_set: set[str]
    headers_set: set[str]
    endpoint_set: set[str]
    pattern_set: set[str]
    service_set: set[str]


@dataclass(frozen=True)
class SimilarTarget:
    target: str
    similarity_score: float
    matching_factors: list[str]
    confidence: float
    factor_scores: dict[str, float]
    memory_match_strength: float
    expected_report_quality: float
    target_importance: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "similarity_score": round(self.similarity_score, 4),
            "matching_factors": list(self.matching_factors),
            "confidence": round(self.confidence, 4),
            "factor_scores": {key: round(float(value), 4) for key, value in self.factor_scores.items()},
            "memory_match_strength": round(self.memory_match_strength, 4),
            "expected_report_quality": round(self.expected_report_quality, 4),
            "target_importance": round(self.target_importance, 4),
            "rationale": self.rationale,
        }


class TargetSimilarityEngine:
    """
    Scores candidate targets against a validated source signal using deterministic factors.
    """

    _W_TECH = 0.24
    _W_HEADERS = 0.12
    _W_ENDPOINT = 0.20
    _W_PATTERNS = 0.18
    _W_SERVICE = 0.14
    _W_MEMORY = 0.12

    def __init__(
        self,
        manager: MemoryManager | None = None,
        query_engine: IntelligenceQueryEngine | None = None,
        report_engine: ReportEngine | None = None,
    ) -> None:
        self._manager = manager or get_memory_manager()
        self._query = query_engine or get_query_engine()
        self._reports = report_engine or get_report_engine()

    def rank_targets(
        self,
        source: SimilaritySource,
        candidate_targets: list[str],
        *,
        min_similarity: float = 0.25,
        limit: int = 50,
    ) -> list[SimilarTarget]:
        normalized_source = self._normalize_source(source)
        rows: list[SimilarTarget] = []
        seen: set[str] = set()
        for candidate in candidate_targets:
            target = _normalize_target(candidate)
            if not target or target in seen:
                continue
            seen.add(target)
            score = self.score_target(normalized_source, target)
            if score.similarity_score < min_similarity:
                continue
            rows.append(score)

        rows.sort(
            key=lambda row: (row.similarity_score, row.memory_match_strength, row.target_importance),
            reverse=True,
        )
        return rows[:limit]

    def score_target(self, source: _NormalizedSource, target: str) -> SimilarTarget:
        target_entries = self._manager.query(domain=target, limit=300)
        target_tech = self._collect_tech(target_entries)
        target_headers = self._collect_headers(target_entries)
        target_endpoints = self._collect_endpoints(target_entries)
        target_patterns = self._collect_patterns(target_entries)
        target_services = self._collect_services(target_entries)

        tech_score = _jaccard(source.tech_stack_set, target_tech)
        header_score = _jaccard(source.headers_set, target_headers)
        endpoint_score = _jaccard(source.endpoint_set, target_endpoints)
        pattern_score = _jaccard(source.pattern_set, target_patterns)
        service_score = _jaccard(source.service_set, target_services)
        memory_match = self._memory_match_strength(source.source.vuln_type, target)

        composite = (
            self._W_TECH * tech_score
            + self._W_HEADERS * header_score
            + self._W_ENDPOINT * endpoint_score
            + self._W_PATTERNS * pattern_score
            + self._W_SERVICE * service_score
            + self._W_MEMORY * memory_match
        )
        report_quality = self._expected_report_quality(target)
        target_importance = self._target_importance(target_entries, report_quality)
        confidence = _clamp((0.65 * composite) + (0.20 * source.source.confidence) + (0.15 * memory_match))

        matching_factors: list[str] = []
        if tech_score >= 0.35:
            matching_factors.append("tech_stack_overlap")
        if header_score >= 0.35:
            matching_factors.append("header_similarity")
        if endpoint_score >= 0.35:
            matching_factors.append("endpoint_shape_overlap")
        if pattern_score >= 0.35:
            matching_factors.append("pattern_alignment")
        if service_score >= 0.35:
            matching_factors.append("service_fingerprint_overlap")
        if memory_match >= 0.35:
            matching_factors.append("prior_memory_match")
        if not matching_factors:
            matching_factors.append("weak_match")

        rationale = (
            f"tech={tech_score:.2f} headers={header_score:.2f} endpoint={endpoint_score:.2f} "
            f"pattern={pattern_score:.2f} service={service_score:.2f} memory={memory_match:.2f}"
        )
        return SimilarTarget(
            target=target,
            similarity_score=round(_clamp(composite), 4),
            matching_factors=matching_factors,
            confidence=round(confidence, 4),
            factor_scores={
                "tech_stack": tech_score,
                "headers": header_score,
                "endpoint_shape": endpoint_score,
                "patterns": pattern_score,
                "services": service_score,
                "memory": memory_match,
            },
            memory_match_strength=round(memory_match, 4),
            expected_report_quality=round(report_quality, 4),
            target_importance=round(target_importance, 4),
            rationale=rationale,
        )

    def _normalize_source(self, source: SimilaritySource) -> _NormalizedSource:
        tech_stack = sorted({_normalize_text(value).lower() for value in source.tech_stack if _normalize_text(value)})
        headers = sorted({_normalize_text(value).lower() for value in source.headers if _normalize_text(value)})
        endpoints = sorted({_extract_endpoint_shape(_normalize_text(value)) for value in source.endpoint_shapes if _normalize_text(value)})
        patterns = sorted(
            {
                _normalize_text(value).lower()
                for value in [source.vuln_type, *source.pattern_tags]
                if _normalize_text(value)
            }
        )
        services = sorted({_normalize_text(value).lower() for value in source.service_fingerprints if _normalize_text(value)})
        source_target = _normalize_target(source.source_target)
        normalized = SimilaritySource(
            source_type=_normalize_text(source.source_type) or "finding",
            source_object_id=_normalize_text(source.source_object_id) or "unknown",
            vuln_type=_normalize_text(source.vuln_type).lower() or "unknown",
            source_target=source_target,
            confidence=_clamp(source.confidence),
            tech_stack=tech_stack,
            headers=headers,
            endpoint_shapes=endpoints,
            pattern_tags=patterns,
            service_fingerprints=services,
        )
        return _NormalizedSource(
            source=normalized,
            tech_stack_set=set(tech_stack),
            headers_set=set(headers),
            endpoint_set=set(endpoints),
            pattern_set=set(patterns),
            service_set=set(services),
        )

    def _collect_tech(self, entries: list[Any]) -> set[str]:
        rows: set[str] = set()
        for entry in entries:
            for tech in entry.target_fingerprint.tech_stack:
                value = _normalize_text(tech).lower()
                if value:
                    rows.add(value)
        return rows

    def _collect_headers(self, entries: list[Any]) -> set[str]:
        rows: set[str] = set()
        for entry in entries:
            rows.update(_extract_entry_tags(entry.tags, "header:"))
            rows.update(_extract_entry_tags(entry.tags, "http_header:"))
        return rows

    def _collect_endpoints(self, entries: list[Any]) -> set[str]:
        rows: set[str] = set()
        for entry in entries:
            for endpoint in _extract_entry_tags(entry.tags, "endpoint:"):
                shape = _extract_endpoint_shape(endpoint)
                if shape:
                    rows.add(shape)
            try:
                payload = entry.decrypt()
            except Exception:
                payload = None
            if isinstance(payload, dict):
                endpoint = _normalize_text(payload.get("endpoint") or payload.get("url") or payload.get("path"))
                if endpoint:
                    rows.add(_extract_endpoint_shape(endpoint))
        return rows

    def _collect_patterns(self, entries: list[Any]) -> set[str]:
        rows: set[str] = set()
        for entry in entries:
            rows.update({value.lower() for value in _extract_entry_tags(entry.tags, "vuln_type:")})
            for tag in entry.tags:
                value = _normalize_text(tag).lower()
                if value and value not in {"compressed_pattern", "validated", "confirmed"}:
                    rows.add(value)
        return rows

    def _collect_services(self, entries: list[Any]) -> set[str]:
        rows: set[str] = set()
        for entry in entries:
            for service in entry.target_fingerprint.services:
                value = _normalize_text(service).lower()
                if value:
                    rows.add(value)
        return rows

    def _memory_match_strength(self, vuln_type: str, target: str) -> float:
        prior_vulns, _ = self._query.find_prior_vuln(vuln_type=vuln_type, domain=target, min_confidence=0.3, limit=30)
        if not prior_vulns:
            return 0.0
        confidence_avg = sum(_clamp(row.confidence) for row in prior_vulns) / len(prior_vulns)
        confirmed_count = sum(1 for row in prior_vulns if row.validation_status == ValidationStatus.CONFIRMED.value)
        confirmation_bonus = min(1.0, confirmed_count / 4.0)
        return _clamp((0.75 * confidence_avg) + (0.25 * confirmation_bonus))

    def _expected_report_quality(self, target: str) -> float:
        reports = self._reports.list_reports(target=target)
        if not reports:
            return 0.55
        values = [_clamp(getattr(row, "quality_score", 0.55)) for row in reports]
        return _clamp(sum(values) / len(values))

    def _target_importance(self, entries: list[Any], report_quality: float) -> float:
        if not entries:
            return _clamp(0.35 + (0.25 * report_quality))
        validated = sum(1 for row in entries if row.validation_status == ValidationStatus.CONFIRMED)
        strategic = sum(1 for row in entries if row.memory_type == MemoryType.PATTERN_SIGNATURE)
        confidence = sum(_clamp(row.confidence_score) for row in entries) / len(entries)
        validated_weight = min(1.0, validated / max(1, len(entries)))
        strategic_bonus = min(1.0, strategic / 3.0)
        return _clamp((0.40 * confidence) + (0.30 * validated_weight) + (0.15 * strategic_bonus) + (0.15 * report_quality))
