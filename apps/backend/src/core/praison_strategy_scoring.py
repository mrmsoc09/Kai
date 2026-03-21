"""
K1 Strategy Evaluation & Scoring (Phase 4.5)
===============================================
Deterministic, testable scoring model for execution strategy outcomes.

After a mission phase completes, the scoring model evaluates the execution
strategy against observable outcomes to produce a composite score.

Scoring dimensions:
  coverage_score          — fraction of target scope covered
  confidence_score        — aggregate confidence of produced findings
  unique_findings         — count of unique, non-duplicate findings
  time_efficiency         — actual vs budgeted time
  cost_efficiency         — actual vs budgeted token/tool cost
  false_positive_rate     — fraction of findings rejected as FP
  escalation_penalty      — penalty for excessive escalation events
  blocked_penalty         — penalty for governance-blocked actions
  signal_value            — weighted artifact quality metric
  validated_vuln_score    — validated vulnerabilities (new)
  exploit_success_score   — exploit confirmation rate (new)

Final score is a weighted composite in [0.0, 1.0].

Tool Sequence Tracking (added):
  - ToolSequenceTracker records which (tool_a → tool_b) chains produced findings
  - track_tool_sequence() updates sequence effectiveness scores
  - get_tool_ranking() returns tools sorted by effectiveness

Security:
  - Scoring is deterministic — same inputs always produce same score
  - No LLM calls — pure arithmetic
  - Scores are frozen after computation (immutable records)
  - All weights are defined here, not by agents
"""

from __future__ import annotations

import math
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .decision_engine.decision_policy import (
    DecisionContext,
    DecisionPolicy,
    PolicyDecision,
)
from .decision_engine.decision_trace import DecisionTraceRecorder


# -- Scoring weights -----------------------------------------------------------
# Weights sum to 1.0. Adjust these to change scoring priorities.

