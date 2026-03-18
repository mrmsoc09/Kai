"""
K1 Strategy Learning Orchestrator (Phase 4.5)
================================================
Closed-loop learning system that consumes execution outcomes and produces
strategy recommendations for future missions.

Loop:
  strategy → execution → artifacts → scoring → learning → updated strategy

The learning system:
  1. Scores completed phase executions (via praison_strategy_scoring)
  2. Updates profile performance metrics (via praison_profile_tracker)
  3. Produces knowledge lessons from high-signal outcomes (via praison_knowledge_base)
  4. Recommends profile selections for future executions

Learning boundaries (ENFORCED):
  MAY influence:
    - Tool ordering within approved set
    - Profile selection among pre-approved profiles
    - Retry/timing adjustments within bounds
    - Work prioritization within same phase

  MUST NOT influence:
    - Scope decisions (targets, domains)
    - Governance rules (approval thresholds, policy bands)
    - Tool allowlists (which tools exist)
    - Graph topology (node/edge structure)
    - Approval bypass

Security:
  - All operations are deterministic — no LLM calls
  - Recommendations are validated through existing governance
  - Low-confidence lessons are quarantined, not applied
  - All learning actions emit audit events
  - Forbidden boundary violations are rejected with reason
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from apps.backend.src.core.praison_adaptive import (
    AdaptiveChangeType,
    ExecutionPlanPatch,
    ExecutionStrategy,
    validate_plan_patch,
)
from apps.backend.src.core.praison_execution_events import (
    emit,
    phase_outcome_scored_event,
    strategy_selected_event,
)
from apps.backend.src.core.praison_knowledge_base import (
    KnowledgeBase,
    KnowledgeLesson,
    get_knowledge_base,
)
from apps.backend.src.core.praison_profile_tracker import (
    ProfileTracker,
    get_profile_tracker,
)
from apps.backend.src.core.praison_strategy_scoring import (
    StrategyOutcome,
    StrategyScore,
    score_strategy,
)

logger = logging.getLogger(__name__)


# -- Learning boundaries -------------------------------------------------------

# Fields that learning MAY influence in strategy recommendations
_ALLOWED_LEARNING_FIELDS = frozenset({
    "tool_order",
    "tool_profile_id",
    "prompt_profile_id",
    "retry_policy",
    "parallelism",
    "work_priority",
})

# Fields that learning MUST NOT touch
_FORBIDDEN_LEARNING_FIELDS = frozenset({
    "scope",
    "targets",
    "domains",
    "governance_rules",
    "approval_thresholds",
    "policy_bands",
    "tool_allowlist",
    "tool_candidates",
    "graph_topology",
    "nodes",
    "edges",
    "approval_bypass",
})

# Minimum score threshold to produce a lesson from an outcome
_LESSON_SCORE_THRESHOLD = 0.6

# Minimum executions before a profile recommendation is trusted
_MIN_EXECUTIONS_FOR_RECOMMENDATION = 3


# -- Strategy recommendation --------------------------------------------------


@dataclass(frozen=True)
class StrategyRecommendation:
    """
    A learning-produced recommendation for strategy configuration.

    Recommendations are proposals — they still pass through governance
    validation (validate_plan_patch) before being applied.
    """
    recommendation_id: str = ""
    field: str = ""              # which field to adjust (must be in _ALLOWED_LEARNING_FIELDS)
    current_value: Any = None
    recommended_value: Any = None
    reason: str = ""
    confidence: float = 0.0      # [0.0, 1.0]
    based_on_executions: int = 0  # how many data points informed this

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "field": self.field,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "based_on_executions": self.based_on_executions,
        }


# -- Learning rejection --------------------------------------------------------


@dataclass(frozen=True)
class LearningRejection:
    """Records why a learning action was rejected."""
    field: str = ""
    reason: str = ""
    boundary_type: str = ""  # "forbidden_field" | "governance_rejected" | "low_confidence"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "reason": self.reason,
            "boundary_type": self.boundary_type,
        }


# -- StrategyLearner -----------------------------------------------------------


class StrategyLearner:
    """
    Closed-loop learning orchestrator.

    Consumes execution outcomes, updates metrics, produces lessons,
    and generates bounded strategy recommendations.

    Thread-safe through delegation to thread-safe subsystems.
    """

    def __init__(
        self,
        knowledge_base: KnowledgeBase | None = None,
        profile_tracker: ProfileTracker | None = None,
    ) -> None:
        self._kb = knowledge_base or get_knowledge_base()
        self._tracker = profile_tracker or get_profile_tracker()

    def process_outcome(
        self,
        outcome: StrategyOutcome,
        *,
        success: bool = True,
        tool_profile_id: str = "",
        tool_profile_name: str = "",
        prompt_profile_id: str = "",
        prompt_profile_name: str = "",
        agent_id: str = "",
        workflow_id: str = "",
        program_id: str = "",
    ) -> StrategyScore:
        """
        Process a completed phase execution outcome.

        1. Score the outcome
        2. Update tool profile metrics (if used)
        3. Update prompt profile metrics (if used)
        4. Produce knowledge lessons (if score warrants)
        5. Emit telemetry

        Returns the computed StrategyScore.
        """
        # 1. Score
        score = score_strategy(outcome)

        # 2. Emit scoring event
        emit(phase_outcome_scored_event(
            mission_id=outcome.mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            phase=outcome.phase,
            score=score.composite_score,
            detail=score.to_dict(),
        ))

        logger.info(
            "Phase outcome scored: mission=%s phase=%s composite=%.3f",
            outcome.mission_id, outcome.phase, score.composite_score,
        )

        # 3. Update tool profile metrics
        if tool_profile_id:
            self._tracker.record_execution(
                profile_id=tool_profile_id,
                profile_type="tool",
                profile_name=tool_profile_name,
                score=score,
                success=success,
                actual_seconds=outcome.actual_seconds,
                false_positives=outcome.false_positives,
                total_findings=outcome.total_findings,
                mission_id=outcome.mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
            )

        # 4. Update prompt profile metrics
        if prompt_profile_id:
            self._tracker.record_execution(
                profile_id=prompt_profile_id,
                profile_type="prompt",
                profile_name=prompt_profile_name,
                score=score,
                success=success,
                actual_seconds=outcome.actual_seconds,
                false_positives=outcome.false_positives,
                total_findings=outcome.total_findings,
                mission_id=outcome.mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
            )

        # 5. Produce knowledge lessons if high-signal
        if score.composite_score >= _LESSON_SCORE_THRESHOLD:
            self._produce_lessons(outcome, score, agent_id=agent_id, workflow_id=workflow_id,
                                  program_id=program_id, tool_profile_id=tool_profile_id,
                                  prompt_profile_id=prompt_profile_id)

        return score

    def recommend_tool_profile(
        self,
        candidate_ids: list[str],
        metric: str = "avg_score",
    ) -> StrategyRecommendation | None:
        """
        Recommend the best tool profile from candidates based on tracked metrics.

        Returns None if insufficient data for a recommendation.
        """
        best_id = self._tracker.best_profile(
            profile_ids=candidate_ids,
            metric=metric,
            min_executions=_MIN_EXECUTIONS_FOR_RECOMMENDATION,
        )
        if best_id is None:
            return None

        metrics = self._tracker.get_metrics(best_id)
        if metrics is None:
            return None

        return StrategyRecommendation(
            field="tool_profile_id",
            recommended_value=best_id,
            reason=f"Best {metric} ({getattr(metrics, metric):.3f}) among candidates "
                   f"with {metrics.executions} executions",
            confidence=min(1.0, metrics.executions / 10.0),  # confidence grows with data
            based_on_executions=metrics.executions,
        )

    def recommend_prompt_profile(
        self,
        candidate_ids: list[str],
        metric: str = "avg_score",
    ) -> StrategyRecommendation | None:
        """
        Recommend the best prompt profile from candidates based on tracked metrics.
        """
        best_id = self._tracker.best_profile(
            profile_ids=candidate_ids,
            metric=metric,
            min_executions=_MIN_EXECUTIONS_FOR_RECOMMENDATION,
        )
        if best_id is None:
            return None

        metrics = self._tracker.get_metrics(best_id)
        if metrics is None:
            return None

        return StrategyRecommendation(
            field="prompt_profile_id",
            recommended_value=best_id,
            reason=f"Best {metric} ({getattr(metrics, metric):.3f}) among candidates "
                   f"with {metrics.executions} executions",
            confidence=min(1.0, metrics.executions / 10.0),
            based_on_executions=metrics.executions,
        )

    def recommend_tool_order(
        self,
        current_order: list[str],
        phase: str = "",
    ) -> StrategyRecommendation | None:
        """
        Recommend tool ordering based on knowledge base lessons.

        Looks up tool_order_lesson entries for the given phase and suggests
        reordering if a high-confidence lesson exists.
        """
        lessons = self._kb.get_lessons(
            lesson_type="tool_order_lesson",
            min_confidence=0.7,
            limit=5,
        )
        if not lessons:
            return None

        # Find the highest-confidence lesson matching this phase
        for lesson in lessons:
            if phase and lesson.phase and lesson.phase != phase:
                continue
            suggested_order = lesson.content.get("tool_order")
            if not isinstance(suggested_order, list):
                continue
            # Only recommend if the suggested order contains the same tools
            if set(suggested_order) == set(current_order) and suggested_order != current_order:
                return StrategyRecommendation(
                    field="tool_order",
                    current_value=current_order,
                    recommended_value=suggested_order,
                    reason=f"Knowledge lesson {lesson.lesson_id}: {lesson.summary}",
                    confidence=lesson.confidence,
                    based_on_executions=1,
                )

        return None

    def validate_recommendation(
        self,
        recommendation: StrategyRecommendation,
        strategy: ExecutionStrategy,
    ) -> LearningRejection | None:
        """
        Validate a learning recommendation against boundaries and governance.

        Returns None if valid, LearningRejection if invalid.
        """
        # Check learning boundaries
        if recommendation.field in _FORBIDDEN_LEARNING_FIELDS:
            return LearningRejection(
                field=recommendation.field,
                reason=f"Field '{recommendation.field}' is in the forbidden learning boundary. "
                       "Learning cannot influence this field.",
                boundary_type="forbidden_field",
            )

        if recommendation.field not in _ALLOWED_LEARNING_FIELDS:
            return LearningRejection(
                field=recommendation.field,
                reason=f"Field '{recommendation.field}' is not in the allowed learning fields.",
                boundary_type="forbidden_field",
            )

        # Low confidence check
        if recommendation.confidence < 0.3:
            return LearningRejection(
                field=recommendation.field,
                reason=f"Recommendation confidence ({recommendation.confidence:.2f}) below threshold (0.30)",
                boundary_type="low_confidence",
            )

        # Validate through governance (for fields that map to plan patches)
        change_type_map = {
            "tool_order": AdaptiveChangeType.REORDER_TOOLS.value,
            "tool_profile_id": AdaptiveChangeType.SELECT_PARAM_PROFILE.value,
            "prompt_profile_id": AdaptiveChangeType.SELECT_PROMPT_PROFILE.value,
            "retry_policy": AdaptiveChangeType.ADJUST_RETRY.value,
        }
        change_type = change_type_map.get(recommendation.field)
        if change_type:
            patch = ExecutionPlanPatch(
                mission_id=strategy.mission_id,
                phase_id=strategy.phase_id,
                proposed_by_agent="strategy_learner",
                change_type=change_type,
                old_value=recommendation.current_value,
                new_value=recommendation.recommended_value,
                justification=recommendation.reason,
                expected_benefit=f"Learning-based recommendation (confidence={recommendation.confidence:.2f})",
            )
            result = validate_plan_patch(patch, strategy)
            if not result.valid:
                return LearningRejection(
                    field=recommendation.field,
                    reason=f"Governance rejected: {result.reason}",
                    boundary_type="governance_rejected",
                )

        return None

    def apply_recommendations(
        self,
        recommendations: list[StrategyRecommendation],
        strategy: ExecutionStrategy,
        mission_id: str = "",
        workflow_id: str = "",
        program_id: str = "",
    ) -> tuple[list[StrategyRecommendation], list[LearningRejection]]:
        """
        Validate and filter a list of recommendations.

        Returns:
          - accepted: recommendations that passed validation
          - rejected: rejections for those that failed

        Note: This does NOT mutate the strategy. The caller (governance layer)
        is responsible for applying accepted recommendations through the
        standard plan patch mechanism.
        """
        accepted = []
        rejected = []

        for rec in recommendations:
            rejection = self.validate_recommendation(rec, strategy)
            if rejection is None:
                accepted.append(rec)
            else:
                rejected.append(rejection)
                logger.info(
                    "Learning recommendation rejected: field=%s reason=%s",
                    rec.field, rejection.reason,
                )

        if accepted:
            emit(strategy_selected_event(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                agent_id="strategy_learner",
                strategy_id=strategy.strategy_id,
                phase=strategy.phase_id,
            ))
            logger.info(
                "Learning recommendations: %d accepted, %d rejected",
                len(accepted), len(rejected),
            )

        return accepted, rejected

    def get_learning_summary(self) -> dict[str, Any]:
        """Return a summary of the learning system state."""
        tool_metrics = self._tracker.get_all_metrics(profile_type="tool")
        prompt_metrics = self._tracker.get_all_metrics(profile_type="prompt")

        return {
            "tool_profiles_tracked": len(tool_metrics),
            "prompt_profiles_tracked": len(prompt_metrics),
            "knowledge_lessons": self._kb.lesson_count(),
            "quarantined_lessons": self._kb.quarantine_count(),
            "top_tool_profiles": [
                m.to_dict() for m in self._tracker.rank_profiles("tool", min_executions=1)[:3]
            ],
            "top_prompt_profiles": [
                m.to_dict() for m in self._tracker.rank_profiles("prompt", min_executions=1)[:3]
            ],
        }

    # -- Internal helpers ------------------------------------------------------

    def _produce_lessons(
        self,
        outcome: StrategyOutcome,
        score: StrategyScore,
        *,
        agent_id: str = "",
        workflow_id: str = "",
        program_id: str = "",
        tool_profile_id: str = "",
        prompt_profile_id: str = "",
    ) -> None:
        """Produce knowledge lessons from a high-scoring outcome."""
        # Tool order lesson — if the execution had high coverage + unique findings
        if score.coverage_score >= 0.7 and score.unique_findings_score >= 0.6:
            try:
                self._kb.add_lesson(KnowledgeLesson(
                    lesson_type="tool_order_lesson",
                    confidence=score.composite_score,
                    content={
                        "tool_profile_id": tool_profile_id,
                        "phase": outcome.phase,
                        "coverage_score": score.coverage_score,
                        "unique_findings_score": score.unique_findings_score,
                    },
                    summary=(
                        f"Tool profile {tool_profile_id} achieved "
                        f"coverage={score.coverage_score:.2f} unique={score.unique_findings_score:.2f} "
                        f"in phase {outcome.phase}"
                    ),
                    mission_id=outcome.mission_id,
                    workflow_id=workflow_id,
                    program_id=program_id,
                    agent_id=agent_id,
                    strategy_id=outcome.strategy_id,
                    phase=outcome.phase,
                ))
            except ValueError as exc:
                logger.debug("Tool order lesson rejected: %s", exc)

        # Prompt effectiveness lesson — if high signal value
        if score.signal_value_score >= 0.7 and prompt_profile_id:
            try:
                self._kb.add_lesson(KnowledgeLesson(
                    lesson_type="prompt_effectiveness",
                    confidence=score.composite_score,
                    content={
                        "prompt_profile_id": prompt_profile_id,
                        "phase": outcome.phase,
                        "signal_value": score.signal_value_score,
                        "confidence_score": score.confidence_score,
                    },
                    summary=(
                        f"Prompt profile {prompt_profile_id} produced "
                        f"signal={score.signal_value_score:.2f} confidence={score.confidence_score:.2f} "
                        f"in phase {outcome.phase}"
                    ),
                    mission_id=outcome.mission_id,
                    workflow_id=workflow_id,
                    program_id=program_id,
                    agent_id=agent_id,
                    strategy_id=outcome.strategy_id,
                    phase=outcome.phase,
                ))
            except ValueError as exc:
                logger.debug("Prompt effectiveness lesson rejected: %s", exc)

        # False positive indicator — if low FP rate is noteworthy
        if score.false_positive_score >= 0.9 and outcome.total_findings >= 5:
            try:
                self._kb.add_lesson(KnowledgeLesson(
                    lesson_type="false_positive_indicator",
                    confidence=score.composite_score,
                    content={
                        "tool_profile_id": tool_profile_id,
                        "total_findings": outcome.total_findings,
                        "false_positives": outcome.false_positives,
                        "fp_rate": outcome.false_positives / max(outcome.total_findings, 1),
                    },
                    summary=(
                        f"Profile {tool_profile_id} achieved FP rate "
                        f"{outcome.false_positives}/{outcome.total_findings} "
                        f"in phase {outcome.phase}"
                    ),
                    mission_id=outcome.mission_id,
                    workflow_id=workflow_id,
                    program_id=program_id,
                    agent_id=agent_id,
                    strategy_id=outcome.strategy_id,
                    phase=outcome.phase,
                ))
            except ValueError as exc:
                logger.debug("FP indicator lesson rejected: %s", exc)


# -- Module singleton ----------------------------------------------------------

_LEARNER: StrategyLearner | None = None


def get_strategy_learner() -> StrategyLearner:
    global _LEARNER
    if _LEARNER is None:
        _LEARNER = StrategyLearner()
    return _LEARNER


def initialize_strategy_learner(
    knowledge_base: KnowledgeBase | None = None,
    profile_tracker: ProfileTracker | None = None,
) -> StrategyLearner:
    global _LEARNER
    _LEARNER = StrategyLearner(knowledge_base, profile_tracker)
    return _LEARNER
