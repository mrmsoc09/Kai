from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from tools.intelligence.severity_payout_estimator import SeverityPayoutEstimator


class AIVerificationAssistant:
    """
    AI-assisted verification that supports analyst review.

    This assistant flags issues and provides confidence; it does not approve/reject.
    """

    def __init__(self) -> None:
        self.estimator = SeverityPayoutEstimator()

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().lower()

    def is_vague(self, step: str) -> bool:
        s = self._normalize(step)
        if len(s) < 12:
            return True
        vague_markers = ["maybe", "somehow", "etc", "stuff", "something"]
        return any(v in s for v in vague_markers)

    def is_technically_sound(self, step: str) -> bool:
        s = self._normalize(step)
        # conservative heuristic: must include an action and an observable result signal
        action_markers = ["send", "request", "validate", "observe", "verify", "compare", "check"]
        result_markers = ["response", "status", "signal", "header", "body", "error", "output"]
        return any(a in s for a in action_markers) and any(r in s for r in result_markers)

    def suggest_clarification(self, step: str) -> str:
        return f"Clarify exact request/input and expected observable response for step: '{step}'"

    def suggest_correction(self, step: str) -> str:
        return f"Rewrite as deterministic action + expected indicator (status/body/header) for: '{step}'"

    def analyze_poc_clarity(self, poc_steps: list[str]) -> dict[str, Any]:
        if not poc_steps:
            return {
                "clarity_score": 0.0,
                "flagged_steps": [{"step": "<none>", "issue": "No POC steps provided", "suggestion": "Add reproducible steps"}],
                "ai_confidence": 0.4,
                "analyst_review_needed": True,
            }

        flagged_steps = []
        score = 1.0
        for step in poc_steps:
            if self.is_vague(step):
                score -= 0.12
                flagged_steps.append(
                    {
                        "step": step,
                        "issue": "Step is vague or lacks specific details",
                        "suggestion": self.suggest_clarification(step),
                    }
                )
            if not self.is_technically_sound(step):
                score -= 0.10
                flagged_steps.append(
                    {
                        "step": step,
                        "issue": "Step may be technically incomplete",
                        "suggestion": self.suggest_correction(step),
                    }
                )

        clarity = round(max(0.0, min(1.0, score)), 2)
        ai_conf = round(0.7 + min(0.25, len(poc_steps) * 0.03), 2)
        return {
            "clarity_score": clarity,
            "flagged_steps": flagged_steps,
            "ai_confidence": ai_conf,
            "analyst_review_needed": bool(flagged_steps),
        }

    def _extract_scope(self, scope_definition: dict[str, Any]) -> tuple[list[str], list[str]]:
        targets = [str(x).lower() for x in scope_definition.get("targets", [])]
        exclusions = [str(x).lower() for x in scope_definition.get("exclusions", [])]
        return targets, exclusions

    def validate_scope_compliance(self, finding: dict[str, Any], scope_definition: dict[str, Any]) -> dict[str, Any]:
        endpoint = str(finding.get("target_endpoint") or finding.get("endpoint") or "").strip().lower()
        host = urlparse(endpoint).hostname or endpoint

        targets, exclusions = self._extract_scope(scope_definition)

        in_scope = any(host == t or host.endswith(f".{t}") for t in targets)
        out_scope = any(host == x or host.endswith(f".{x}") for x in exclusions)

        if in_scope and not out_scope:
            return {"scope_status": "IN_SCOPE", "confidence": 0.95, "analyst_review_needed": False}
        if out_scope:
            return {"scope_status": "OUT_OF_SCOPE", "confidence": 0.98, "analyst_review_needed": True}
        return {"scope_status": "BOUNDARY_CASE", "confidence": 0.60, "analyst_review_needed": True}

    def validate_severity_estimate(self, finding: dict[str, Any], target_context: dict[str, Any]) -> dict[str, Any]:
        predicted = self.estimator.estimate_severity(finding, target_context)
        estimated_score = float((finding.get("severity") or {}).get("severity_score", predicted["severity_score"]))
        recommended_score = float(predicted["severity_score"])

        delta = estimated_score - recommended_score
        if abs(delta) <= 0.7:
            status = "REASONABLE"
            conf = 0.88
        elif delta < -0.7:
            status = "POTENTIALLY_UNDERESTIMATED"
            conf = 0.75
        else:
            status = "POTENTIALLY_OVERESTIMATED"
            conf = 0.75

        return {
            "severity_validation": status,
            "confidence": conf,
            "estimated_score": round(estimated_score, 2),
            "recommended_score": round(recommended_score, 2),
            "analyst_review_needed": conf < 0.85,
        }


__all__ = ["AIVerificationAssistant"]
