"""Heuristic false-positive detector for analyst review prioritization."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FalsePositiveReason(str, Enum):
    """Reasons a finding may be a false positive."""

    NOT_REPRODUCIBLE = "not_reproducible"
    EXPECTED_BEHAVIOR = "expected_behavior"
    INPUT_VALIDATION = "input_validation"
    MITIGATING_CONTROL = "mitigating_control"
    THIRD_PARTY_CODE = "third_party_code"
    WAF_BLOCKED = "waf_blocked"
    SCOPE_EXCEPTION = "scope_exception"
    NEEDS_SPECIAL_ACCESS = "needs_special_access"


class FalsePositiveDetector:
    """Analyze findings for false-positive indicators.

    This service does not auto-exclude findings. It only produces a confidence
    score and likely reason to accelerate human review.
    """

    async def analyze_finding_for_false_positive(
        self, finding_id: str, finding: dict[str, Any]
    ) -> tuple[float, Optional[str]]:
        confidence_score = 0.0
        reasons: list[FalsePositiveReason] = []

        if not self._check_reproducibility(finding):
            confidence_score += 0.30
            reasons.append(FalsePositiveReason.NOT_REPRODUCIBLE)

        if self._check_expected_behavior(finding):
            confidence_score += 0.25
            reasons.append(FalsePositiveReason.EXPECTED_BEHAVIOR)

        if self._check_input_validation(finding):
            confidence_score += 0.20
            reasons.append(FalsePositiveReason.INPUT_VALIDATION)

        if self._check_mitigating_controls(finding):
            confidence_score += 0.15
            reasons.append(FalsePositiveReason.MITIGATING_CONTROL)

        if self._check_third_party(finding):
            confidence_score += 0.10
            reasons.append(FalsePositiveReason.THIRD_PARTY_CODE)

        if self._check_waf_blocked(finding):
            confidence_score += 0.20
            reasons.append(FalsePositiveReason.WAF_BLOCKED)

        confidence_score = min(confidence_score, 1.0)
        primary_reason = reasons[0].value if reasons else None

        if confidence_score >= 0.60:
            logger.info(
                "Finding %s flagged as likely false positive (confidence=%.2f, reason=%s)",
                finding_id,
                confidence_score,
                primary_reason,
            )

        return confidence_score, primary_reason

    def _check_reproducibility(self, finding: dict[str, Any]) -> bool:
        if not finding.get("proof_of_concept"):
            return False
        if not finding.get("endpoint"):
            return False
        if not finding.get("payload_used"):
            return False
        return True

    def _check_expected_behavior(self, finding: dict[str, Any]) -> bool:
        vuln_type = str(finding.get("vulnerability_type") or "").lower()
        endpoint = str(finding.get("endpoint") or "").lower()
        description = str(finding.get("description") or "").lower()

        if vuln_type == "xss" and "error" in endpoint and "user input" in description:
            return True

        if vuln_type == "open redirect" and "same-site" in description:
            return True

        return False

    def _check_input_validation(self, finding: dict[str, Any]) -> bool:
        description = str(finding.get("description") or "").lower()
        validation_terms = ("encoded", "escaped", "sanitized", "filtered")
        return any(term in description for term in validation_terms)

    def _check_mitigating_controls(self, finding: dict[str, Any]) -> bool:
        description = str(finding.get("description") or "").lower()
        mitigation_terms = (
            "waf",
            "web application firewall",
            "csp header",
            "content security policy",
        )
        return any(term in description for term in mitigation_terms)

    def _check_third_party(self, finding: dict[str, Any]) -> bool:
        endpoint = str(finding.get("endpoint") or "").lower()
        description = str(finding.get("description") or "").lower()
        third_party_indicators = (
            "jquery",
            "bootstrap",
            "node_modules",
            "vendor",
            "dependency",
            "package",
            "npm",
            "composer",
        )
        return any(ind in endpoint or ind in description for ind in third_party_indicators)

    def _check_waf_blocked(self, finding: dict[str, Any]) -> bool:
        description = str(finding.get("description") or "").lower()
        poc = str(finding.get("proof_of_concept") or "").lower()
        return "blocked by waf" in description or "blocked by waf" in poc

