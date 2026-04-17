from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _normalize_endpoint(endpoint: str) -> str:
    """Normalize an endpoint: lowercase, strip trailing slash, keep first query param only."""
    raw = (endpoint or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        path = parsed.path or "/"
    else:
        path = raw.split("?")[0] if "?" in raw else raw

    # Strip query params beyond the first
    if "?" in raw:
        base, query = raw.split("?", 1)
        first_param = query.split("&")[0] if "&" in query else query
        path = (urlparse(base).path if "://" in base else base.split("?")[0])
        path = f"{path}?{first_param}"

    return path.rstrip("/") or "/"


def _compute_fingerprint(endpoint: str, vuln_type: str, parameter: str = "") -> str:
    """SHA-256 fingerprint of normalized (endpoint + vuln_type + parameter)."""
    norm_endpoint = _normalize_endpoint(endpoint)
    norm_vuln = (vuln_type or "").strip().lower()
    norm_param = (parameter or "").strip().lower()
    payload = f"{norm_endpoint}|{norm_vuln}|{norm_param}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    duplicate_of: str | None = None
    similarity_score: float = 0.0
    match_reason: str = ""


class DeduplicationService:
    """Fingerprint-based duplicate detection for findings within a campaign.

    Uses an in-memory store for MVP. Production should use DedupFingerprint DB table.
    """

    def __init__(self) -> None:
        # In-memory store: campaign_id -> {fingerprint -> finding_id}
        self._store: dict[str, dict[str, str]] = {}
        # Also track endpoint paths for near-duplicate detection
        self._endpoints: dict[str, dict[str, str]] = {}  # campaign_id -> {path -> finding_id}

    def _fingerprint(self, finding: dict[str, Any]) -> str:
        endpoint = finding.get("endpoint", finding.get("asset", finding.get("target", "")))
        vuln_type = finding.get("vuln_type", finding.get("vulnerability_type", ""))
        parameter = finding.get("parameter", "")
        return _compute_fingerprint(endpoint, vuln_type, parameter)

    def _extract_path(self, finding: dict[str, Any]) -> str:
        endpoint = finding.get("endpoint", finding.get("asset", finding.get("target", "")))
        return _normalize_endpoint(endpoint)

    async def check_duplicate(
        self,
        finding: dict[str, Any],
        campaign_id: str,
        db: Any = None,
    ) -> DuplicateCheckResult:
        """Check if finding is a duplicate within the campaign.

        1. Exact fingerprint match -> duplicate (score=1.0)
        2. Same path, different parameter -> near duplicate (score=0.7)
        """
        fp = self._fingerprint(finding)
        campaign_fps = self._store.get(campaign_id, {})

        # Exact match
        if fp in campaign_fps:
            return DuplicateCheckResult(
                is_duplicate=True,
                duplicate_of=campaign_fps[fp],
                similarity_score=1.0,
                match_reason="exact_fingerprint_match",
            )

        # Near duplicate: same endpoint path, different parameter
        path = self._extract_path(finding)
        campaign_endpoints = self._endpoints.get(campaign_id, {})
        if path and path in campaign_endpoints:
            return DuplicateCheckResult(
                is_duplicate=True,
                duplicate_of=campaign_endpoints[path],
                similarity_score=0.7,
                match_reason="near_duplicate_same_path",
            )

        return DuplicateCheckResult(
            is_duplicate=False,
            similarity_score=0.0,
            match_reason="no_match",
        )

    async def register_finding(
        self,
        finding: dict[str, Any],
        campaign_id: str,
        db: Any = None,
    ) -> str:
        """Store fingerprint and return a finding_id."""
        fp = self._fingerprint(finding)
        finding_id = finding.get("id", str(uuid.uuid4()))
        path = self._extract_path(finding)

        if campaign_id not in self._store:
            self._store[campaign_id] = {}
        self._store[campaign_id][fp] = finding_id

        if campaign_id not in self._endpoints:
            self._endpoints[campaign_id] = {}
        if path:
            self._endpoints[campaign_id][path] = finding_id

        return finding_id
