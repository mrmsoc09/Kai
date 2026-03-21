from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


class DecisionAction(str, Enum):
    CONTINUE = "continue"
    VALIDATE = "validate"
    EXPLOIT = "exploit"
    PIVOT = "pivot"
    STOP = "stop"
    GENERATE_OPPORTUNITY = "generate_opportunity"


@dataclass(frozen=True)
class DecisionContext:
    top_confidence: float
    noise_ratio: float
    duplicate_risk: float
    budget_remaining_ratio: float
    time_remaining_ratio: float
    has_validated_finding: bool
    hypothesis_count: int
    opportunity_signal: float = 0.0
    exploit_chain_available: bool = False
    high_value_chain_detected: bool = False


@dataclass(frozen=True)
class PolicyThresholds:
    min_validate_confidence: float = 0.45
    min_exploit_confidence: float = 0.72
    min_generate_opportunity_confidence: float = 0.62
    max_noise_for_exploit: float = 0.35
    max_noise_ratio: float = 0.70
    max_duplicate_for_exploit: float = 0.85
    critical_budget_ratio: float = 0.05
    critical_time_ratio: float = 0.05
    min_decision_score: float = 0.30


@dataclass(frozen=True)
class RejectedAlternative:
    action: DecisionAction
    score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "score": round(self.score, 4),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PolicyDecision:
    chosen_action: DecisionAction
    reason_code: str
    score: float
    rejected_alternatives: list[RejectedAlternative]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chosen_action": self.chosen_action.value,
            "reason_code": self.reason_code,
            "score": round(self.score, 4),
            "rejected_alternatives": [row.to_dict() for row in self.rejected_alternatives],
        }


