from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SafetyViolation(ValueError):
    """Raised when an AI-generated recommendation violates detection-only policy."""


FORBIDDEN_KEYWORDS = {
    "exploit",
    "exploitation",
    "compromise",
    "persistence",
    "backdoor",
    "lateral movement",
    "evasion",
    "destroy",
    "delete",
    "modify data",
    "ransomware",
    "infiltrate",
    "privilege_escalate",
    "bypass_auth",
    "shell",
    "dropper",
    "payload execution",
}

REQUIRED_DETECTION_CUES = {
    "detect",
    "test",
    "identify",
    "validate",
    "verify",
    "observe",
    "review",
}


@dataclass(slots=True)
class SafetyValidationResult:
    allowed: bool
    violations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "violations": self.violations}


class AIOperationsSafetyGates:
    """
    Safety gates for AI recommendation outputs.

    The gates enforce detection-only behavior and block any recommendation text
    that implies exploitation, persistence, destructive action, or evasion.
    """

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().lower()

    def validate_ai_recommendation(self, recommendation: dict[str, Any]) -> bool:
        text_fields = [
            self._normalize(str(recommendation.get("suggested_testing", ""))),
            self._normalize(str(recommendation.get("inference", ""))),
            self._normalize(str(recommendation.get("rationale", ""))),
            self._normalize(str(recommendation.get("recommendation", ""))),
        ]
        blob = " ".join(t for t in text_fields if t)

        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in blob:
                raise SafetyViolation(f"AI recommendation contains forbidden keyword: {keyword}")

        if not any(cue in blob for cue in REQUIRED_DETECTION_CUES):
            raise SafetyViolation("AI recommendation does not appear to be detection-only")

        return True

    def validate_recommendations_batch(self, recommendations: list[dict[str, Any]]) -> SafetyValidationResult:
        violations: list[str] = []
        for i, rec in enumerate(recommendations, start=1):
            try:
                self.validate_ai_recommendation(rec)
            except SafetyViolation as exc:
                violations.append(f"recommendation_{i}: {exc}")

        return SafetyValidationResult(allowed=not violations, violations=violations)

    def sanitize_recommendation(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        """
        Best-effort sanitization for borderline texts while preserving detection intent.
        """
        sanitized = dict(recommendation)
        text = self._normalize(str(sanitized.get("suggested_testing", "")))
        for keyword in FORBIDDEN_KEYWORDS:
            text = text.replace(keyword, "[blocked]")
        if text and not any(cue in text for cue in REQUIRED_DETECTION_CUES):
            text = f"identify and validate in-scope indicators safely: {text}"
        sanitized["suggested_testing"] = text
        sanitized["safety_gate"] = "sanitized_detection_only"
        return sanitized


__all__ = ["AIOperationsSafetyGates", "SafetyViolation", "SafetyValidationResult"]
