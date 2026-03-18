"""
K1 Strategy Evaluation & Scoring (Phase 4.5)
===============================================
Deterministic, testable scoring model for execution strategy outcomes.

After a mission phase completes, the scoring model evaluates the execution
strategy against observable outcomes to produce a composite score.

Scoring dimensions:
  coverage_score      — fraction of target scope covered
  confidence_score    — aggregate confidence of produced findings
  unique_findings     — count of unique, non-duplicate findings
  time_efficiency     — actual vs budgeted time
  cost_efficiency     — actual vs budgeted token/tool cost
  false_positive_rate — fraction of findings rejected as FP
  escalation_penalty  — penalty for excessive escalation events
  blocked_penalty     — penalty for governance-blocked actions
  signal_value        — weighted artifact quality metric

Final score is a weighted composite in [0.0, 1.0].

Security:
  - Scoring is deterministic — same inputs always produce same score
  - No LLM calls — pure arithmetic
  - Scores are frozen after computation (immutable records)
  - All weights are defined here, not by agents
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# -- Scoring weights -----------------------------------------------------------
# Weights sum to 1.0. Adjust these to change scoring priorities.

_DEFAULT_WEIGHTS: dict[str, float] = {
    "coverage": 0.15,
    "confidence": 0.15,
    "unique_findings": 0.20,
    "time_efficiency": 0.10,
    "cost_efficiency": 0.05,
    "false_positive_rate": 0.10,
    "escalation_penalty": 0.05,
    "blocked_penalty": 0.05,
    "signal_value": 0.15,
}


# -- Scoring input -------------------------------------------------------------


@dataclass(frozen=True)
class StrategyOutcome:
    """Observable outcomes from a strategy execution."""
    mission_id: str = ""
    phase: str = ""
    strategy_id: str = ""

    # Coverage
    targets_in_scope: int = 0
    targets_covered: int = 0

    # Findings
    total_findings: int = 0
    unique_findings: int = 0
    high_confidence_findings: int = 0
    medium_confidence_findings: int = 0
    low_confidence_findings: int = 0
    false_positives: int = 0

    # Time
    budgeted_seconds: float = 3600.0
    actual_seconds: float = 0.0

    # Cost
    budgeted_tokens: int = 100000
    actual_tokens: int = 0
    tool_invocations: int = 0

    # Governance
    escalation_count: int = 0
    blocked_count: int = 0
    approval_count: int = 0

    # Artifacts
    artifacts_produced: int = 0
    high_value_artifacts: int = 0

    # Tool/prompt profile used
    tool_profile_id: str = ""
    prompt_profile_id: str = ""


# -- Score result --------------------------------------------------------------


@dataclass(frozen=True)
class StrategyScore:
    """Computed strategy evaluation score. Frozen — immutable after creation."""
    mission_id: str = ""
    phase: str = ""
    strategy_id: str = ""
    tool_profile_id: str = ""
    prompt_profile_id: str = ""

    # Individual dimension scores [0.0, 1.0]
    coverage_score: float = 0.0
    confidence_score: float = 0.0
    unique_findings_score: float = 0.0
    time_efficiency_score: float = 0.0
    cost_efficiency_score: float = 0.0
    false_positive_score: float = 0.0
    escalation_score: float = 0.0
    blocked_score: float = 0.0
    signal_value_score: float = 0.0

    # Composite
    composite_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "phase": self.phase,
            "strategy_id": self.strategy_id,
            "tool_profile_id": self.tool_profile_id,
            "prompt_profile_id": self.prompt_profile_id,
            "coverage_score": round(self.coverage_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "unique_findings_score": round(self.unique_findings_score, 4),
            "time_efficiency_score": round(self.time_efficiency_score, 4),
            "cost_efficiency_score": round(self.cost_efficiency_score, 4),
            "false_positive_score": round(self.false_positive_score, 4),
            "escalation_score": round(self.escalation_score, 4),
            "blocked_score": round(self.blocked_score, 4),
            "signal_value_score": round(self.signal_value_score, 4),
            "composite_score": round(self.composite_score, 4),
        }


# -- Scoring functions ---------------------------------------------------------


def score_strategy(
    outcome: StrategyOutcome,
    weights: dict[str, float] | None = None,
) -> StrategyScore:
    """
    Compute a deterministic strategy score from observed outcomes.

    All dimensions produce a value in [0.0, 1.0] where higher is better.
    The composite score is the weighted sum of all dimensions.

    This function is pure — no I/O, no LLM calls, no side effects.
    """
    w = weights or _DEFAULT_WEIGHTS

    coverage = _score_coverage(outcome)
    confidence = _score_confidence(outcome)
    unique = _score_unique_findings(outcome)
    time_eff = _score_time_efficiency(outcome)
    cost_eff = _score_cost_efficiency(outcome)
    fp_rate = _score_false_positive_rate(outcome)
    escalation = _score_escalation(outcome)
    blocked = _score_blocked(outcome)
    signal = _score_signal_value(outcome)

    composite = (
        w.get("coverage", 0) * coverage
        + w.get("confidence", 0) * confidence
        + w.get("unique_findings", 0) * unique
        + w.get("time_efficiency", 0) * time_eff
        + w.get("cost_efficiency", 0) * cost_eff
        + w.get("false_positive_rate", 0) * fp_rate
        + w.get("escalation_penalty", 0) * escalation
        + w.get("blocked_penalty", 0) * blocked
        + w.get("signal_value", 0) * signal
    )
    composite = max(0.0, min(1.0, composite))

    return StrategyScore(
        mission_id=outcome.mission_id,
        phase=outcome.phase,
        strategy_id=outcome.strategy_id,
        tool_profile_id=outcome.tool_profile_id,
        prompt_profile_id=outcome.prompt_profile_id,
        coverage_score=coverage,
        confidence_score=confidence,
        unique_findings_score=unique,
        time_efficiency_score=time_eff,
        cost_efficiency_score=cost_eff,
        false_positive_score=fp_rate,
        escalation_score=escalation,
        blocked_score=blocked,
        signal_value_score=signal,
        composite_score=composite,
    )


# -- Individual dimension scorers ----------------------------------------------


def _score_coverage(o: StrategyOutcome) -> float:
    """Fraction of in-scope targets covered. 0 if no targets."""
    if o.targets_in_scope <= 0:
        return 0.0
    return min(1.0, o.targets_covered / o.targets_in_scope)


def _score_confidence(o: StrategyOutcome) -> float:
    """Weighted confidence: high=1.0, medium=0.6, low=0.2."""
    total = o.high_confidence_findings + o.medium_confidence_findings + o.low_confidence_findings
    if total == 0:
        return 0.0
    weighted = (
        o.high_confidence_findings * 1.0
        + o.medium_confidence_findings * 0.6
        + o.low_confidence_findings * 0.2
    )
    return min(1.0, weighted / total)


def _score_unique_findings(o: StrategyOutcome) -> float:
    """
    Unique findings relative to total. Higher dedup ratio = better.
    Uses sigmoid-like scaling: 1-5 findings = good, >10 = diminishing returns.
    """
    if o.unique_findings <= 0:
        return 0.0
    # Sigmoid: 5 findings -> ~0.75, 10 -> ~0.9, 20 -> ~0.97
    return 1.0 - math.exp(-0.15 * o.unique_findings)


def _score_time_efficiency(o: StrategyOutcome) -> float:
    """Score based on time usage vs budget. Under budget = 1.0, 2x over = 0.0."""
    if o.budgeted_seconds <= 0:
        return 1.0 if o.actual_seconds == 0 else 0.5
    ratio = o.actual_seconds / o.budgeted_seconds
    if ratio <= 1.0:
        return 1.0
    # Linear decay: 1x budget = 1.0, 2x budget = 0.0
    return max(0.0, 2.0 - ratio)


def _score_cost_efficiency(o: StrategyOutcome) -> float:
    """Score based on token usage vs budget."""
    if o.budgeted_tokens <= 0:
        return 1.0 if o.actual_tokens == 0 else 0.5
    ratio = o.actual_tokens / o.budgeted_tokens
    if ratio <= 1.0:
        return 1.0
    return max(0.0, 2.0 - ratio)


def _score_false_positive_rate(o: StrategyOutcome) -> float:
    """Lower FP rate = higher score. FP rate of 0% = 1.0, 50% = 0.5."""
    if o.total_findings <= 0:
        return 1.0  # no findings = no FPs
    fp_rate = o.false_positives / o.total_findings
    return max(0.0, 1.0 - fp_rate)


def _score_escalation(o: StrategyOutcome) -> float:
    """Penalty for excessive escalation. 0 escalations = 1.0, >5 = 0.0."""
    if o.escalation_count <= 0:
        return 1.0
    return max(0.0, 1.0 - (o.escalation_count / 5.0))


def _score_blocked(o: StrategyOutcome) -> float:
    """Penalty for blocked actions. 0 blocked = 1.0, >3 = 0.0."""
    if o.blocked_count <= 0:
        return 1.0
    return max(0.0, 1.0 - (o.blocked_count / 3.0))


def _score_signal_value(o: StrategyOutcome) -> float:
    """Signal quality: high-value artifacts relative to total produced."""
    if o.artifacts_produced <= 0:
        return 0.0
    return min(1.0, o.high_value_artifacts / o.artifacts_produced)