class DecisionPolicy:
    def __init__(self, thresholds: PolicyThresholds | None = None) -> None:
        self._thresholds = thresholds or PolicyThresholds()

    def decide(self, context: DecisionContext) -> PolicyDecision:
        normalized = DecisionContext(
            top_confidence=_clamp(context.top_confidence),
            noise_ratio=_clamp(context.noise_ratio),
            duplicate_risk=_clamp(context.duplicate_risk),
            budget_remaining_ratio=_clamp(context.budget_remaining_ratio),
            time_remaining_ratio=_clamp(context.time_remaining_ratio),
            has_validated_finding=bool(context.has_validated_finding),
            hypothesis_count=max(0, int(context.hypothesis_count)),
            opportunity_signal=_clamp(context.opportunity_signal),
            exploit_chain_available=bool(context.exploit_chain_available),
            high_value_chain_detected=bool(context.high_value_chain_detected),
        )
        if (
            normalized.budget_remaining_ratio <= self._thresholds.critical_budget_ratio
            or normalized.time_remaining_ratio <= self._thresholds.critical_time_ratio
        ):
            rejected = [
                RejectedAlternative(action=action, score=0.0, reason="critical_resource_limit")
                for action in DecisionAction
                if action is not DecisionAction.STOP
            ]
            return PolicyDecision(
                chosen_action=DecisionAction.STOP,
                reason_code="critical_resource_limit",
                score=1.0,
                rejected_alternatives=rejected,
            )

        scored: dict[DecisionAction, tuple[float, str]] = {
            DecisionAction.CONTINUE: self._score_continue(normalized),
            DecisionAction.VALIDATE: self._score_validate(normalized),
            DecisionAction.EXPLOIT: self._score_exploit(normalized),
            DecisionAction.PIVOT: self._score_pivot(normalized),
            DecisionAction.STOP: self._score_stop(normalized),
            DecisionAction.GENERATE_OPPORTUNITY: self._score_generate_opportunity(normalized),
        }

        selected_action = max(scored.items(), key=lambda item: item[1][0])[0]
        selected_score, selected_reason = scored[selected_action]
        if (
            selected_action is not DecisionAction.STOP
            and selected_score < self._thresholds.min_decision_score
        ):
            selected_action = DecisionAction.STOP
            selected_score = max(selected_score, scored[DecisionAction.STOP][0], 0.5)
            selected_reason = "insufficient_signal"

        rejected = [
            RejectedAlternative(action=action, score=score, reason=reason)
            for action, (score, reason) in scored.items()
            if action is not selected_action
        ]
        rejected.sort(key=lambda row: row.score, reverse=True)

        return PolicyDecision(
            chosen_action=selected_action,
            reason_code=selected_reason,
            score=round(selected_score, 4),
            rejected_alternatives=rejected,
        )

    def _score_continue(self, context: DecisionContext) -> tuple[float, str]:
        resource_factor = min(context.budget_remaining_ratio, context.time_remaining_ratio)
        score = context.top_confidence * (1.0 - context.noise_ratio) * resource_factor
        reason = "continue_exploration"
        if context.hypothesis_count <= 0:
            score *= 0.2
            reason = "no_hypotheses"
        if context.has_validated_finding:
            score *= 0.65
            reason = "validated_signal_prefer_action"
        if context.high_value_chain_detected:
            score *= 0.70
            reason = "high_value_chain_prefer_action"
        return _clamp(score), reason

    def _score_validate(self, context: DecisionContext) -> tuple[float, str]:
        if context.has_validated_finding:
            return 0.05, "already_validated"
        if context.top_confidence < self._thresholds.min_validate_confidence:
            return context.top_confidence * 0.3, "confidence_below_validate_threshold"
        score = context.top_confidence * (1.0 - context.noise_ratio) * (1.0 - context.duplicate_risk)
        return _clamp(score), "validation_candidate_ready"

    def _score_exploit(self, context: DecisionContext) -> tuple[float, str]:
        if not context.has_validated_finding:
            if context.exploit_chain_available and context.high_value_chain_detected:
                return _clamp(context.top_confidence * 0.45), "exploit_chain_requires_validation_or_governance"
            return 0.0, "validated_finding_required"
        if context.top_confidence < self._thresholds.min_exploit_confidence:
            return context.top_confidence * 0.4, "confidence_below_exploit_threshold"
        if context.noise_ratio > self._thresholds.max_noise_for_exploit:
            return 0.05, "noise_too_high_for_exploit"
        if context.duplicate_risk > self._thresholds.max_duplicate_for_exploit:
            return 0.10, "duplicate_risk_too_high"
        score = (
            context.top_confidence
            * (1.0 - context.noise_ratio)
            * min(context.budget_remaining_ratio, context.time_remaining_ratio)
        )
        score *= 1.10
        if context.exploit_chain_available:
            score *= 1.08
        if context.high_value_chain_detected:
            score *= 1.12
        return _clamp(score), "validated_high_confidence_signal"

    def _score_pivot(self, context: DecisionContext) -> tuple[float, str]:
        pivot_pressure = max(context.noise_ratio, context.duplicate_risk)
        confidence_penalty = 1.0 - context.top_confidence
        score = 0.6 * pivot_pressure + 0.4 * confidence_penalty
        reason = "high_noise_or_duplicate_pressure"
        if context.hypothesis_count <= 0:
            score = max(score, 0.7)
            reason = "no_viable_hypothesis"
        if context.high_value_chain_detected:
            score *= 0.60
            reason = "high_value_chain_available"
        return _clamp(score), reason

    def _score_stop(self, context: DecisionContext) -> tuple[float, str]:
        resource_pressure = 1.0 - min(context.budget_remaining_ratio, context.time_remaining_ratio)
        weak_signal = 1.0 - context.top_confidence
        score = max(resource_pressure, weak_signal * 0.8, context.noise_ratio * 0.7)
        reason = "stop_loss"
        if context.noise_ratio >= self._thresholds.max_noise_ratio:
            score = max(score, 0.85)
            reason = "noise_threshold_exceeded"
        return _clamp(score), reason

    def _score_generate_opportunity(self, context: DecisionContext) -> tuple[float, str]:
        if context.top_confidence < self._thresholds.min_generate_opportunity_confidence:
            return context.top_confidence * 0.35, "confidence_below_opportunity_threshold"
        if context.opportunity_signal <= 0.0:
            return context.top_confidence * 0.2, "opportunity_signal_missing"
        score = (
            context.top_confidence
            * context.opportunity_signal
            * (1.0 - context.duplicate_risk)
            * (1.0 - (0.5 * context.noise_ratio))
        )
        if context.exploit_chain_available:
            score *= 1.10
        if context.high_value_chain_detected:
            score *= 1.15
        return _clamp(score), "opportunity_signal_detected"
