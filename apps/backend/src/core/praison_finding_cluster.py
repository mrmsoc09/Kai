"""
Finding Deduplication & Clustering
=====================================
Groups raw findings by endpoint, parameter, and vulnerability type.
Collapses duplicates into representative cluster records with a
combined confidence score.

Features:
  - Endpoint normalization (strips UUIDs, numeric IDs from paths)
  - Fuzzy title matching (difflib SequenceMatcher)
  - Vuln-type-aware clustering (XSS findings never merged with SQLi)
  - Cluster confidence = max(individual confidences) + bonus for corroboration
  - Thread-safe — uses a simple lock around cluster state

Integrates with:
  - StrategyLearner (via cluster summary → learning feedback)
  - ReportSynthesisAgent (cluster → deduplicated finding list)
"""

from __future__ import annotations

import difflib
import hashlib
import re
import threading
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RawFinding:
    """Input finding for clustering."""

    finding_id: str
    title: str
    url: str
    parameter: str | None
    vuln_type: str  # xss, sqli, ssrf, path_traversal, etc.
    severity: str  # critical, high, medium, low
    confidence: float  # 0.0–1.0
    payload: str | None = None
    response_snippet: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FindingCluster:
    """A cluster of related findings collapsed into one representative record."""

    cluster_id: str
    representative_title: str
    endpoint_pattern: str  # normalized URL pattern
    parameter: str | None
    vuln_type: str
    severity: str  # highest severity in cluster
    cluster_confidence: float  # 0.0–1.0
    finding_ids: list[str] = field(default_factory=list)
    count: int = 0  # number of findings in cluster
    payloads: list[str] = field(default_factory=list)  # unique payloads seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "representative_title": self.representative_title,
            "endpoint_pattern": self.endpoint_pattern,
            "parameter": self.parameter,
            "vuln_type": self.vuln_type,
            "severity": self.severity,
            "cluster_confidence": round(self.cluster_confidence, 4),
            "finding_ids": self.finding_ids,
            "count": self.count,
            "payloads": self.payloads[:10],  # cap at 10
        }


@dataclass
class ClusterSummary:
    """Output of a full clustering run."""

    total_raw: int
    total_clusters: int
    duplicate_rate: float  # fraction of raw findings that were collapsed
    clusters: list[FindingCluster] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_raw": self.total_raw,
            "total_clusters": self.total_clusters,
            "duplicate_rate": round(self.duplicate_rate, 4),
            "clusters": [c.to_dict() for c in self.clusters],
        }


# ---------------------------------------------------------------------------
# Severity rank for "highest in cluster" logic
# ---------------------------------------------------------------------------

_SEVERITY_RANK: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "informational": 0,
}


def _higher_severity(a: str, b: str) -> str:
    return a if _SEVERITY_RANK.get(a.lower(), 0) >= _SEVERITY_RANK.get(b.lower(), 0) else b


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

# Patterns that identify variable path segments
_ID_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE),  # UUID
    re.compile(r"/\d{4,}/"),  # long numeric segment
    re.compile(r"/\d+$"),  # trailing numeric ID
    re.compile(r"/\d+/"),  # mid-path numeric ID
]


def normalize_endpoint(url: str) -> str:
    """
    Strip query string, normalize dynamic path segments to placeholders.

    /api/users/12345/profile  → /api/users/{id}/profile
    /api/items/abc-uuid-here  → /api/items/{id}
    """
    # Strip query string and fragment
    url = url.split("?")[0].split("#")[0]
    # Strip scheme and host to get path only
    m = re.match(r"https?://[^/]+(.*)", url)
    path = m.group(1) if m else url

    for pat in _ID_PATTERNS:
        path = pat.sub(lambda _m: _m.group(0).replace(_m.group(0), "{id}"), path)

    # Collapse repeated slashes
    path = re.sub(r"//+", "/", path)
    return path.rstrip("/") or "/"


# ---------------------------------------------------------------------------
# Clustering engine
# ---------------------------------------------------------------------------

_TITLE_SIMILARITY_THRESHOLD = 0.75  # SequenceMatcher ratio above which titles are "same"
_CORROBORATION_BONUS = 0.05  # per additional finding in cluster (capped)


