"""
False Positive Suppression Filter
====================================
Rule-based filter applied before findings are escalated to HIL.

Rules:
  - Duplicate/identical responses (same body, different parameter values)
  - Known noise patterns (WAF error pages, CDN boilerplate, version banners)
  - Non-exploitable reflections (parameter echoed in benign context, HTML-encoded)
  - Informational-only findings masquerading as vulnerabilities
  - Common scanner artifacts (default pages, test endpoints)

All rules are deterministic — no LLM calls.

Usage::

    filters = FalsePositiveFilters()
    decision = filters.evaluate(finding)
    if decision.is_false_positive:
        log.info("Suppressed: %s", decision.reason)
    else:
        escalate(finding)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FindingSignal:
    """Minimal representation of a raw finding for FP evaluation."""

    finding_id: str
    title: str
    url: str
    vuln_type: str
    severity: str  # critical, high, medium, low, informational
    response_body: str = ""
    response_status: int = 200
    parameter: str | None = None
    payload: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FPDecision:
    """Result of false positive evaluation."""

    finding_id: str
    is_false_positive: bool
    reason: str  # human-readable explanation
    rule_triggered: str | None = None  # which rule fired
    confidence: float = 1.0  # FP confidence (1.0 = certain FP)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "is_false_positive": self.is_false_positive,
            "reason": self.reason,
            "rule_triggered": self.rule_triggered,
            "confidence": round(self.confidence, 4),
        }


# ---------------------------------------------------------------------------
# Known noise patterns
# ---------------------------------------------------------------------------

# WAF / CDN boilerplate body patterns — these indicate the real target was not reached
_WAF_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"access denied.*cloudflare",
        r"cf-ray:",
        r"ray id:",
        r"sorry, you have been blocked",
        r"this site is protected by",
        r"attention required.*cloudflare",
        r"incapsula incident id",
        r"mod_security",
        r"akamai ghost",
        r"sucuri websit(e)? firewall",
        r"request was rejected",
    ]
]

# Generic default/test page patterns (not real app responses)
_DEFAULT_PAGE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"apache2 ubuntu default page",
        r"welcome to nginx",
        r"it works!.*apache",
        r"iis windows server",
        r"default web site page",
        r"test page for the apache",
        r"this is the default welcome page",
    ]
]

# Benign reflection contexts — reflected but HTML-encoded or in safe attributes
_SAFE_REFLECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"&lt;script",
        r"&gt;",
        r"&amp;",
        r"&#x3c;",
        r"&#60;",
        r"value=\"[^\"]*k1probe",  # reflected into input value attribute (still potentially XSS but weaker)
    ]
]

# Titles that are obviously informational / scanner noise
_INFORMATIONAL_TITLE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^(x-powered-by|server header|x-aspnet-version)",
        r"^(ssl certificate|tls version|cipher suite)",
        r"^(cookie without httponly|cookie without secure flag)",
        r"^(missing (x-frame-options|content-security-policy|hsts))",
        r"^(directory listing enabled)",
        r"^(http methods allowed)",
        r"^robots\.txt (found|disclosure)",
        r"^(source code disclosure.*\.map)",
    ]
]

# Body patterns that indicate benign application errors (not injection-induced)
_BENIGN_ERROR_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"404 not found",
        r"page not found",
        r"the requested url was not found",
        r"sorry, the page you are looking for",
        r"400 bad request",
        r"invalid input",  # generic validation error
        r"please enter a valid",
    ]
]


# ---------------------------------------------------------------------------
# Filter engine
# ---------------------------------------------------------------------------


class FalsePositiveFilters:
    """
    Applies a chain of FP suppression rules to a raw finding.

    Rules are evaluated in order; first match wins (short-circuit).
    """

    def evaluate(self, finding: FindingSignal) -> FPDecision:
        """Evaluate a single finding. Returns FPDecision with is_false_positive flag."""
        for rule in self._rules():
            decision = rule(finding)
            if decision is not None:
                return decision

        # No FP rule triggered — treat as genuine signal
        return FPDecision(
            finding_id=finding.finding_id,
            is_false_positive=False,
            reason="passed_all_fp_rules",
        )

    def evaluate_batch(self, findings: list[FindingSignal]) -> list[FPDecision]:
        """Evaluate a batch of findings. Also deduplicates by response body hash."""
        seen_bodies: dict[str, str] = {}  # body_hash → first finding_id
        decisions: list[FPDecision] = []

        for finding in findings:
            # Duplicate body check (before other rules)
            body_hash = _hash_body(finding.response_body)
            if body_hash and body_hash in seen_bodies:
                decisions.append(
                    FPDecision(
                        finding_id=finding.finding_id,
                        is_false_positive=True,
                        reason=f"duplicate_response_body (matches finding {seen_bodies[body_hash]})",
                        rule_triggered="duplicate_response",
                        confidence=0.95,
                    )
                )
                continue

            decision = self.evaluate(finding)
            if not decision.is_false_positive and body_hash:
                seen_bodies[body_hash] = finding.finding_id
            decisions.append(decision)

        return decisions

    # -- Rule definitions -------------------------------------------------------

    def _rules(self):
        return [
            self._rule_waf_block,
            self._rule_default_page,
            self._rule_informational_title,
            self._rule_benign_error_body,
            self._rule_safe_html_encoding,
            self._rule_informational_severity,
            self._rule_empty_response,
        ]

    def _rule_waf_block(self, f: FindingSignal) -> FPDecision | None:
        """Finding triggered a WAF/CDN block — didn't reach the real target."""
        for pat in _WAF_PATTERNS:
            if pat.search(f.response_body):
                return FPDecision(
                    finding_id=f.finding_id,
                    is_false_positive=True,
                    reason="WAF/CDN block page detected — finding did not reach real target",
                    rule_triggered="waf_block",
                    confidence=0.95,
                )
        return None

    def _rule_default_page(self, f: FindingSignal) -> FPDecision | None:
        """Finding hit a default web server page, not the application."""
        for pat in _DEFAULT_PAGE_PATTERNS:
            if pat.search(f.response_body):
                return FPDecision(
                    finding_id=f.finding_id,
                    is_false_positive=True,
                    reason="Default web server page detected — application not reached",
                    rule_triggered="default_page",
                    confidence=0.90,
                )
        return None

    def _rule_informational_title(self, f: FindingSignal) -> FPDecision | None:
        """Finding title matches a known informational scanner artifact."""
        for pat in _INFORMATIONAL_TITLE_PATTERNS:
            if pat.search(f.title):
                return FPDecision(
                    finding_id=f.finding_id,
                    is_false_positive=True,
                    reason=f"Title matches known informational pattern: '{f.title}'",
                    rule_triggered="informational_title",
                    confidence=0.85,
                )
        return None

    def _rule_benign_error_body(self, f: FindingSignal) -> FPDecision | None:
        """Response body contains only a benign application validation error, not injection."""
        body_lower = f.response_body.lower()[:2000]  # check first 2 KB only
        for pat in _BENIGN_ERROR_PATTERNS:
            if pat.search(body_lower):
                # Only suppress if there are NO injection-specific patterns
                if not _has_injection_signal(f.response_body):
                    return FPDecision(
                        finding_id=f.finding_id,
                        is_false_positive=True,
                        reason="Response is a generic input validation error without injection signal",
                        rule_triggered="benign_error_body",
                        confidence=0.75,
                    )
        return None

    def _rule_safe_html_encoding(self, f: FindingSignal) -> FPDecision | None:
        """Reflected content is HTML-encoded — not executable, not a real XSS."""
        if f.vuln_type.lower() not in ("xss", "reflected_xss"):
            return None
        for pat in _SAFE_REFLECTION_PATTERNS:
            if pat.search(f.response_body):
                # If content is encoded, it's not exploitable XSS
                if not _has_unencoded_xss(f.response_body):
                    return FPDecision(
                        finding_id=f.finding_id,
                        is_false_positive=True,
                        reason="Reflected payload is HTML-encoded — not exploitable as XSS",
                        rule_triggered="safe_html_encoding",
                        confidence=0.80,
                    )
        return None

    def _rule_informational_severity(self, f: FindingSignal) -> FPDecision | None:
        """Informational findings are not vulnerabilities — suppress automatically."""
        if f.severity.lower() == "informational":
            return FPDecision(
                finding_id=f.finding_id,
                is_false_positive=True,
                reason="Severity is 'informational' — not a vulnerability",
                rule_triggered="informational_severity",
                confidence=1.0,
            )
        return None

    def _rule_empty_response(self, f: FindingSignal) -> FPDecision | None:
        """Empty response body with 200 status is likely a timeout/error — suppress."""
        if len(f.response_body.strip()) < 10 and f.response_status == 200:
            return FPDecision(
                finding_id=f.finding_id,
                is_false_positive=True,
                reason="Empty response body — likely a probe timeout or redirect loop",
                rule_triggered="empty_response",
                confidence=0.70,
            )
        return None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

# Injection signal patterns — if present, don't suppress even if benign body matched
_INJECTION_SIGNAL_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"you have an error in your sql syntax",
        r"ORA-\d{5}",
        r"<script[^>]*>alert\(",
        r"root:x:\d+:\d+:",
    ]
]

_UNENCODED_XSS_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"<script[^>]*>",
        r"javascript:[^\s\"']+",
        r"on(load|error|click)=[\"'][^\"']*[\"']",
    ]
]


def _has_injection_signal(body: str) -> bool:
    return any(p.search(body) for p in _INJECTION_SIGNAL_PATTERNS)


def _has_unencoded_xss(body: str) -> bool:
    return any(p.search(body) for p in _UNENCODED_XSS_PATTERNS)


def _hash_body(body: str) -> str:
    """Short hash of normalized body for deduplication."""
    import hashlib

    normalized = re.sub(r"\s+", " ", body.strip().lower())
    return hashlib.md5(normalized.encode("utf-8", errors="replace")).hexdigest()