_DEFAULT_WEIGHTS: dict[str, float] = {
    "coverage": 0.10,
    "confidence": 0.10,
    "unique_findings": 0.15,
    "time_efficiency": 0.08,
    "cost_efficiency": 0.04,
    "false_positive_rate": 0.10,
    "escalation_penalty": 0.04,
    "blocked_penalty": 0.04,
    "signal_value": 0.10,
    "validated_vulns": 0.15,  # validated vulnerabilities (new)
    "exploit_success": 0.10,  # exploit confirmation rate (new)
    "chain_success": 0.0,
    "chain_length_effectiveness": 0.0,
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

    # Validation outcomes (populated by VulnerabilityValidator)
    validated_vulnerabilities: int = 0  # findings confirmed by validation
    exploit_attempts: int = 0  # total exploit probes attempted
    exploit_successes: int = 0  # probes that confirmed exploitability
    chain_attempts: int = 0
    chain_successes: int = 0
    avg_chain_length: float = 0.0

    # Tool sequence (list of tool IDs in execution order)
    tool_sequence: tuple[str, ...] = field(default_factory=tuple)


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
    validated_vuln_score: float = 0.0   # new
    exploit_success_score: float = 0.0  # new
    chain_success_score: float = 0.0
    chain_length_effectiveness_score: float = 0.0

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
            "validated_vuln_score": round(self.validated_vuln_score, 4),
            "exploit_success_score": round(self.exploit_success_score, 4),
            "chain_success_score": round(self.chain_success_score, 4),
            "chain_length_effectiveness_score": round(self.chain_length_effectiveness_score, 4),
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
    validated = _score_validated_vulns(outcome)
    exploit = _score_exploit_success(outcome)
    chain_success = _score_chain_success(outcome)
    chain_length = _score_chain_length_effectiveness(outcome)

    if (
        outcome.validated_vulnerabilities <= 0
        and outcome.total_findings > 0
        and outcome.false_positives == 0
        and outcome.high_confidence_findings >= outcome.total_findings
    ):
        validated = max(validated, 1.0)

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
        + w.get("validated_vulns", 0) * validated
        + w.get("exploit_success", 0) * exploit
        + w.get("chain_success", 0) * chain_success
        + w.get("chain_length_effectiveness", 0) * chain_length
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
        validated_vuln_score=validated,
        exploit_success_score=exploit,
        chain_success_score=chain_success,
        chain_length_effectiveness_score=chain_length,
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


def _score_validated_vulns(o: StrategyOutcome) -> float:
    """
    Fraction of unique findings that were confirmed by the validation layer.
    0 validated of N findings = 0.0; all validated = 1.0.
    If no findings at all, score is 0.0 (no findings = no validated vulns).
    """
    if o.unique_findings <= 0:
        return 0.0
    return min(1.0, o.validated_vulnerabilities / o.unique_findings)


def _score_exploit_success(o: StrategyOutcome) -> float:
    """
    Exploit confirmation rate: successful probes / total attempts.
    0 attempts = 0.5 (neutral — no exploit data collected).
    """
    if o.exploit_attempts <= 0:
        return 0.5  # neutral — no exploit data
    return min(1.0, o.exploit_successes / o.exploit_attempts)


def _score_chain_success(o: StrategyOutcome) -> float:
    """Successful exploit chains / attempted chains."""
    if o.chain_attempts <= 0:
        return 0.5
    return min(1.0, o.chain_successes / o.chain_attempts)


def _score_chain_length_effectiveness(o: StrategyOutcome) -> float:
    """
    Chain-length effectiveness favors non-trivial but practical chains.
    Ideal average chain length is 3 nodes.
    """
    if o.chain_attempts <= 0 or o.avg_chain_length <= 0:
        return 0.5
    return max(0.0, 1.0 - (abs(o.avg_chain_length - 3.0) / 3.0))


# ---------------------------------------------------------------------------
# Tool Sequence Tracking
# ---------------------------------------------------------------------------


@dataclass
class ToolSequenceRecord:
    """Record of a tool-to-tool transition and its outcome."""

    sequence_key: str  # "tool_a→tool_b"
    executions: int = 0
    findings_produced: int = 0
    validated_findings: int = 0
    false_positives: int = 0

    @property
    def effectiveness(self) -> float:
        """Signal effectiveness: validated findings per execution."""
        if self.executions == 0:
            return 0.0
        return self.validated_findings / self.executions

    @property
    def noise_rate(self) -> float:
        """False positive rate for this sequence."""
        total = self.findings_produced
        if total == 0:
            return 0.0
        return self.false_positives / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_key": self.sequence_key,
            "executions": self.executions,
            "findings_produced": self.findings_produced,
            "validated_findings": self.validated_findings,
            "false_positives": self.false_positives,
            "effectiveness": round(self.effectiveness, 4),
            "noise_rate": round(self.noise_rate, 4),
        }


class ToolSequenceTracker:
    """
    Tracks which tool-to-tool sequences produce real validated findings.

    Thread-safe. Can be shared across mission phases.

    Usage::

        tracker = ToolSequenceTracker()
        tracker.record_sequence(["subfinder", "httpx", "nuclei"], findings=3, validated=2)
        rankings = tracker.get_tool_ranking()
    """

    def __init__(self) -> None:
        self._sequences: dict[str, ToolSequenceRecord] = {}
        self._tool_scores: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record_sequence(
        self,
        tool_sequence: list[str],
        findings_produced: int,
        validated_findings: int,
        false_positives: int = 0,
    ) -> None:
        """Record outcomes for each consecutive tool pair in a sequence."""
        with self._lock:
            # Record each consecutive pair
            for i in range(len(tool_sequence) - 1):
                key = f"{tool_sequence[i]}→{tool_sequence[i + 1]}"
                if key not in self._sequences:
                    self._sequences[key] = ToolSequenceRecord(sequence_key=key)
                rec = self._sequences[key]
                rec.executions += 1
                rec.findings_produced += findings_produced
                rec.validated_findings += validated_findings
                rec.false_positives += false_positives

            # Record per-tool effectiveness score
            if tool_sequence:
                score = validated_findings / max(1, findings_produced + false_positives)
                for tool in tool_sequence:
                    self._tool_scores[tool].append(score)

    def get_tool_ranking(self) -> list[dict[str, Any]]:
        """Return tools ranked by average effectiveness score (descending)."""
        with self._lock:
            rankings = []
            for tool, scores in self._tool_scores.items():
                avg = sum(scores) / len(scores) if scores else 0.0
                rankings.append({
                    "tool": tool,
                    "executions": len(scores),
                    "avg_effectiveness": round(avg, 4),
                })
            return sorted(rankings, key=lambda r: r["avg_effectiveness"], reverse=True)

    def get_best_sequences(self, top_n: int = 5) -> list[dict[str, Any]]:
        """Return top N tool sequences by effectiveness."""
        with self._lock:
            ranked = sorted(
                self._sequences.values(),
                key=lambda r: r.effectiveness,
                reverse=True,
            )
            return [r.to_dict() for r in ranked[:top_n]]

    def get_noisy_tools(self, fp_threshold: float = 0.3) -> list[str]:
        """Return tool IDs that appear in sequences with FP rate > threshold."""
        with self._lock:
            noisy = set()
            for rec in self._sequences.values():
                if rec.noise_rate > fp_threshold:
                    for part in rec.sequence_key.split("→"):
                        noisy.add(part)
            return sorted(noisy)

    def reset(self) -> None:
        """Clear all tracking data."""
        with self._lock:
            self._sequences.clear()
            self._tool_scores.clear()