class FindingClusterer:
    """
    Clusters raw findings by (endpoint_pattern, parameter, vuln_type).

    Two findings are in the same cluster when ALL three keys match.
    Additionally, titles with high SequenceMatcher similarity and the same
    key triple are merged even if titles differ slightly.

    Thread-safe — a lock protects internal cluster state.
    """

    def __init__(self) -> None:
        self._clusters: dict[str, FindingCluster] = {}
        self._lock = threading.Lock()

    def cluster(self, findings: list[RawFinding]) -> ClusterSummary:
        """Cluster a list of findings. Returns a ClusterSummary."""
        with self._lock:
            self._clusters = {}
            for finding in findings:
                self._assign(finding)

            clusters = sorted(
                self._clusters.values(),
                key=lambda c: c.cluster_confidence,
                reverse=True,
            )
            duplicate_rate = (
                (len(findings) - len(clusters)) / len(findings) if findings else 0.0
            )
            return ClusterSummary(
                total_raw=len(findings),
                total_clusters=len(clusters),
                duplicate_rate=duplicate_rate,
                clusters=clusters,
            )

    def _assign(self, finding: RawFinding) -> None:
        """Assign a finding to an existing cluster or create a new one."""
        ep = normalize_endpoint(finding.url)
        key = _cluster_key(ep, finding.parameter, finding.vuln_type)

        if key in self._clusters:
            cluster = self._clusters[key]
            # Check title similarity — if very different, create a sub-cluster
            if _title_similar(cluster.representative_title, finding.title):
                _merge_into(cluster, finding)
                return
            # Different title but same key — use a sub-key with title hash
            sub_key = key + ":" + _short_hash(finding.title)
            if sub_key in self._clusters:
                _merge_into(self._clusters[sub_key], finding)
            else:
                self._clusters[sub_key] = _new_cluster(ep, finding)
        else:
            self._clusters[key] = _new_cluster(ep, finding)

    def reset(self) -> None:
        """Clear cluster state (for reuse across mission phases)."""
        with self._lock:
            self._clusters = {}

    def get_clusters(self) -> list[FindingCluster]:
        with self._lock:
            return list(self._clusters.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cluster_key(endpoint: str, parameter: str | None, vuln_type: str) -> str:
    param_part = (parameter or "").lower().strip()
    type_part = vuln_type.lower().strip()
    raw = f"{endpoint}|{param_part}|{type_part}"
    return hashlib.md5(raw.encode()).hexdigest()


def _new_cluster(endpoint: str, finding: RawFinding) -> FindingCluster:
    cluster_id = "cluster-" + _short_hash(finding.finding_id + finding.vuln_type)
    payloads = [finding.payload] if finding.payload else []
    return FindingCluster(
        cluster_id=cluster_id,
        representative_title=finding.title,
        endpoint_pattern=endpoint,
        parameter=finding.parameter,
        vuln_type=finding.vuln_type,
        severity=finding.severity,
        cluster_confidence=finding.confidence,
        finding_ids=[finding.finding_id],
        count=1,
        payloads=payloads,
    )


def _merge_into(cluster: FindingCluster, finding: RawFinding) -> None:
    """Merge a finding into an existing cluster, updating metadata."""
    cluster.finding_ids.append(finding.finding_id)
    cluster.count += 1

    # Highest severity wins
    cluster.severity = _higher_severity(cluster.severity, finding.severity)  # type: ignore[assignment]

    # Confidence: max + small corroboration bonus (capped at 0.95)
    bonus = min(0.15, _CORROBORATION_BONUS * (cluster.count - 1))
    cluster.cluster_confidence = min(0.95, max(cluster.cluster_confidence, finding.confidence) + bonus)

    # Accumulate unique payloads
    if finding.payload and finding.payload not in cluster.payloads:
        cluster.payloads.append(finding.payload)


def _title_similar(a: str, b: str) -> bool:
    ratio = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return ratio >= _TITLE_SIMILARITY_THRESHOLD


def _short_hash(s: str) -> str:
    return hashlib.md5(s.encode("utf-8", errors="replace")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Convenience function for strategy learner integration
# ---------------------------------------------------------------------------


def summarize_for_learner(summary: ClusterSummary) -> dict[str, Any]:
    """
    Convert a ClusterSummary into the format expected by StrategyLearner.

    Returns a dict with validated_vulnerabilities, false_positive_rate,
    and cluster_breakdown for strategy scoring.
    """
    high_conf_clusters = [c for c in summary.clusters if c.cluster_confidence >= 0.6]
    low_conf_clusters = [c for c in summary.clusters if c.cluster_confidence < 0.4]

    return {
        "total_raw_findings": summary.total_raw,
        "unique_clusters": summary.total_clusters,
        "duplicate_rate": summary.duplicate_rate,
        "high_confidence_clusters": len(high_conf_clusters),
        "low_confidence_clusters": len(low_conf_clusters),
        "estimated_false_positives": len(low_conf_clusters),
        "cluster_breakdown": [
            {
                "vuln_type": c.vuln_type,
                "severity": c.severity,
                "count": c.count,
                "confidence": c.cluster_confidence,
            }
            for c in summary.clusters[:20]  # top 20 clusters
        ],
    }
