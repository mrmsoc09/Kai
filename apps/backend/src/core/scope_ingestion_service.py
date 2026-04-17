from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .scope_guardrails import (
    ScopeDecision,
    ScopePolicy,
    audit_scope_decision,
    evaluate_target_scope,
)

logger = logging.getLogger(__name__)


@dataclass
class NormalizedScope:
    """Normalized scope derived from platform program data."""

    allowed: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)


@dataclass
class ScopeEntry:
    """A single scope entry with its classification."""

    raw: str
    normalized: str
    entry_type: str  # domain, subdomain, cidr, url, wildcard, other


class ProgramScopeIngestion:
    """Ingests program scope payloads and normalizes them for enforcement."""

    DOMAIN_RE = re.compile(
        r"^(?:\*\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$", re.IGNORECASE
    )
    CIDR_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}$")

    def _classify_entry(self, raw: str) -> ScopeEntry:
        """Classify and normalize a single scope entry."""
        stripped = raw.strip()
        lower = stripped.lower()

        # CIDR
        if self.CIDR_RE.match(stripped):
            return ScopeEntry(raw=raw, normalized=stripped, entry_type="cidr")

        # URL
        if "://" in lower:
            parsed = urlparse(lower)
            host = parsed.hostname or ""
            return ScopeEntry(raw=raw, normalized=host, entry_type="url")

        # Wildcard domain like *.example.com
        if lower.startswith("*."):
            return ScopeEntry(raw=raw, normalized=lower, entry_type="wildcard")

        # Plain domain / subdomain
        if self.DOMAIN_RE.match(lower):
            parts = lower.split(".")
            if len(parts) > 2:
                return ScopeEntry(raw=raw, normalized=lower, entry_type="subdomain")
            return ScopeEntry(raw=raw, normalized=lower, entry_type="domain")

        return ScopeEntry(raw=raw, normalized=lower, entry_type="other")

    def ingest_hackerone_payload(self, payload: dict[str, Any]) -> NormalizedScope:
        """Parse a HackerOne program scope payload into NormalizedScope.

        Expected payload structure (from H1 structured_scopes):
        {
            "in_scope": [{"asset_identifier": "...", "asset_type": "URL|DOMAIN|..."}],
            "out_of_scope": [{"asset_identifier": "...", "asset_type": "..."}]
        }
        """
        allowed: list[str] = []
        denied: list[str] = []

        for entry in payload.get("in_scope", []):
            identifier = str(entry.get("asset_identifier", "")).strip()
            if not identifier:
                continue
            classified = self._classify_entry(identifier)
            allowed.append(classified.normalized)

        for entry in payload.get("out_of_scope", []):
            identifier = str(entry.get("asset_identifier", "")).strip()
            if not identifier:
                continue
            classified = self._classify_entry(identifier)
            denied.append(classified.normalized)

        return NormalizedScope(allowed=allowed, denied=denied)

    def ingest_structured(self, data: dict[str, Any]) -> NormalizedScope:
        """Parse a structured dict {in_scope: [...], out_of_scope: [...]} into NormalizedScope."""
        return self.ingest_hackerone_payload(data)


class ScopeEnforcementGate:
    """Wraps scope_guardrails to check targets against a NormalizedScope."""

    def check_target(self, target: str, scope: NormalizedScope) -> bool:
        """Return True if target is in-scope, False otherwise. Logs rejections."""
        policy = ScopePolicy(
            allowlist=scope.allowed,
            denylist=scope.denied,
            strict_allowlist=True,
        )
        decision = evaluate_target_scope(target, policy)
        if not decision.allowed:
            logger.info(
                "Scope rejection: target=%s reason=%s rule=%s",
                target,
                decision.reason,
                decision.matched_rule,
            )
            audit_scope_decision(decision)
        return decision.allowed