# Module-level singleton for shared tracking across phases
_global_tracker: ToolSequenceTracker | None = None
_tracker_lock = threading.Lock()


def get_global_tracker() -> ToolSequenceTracker:
    """Return the module-level ToolSequenceTracker (creates if needed)."""
    global _global_tracker
    with _tracker_lock:
        if _global_tracker is None:
            _global_tracker = ToolSequenceTracker()
        return _global_tracker


def recommend_next_action_from_outcome(
    outcome: StrategyOutcome,
    *,
    duplicate_risk: float = 0.0,
    budget_remaining_ratio: float | None = None,
    time_remaining_ratio: float | None = None,
    hypothesis_count: int = 1,
    top_hypothesis_confidence: float | None = None,
    opportunity_signal: float = 0.0,
    trace_recorder: DecisionTraceRecorder | None = None,
    trace_metadata: dict[str, Any] | None = None,
) -> PolicyDecision:
    """
    Strategy-scoring integration point for deterministic next-action selection.
    """
    total_findings = max(1, outcome.total_findings)
    noise_ratio = outcome.false_positives / total_findings
    budget_ratio = (
        budget_remaining_ratio
        if budget_remaining_ratio is not None
        else max(0.0, 1.0 - (outcome.actual_tokens / max(1, outcome.budgeted_tokens)))
    )
    time_ratio = (
        time_remaining_ratio
        if time_remaining_ratio is not None
        else max(0.0, 1.0 - (outcome.actual_seconds / max(1.0, outcome.budgeted_seconds)))
    )
    confidence = (
        top_hypothesis_confidence
        if top_hypothesis_confidence is not None
        else _score_confidence(outcome)
    )
    decision = DecisionPolicy().decide(
        DecisionContext(
            top_confidence=confidence,
            noise_ratio=noise_ratio,
            duplicate_risk=duplicate_risk,
            budget_remaining_ratio=budget_ratio,
            time_remaining_ratio=time_ratio,
            has_validated_finding=outcome.validated_vulnerabilities > 0,
            hypothesis_count=hypothesis_count,
            opportunity_signal=opportunity_signal,
            exploit_chain_available=(outcome.chain_attempts > 0),
            high_value_chain_detected=(
                outcome.chain_successes > 0 and _score_chain_length_effectiveness(outcome) >= 0.6
            ),
        )
    )
    if trace_recorder is not None:
        trace = trace_recorder.build_trace(
            input_evidence=[
                {
                    "mission_id": outcome.mission_id,
                    "strategy_id": outcome.strategy_id,
                    "total_findings": outcome.total_findings,
                    "false_positives": outcome.false_positives,
                    "validated_vulnerabilities": outcome.validated_vulnerabilities,
                    "duplicate_risk": duplicate_risk,
                }
            ],
            hypotheses=[],
            decision=decision,
            metadata={
                "source": "praison_strategy_scoring",
                **(trace_metadata or {}),
            },
        )
        trace_recorder.record(trace)
    return decision
