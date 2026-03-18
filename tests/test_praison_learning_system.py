"""
K1 Learning System Tests (Phase 4.5)
=======================================
Comprehensive tests for the governed closed-loop adaptive learning system.

Test coverage:
  1. Strategy scoring determinism
  2. Profile performance metric updates
  3. Knowledge curator lesson production
  4. Noisy lesson rejection (quarantine)
  5. Learning only influences allowed strategy fields
  6. Forbidden areas cannot be modified
  7. Telemetry events emit correctly
  8. Full pipeline: outcome → score → metrics → lessons → recommendation
"""

from __future__ import annotations

import math
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the backend source is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend" / "src"))

from apps.backend.src.core.praison_strategy_scoring import (
    StrategyOutcome,
    StrategyScore,
    score_strategy,
    _DEFAULT_WEIGHTS,
)
from apps.backend.src.core.praison_knowledge_base import (
    KnowledgeBase,
    KnowledgeLesson,
    VALID_LESSON_TYPES,
    _QUARANTINE_THRESHOLD,
)
from apps.backend.src.core.praison_profile_tracker import (
    ProfileMetrics,
    ProfileTracker,
    ProfileUpdateRecord,
)
from apps.backend.src.core.praison_strategy_learning import (
    StrategyLearner,
    StrategyRecommendation,
    LearningRejection,
    _ALLOWED_LEARNING_FIELDS,
    _FORBIDDEN_LEARNING_FIELDS,
    _LESSON_SCORE_THRESHOLD,
)
from apps.backend.src.core.praison_adaptive import (
    ExecutionStrategy,
    ExecutionPlanPatch,
    ToolProfile,
    PromptProfile,
    AdaptiveChangeType,
    validate_plan_patch,
)
from apps.backend.src.core.praison_execution_events import (
    EventBus,
    EventType,
    MissionEvent,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_storage(tmp_path):
    """Provide a temporary storage root for all learning subsystems."""
    return str(tmp_path)


@pytest.fixture
def knowledge_base(tmp_storage):
    return KnowledgeBase(storage_root=tmp_storage)


@pytest.fixture
def profile_tracker(tmp_storage):
    return ProfileTracker(storage_root=tmp_storage)


@pytest.fixture
def learner(knowledge_base, profile_tracker):
    return StrategyLearner(knowledge_base=knowledge_base, profile_tracker=profile_tracker)


@pytest.fixture
def good_outcome():
    """A high-performing outcome that should produce lessons."""
    return StrategyOutcome(
        mission_id="m-001",
        phase="recon",
        strategy_id="s-001",
        targets_in_scope=10,
        targets_covered=8,
        total_findings=20,
        unique_findings=15,
        high_confidence_findings=10,
        medium_confidence_findings=4,
        low_confidence_findings=1,
        false_positives=1,
        budgeted_seconds=3600.0,
        actual_seconds=2400.0,
        budgeted_tokens=100000,
        actual_tokens=60000,
        tool_invocations=30,
        escalation_count=0,
        blocked_count=0,
        approval_count=1,
        artifacts_produced=10,
        high_value_artifacts=7,
        tool_profile_id="tp_balanced_recon",
        prompt_profile_id="pp_thorough_analysis",
    )


@pytest.fixture
def poor_outcome():
    """A poorly performing outcome."""
    return StrategyOutcome(
        mission_id="m-002",
        phase="scanning",
        strategy_id="s-002",
        targets_in_scope=10,
        targets_covered=2,
        total_findings=5,
        unique_findings=1,
        high_confidence_findings=0,
        medium_confidence_findings=1,
        low_confidence_findings=4,
        false_positives=3,
        budgeted_seconds=3600.0,
        actual_seconds=7000.0,
        budgeted_tokens=100000,
        actual_tokens=190000,
        tool_invocations=50,
        escalation_count=4,
        blocked_count=2,
        approval_count=0,
        artifacts_produced=3,
        high_value_artifacts=0,
    )


@pytest.fixture
def test_strategy():
    """An execution strategy for validation tests."""
    return ExecutionStrategy(
        strategy_id="strat-test",
        mission_id="m-test",
        phase_id="recon",
        tool_candidates=("subfinder", "httpx", "nuclei"),
        tool_order=("subfinder", "httpx", "nuclei"),
        allowed_parameter_profiles=(
            ToolProfile(profile_id="tp_passive_recon", tool_id="subfinder",
                        profile_name="passive_recon"),
            ToolProfile(profile_id="tp_balanced_recon", tool_id="httpx",
                        profile_name="balanced_recon"),
        ),
        allowed_prompt_profiles=(
            PromptProfile(profile_id="pp_thorough_analysis",
                          profile_name="thorough_analysis", template="test"),
            PromptProfile(profile_id="pp_fast_triage",
                          profile_name="fast_triage", template="test"),
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Strategy Scoring Determinism
# ═══════════════════════════════════════════════════════════════════════════════


class TestScoringDeterminism:
    """Same inputs always produce identical scores."""

    def test_same_outcome_same_score(self, good_outcome):
        s1 = score_strategy(good_outcome)
        s2 = score_strategy(good_outcome)
        assert s1.composite_score == s2.composite_score
        assert s1.coverage_score == s2.coverage_score
        assert s1.confidence_score == s2.confidence_score

    def test_score_in_unit_range(self, good_outcome):
        score = score_strategy(good_outcome)
        for attr in ("composite_score", "coverage_score", "confidence_score",
                      "unique_findings_score", "time_efficiency_score",
                      "cost_efficiency_score", "false_positive_score",
                      "escalation_score", "blocked_score", "signal_value_score"):
            val = getattr(score, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} out of range"

    def test_perfect_outcome_high_score(self):
        perfect = StrategyOutcome(
            mission_id="m-perfect",
            phase="recon",
            targets_in_scope=10,
            targets_covered=10,
            total_findings=10,
            unique_findings=10,
            high_confidence_findings=10,
            medium_confidence_findings=0,
            low_confidence_findings=0,
            false_positives=0,
            budgeted_seconds=3600.0,
            actual_seconds=1800.0,
            budgeted_tokens=100000,
            actual_tokens=50000,
            escalation_count=0,
            blocked_count=0,
            artifacts_produced=10,
            high_value_artifacts=10,
        )
        score = score_strategy(perfect)
        assert score.composite_score >= 0.9

    def test_poor_outcome_low_score(self, poor_outcome):
        score = score_strategy(poor_outcome)
        assert score.composite_score < 0.5

    def test_zero_outcome_baseline_score(self):
        """Empty outcome still gets credit for no escalations/blocks/FPs and being under budget."""
        empty = StrategyOutcome()
        score = score_strategy(empty)
        # time_efficiency=1.0, cost_efficiency=1.0, fp=1.0, escalation=1.0, blocked=1.0
        # weighted: 0.10 + 0.05 + 0.10 + 0.05 + 0.05 = 0.35
        assert abs(score.composite_score - 0.35) < 1e-9

    def test_weights_sum_to_one(self):
        total = sum(_DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_custom_weights(self, good_outcome):
        # All weight on coverage
        w = {k: 0.0 for k in _DEFAULT_WEIGHTS}
        w["coverage"] = 1.0
        score = score_strategy(good_outcome, weights=w)
        assert abs(score.composite_score - score.coverage_score) < 1e-9

    def test_coverage_score_formula(self):
        o = StrategyOutcome(targets_in_scope=10, targets_covered=7)
        score = score_strategy(o)
        assert abs(score.coverage_score - 0.7) < 1e-9

    def test_unique_findings_sigmoid(self):
        o5 = StrategyOutcome(unique_findings=5)
        o20 = StrategyOutcome(unique_findings=20)
        s5 = score_strategy(o5).unique_findings_score
        s20 = score_strategy(o20).unique_findings_score
        assert s20 > s5  # diminishing returns but still higher
        assert abs(s5 - (1.0 - math.exp(-0.15 * 5))) < 1e-9

    def test_time_efficiency_under_budget(self):
        o = StrategyOutcome(budgeted_seconds=3600, actual_seconds=1800)
        assert score_strategy(o).time_efficiency_score == 1.0

    def test_time_efficiency_double_budget(self):
        o = StrategyOutcome(budgeted_seconds=3600, actual_seconds=7200)
        assert score_strategy(o).time_efficiency_score == 0.0

    def test_escalation_penalty(self):
        o0 = StrategyOutcome(escalation_count=0)
        o5 = StrategyOutcome(escalation_count=5)
        assert score_strategy(o0).escalation_score == 1.0
        assert score_strategy(o5).escalation_score == 0.0

    def test_thread_safety(self, good_outcome):
        """Concurrent scoring should produce deterministic results."""
        results = []

        def score_it():
            results.append(score_strategy(good_outcome).composite_score)

        threads = [threading.Thread(target=score_it) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(r == results[0] for r in results)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Profile Performance Metric Updates
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfileTracker:
    """Profile tracker accumulates metrics correctly."""

    def test_first_execution(self, profile_tracker, good_outcome):
        score = score_strategy(good_outcome)
        metrics = profile_tracker.record_execution(
            profile_id="tp_test",
            profile_type="tool",
            profile_name="test_profile",
            score=score,
            success=True,
            actual_seconds=2400.0,
            false_positives=1,
            total_findings=20,
        )
        assert metrics.executions == 1
        assert metrics.successes == 1
        assert metrics.total_score == score.composite_score
        assert metrics.success_rate == 1.0

    def test_multiple_executions_accumulate(self, profile_tracker, good_outcome, poor_outcome):
        s1 = score_strategy(good_outcome)
        s2 = score_strategy(poor_outcome)
        profile_tracker.record_execution(
            profile_id="tp_multi", profile_type="tool", profile_name="multi",
            score=s1, success=True, actual_seconds=100,
        )
        metrics = profile_tracker.record_execution(
            profile_id="tp_multi", profile_type="tool", profile_name="multi",
            score=s2, success=False, actual_seconds=200,
        )
        assert metrics.executions == 2
        assert metrics.successes == 1
        assert metrics.success_rate == 0.5
        assert abs(metrics.total_score - (s1.composite_score + s2.composite_score)) < 1e-9

    def test_get_metrics_returns_none_for_unknown(self, profile_tracker):
        assert profile_tracker.get_metrics("nonexistent") is None

    def test_get_all_metrics_filter(self, profile_tracker, good_outcome):
        score = score_strategy(good_outcome)
        profile_tracker.record_execution(
            profile_id="tp_tool1", profile_type="tool", profile_name="tool1", score=score,
        )
        profile_tracker.record_execution(
            profile_id="pp_prompt1", profile_type="prompt", profile_name="prompt1", score=score,
        )
        tool_metrics = profile_tracker.get_all_metrics(profile_type="tool")
        prompt_metrics = profile_tracker.get_all_metrics(profile_type="prompt")
        assert len(tool_metrics) == 1
        assert len(prompt_metrics) == 1

    def test_rank_profiles_by_score(self, profile_tracker, good_outcome, poor_outcome):
        sg = score_strategy(good_outcome)
        sp = score_strategy(poor_outcome)
        for _ in range(3):
            profile_tracker.record_execution(
                profile_id="tp_good", profile_type="tool", profile_name="good", score=sg,
            )
            profile_tracker.record_execution(
                profile_id="tp_bad", profile_type="tool", profile_name="bad", score=sp,
            )
        ranked = profile_tracker.rank_profiles("tool", metric="avg_score", min_executions=3)
        assert len(ranked) == 2
        assert ranked[0].profile_id == "tp_good"

    def test_best_profile(self, profile_tracker, good_outcome, poor_outcome):
        sg = score_strategy(good_outcome)
        sp = score_strategy(poor_outcome)
        for _ in range(3):
            profile_tracker.record_execution(
                profile_id="tp_a", profile_type="tool", profile_name="a", score=sg,
            )
            profile_tracker.record_execution(
                profile_id="tp_b", profile_type="tool", profile_name="b", score=sp,
            )
        best = profile_tracker.best_profile(["tp_a", "tp_b"], metric="avg_score", min_executions=3)
        assert best == "tp_a"

    def test_best_profile_insufficient_data(self, profile_tracker, good_outcome):
        score = score_strategy(good_outcome)
        profile_tracker.record_execution(
            profile_id="tp_single", profile_type="tool", profile_name="single", score=score,
        )
        # Only 1 execution, need 3
        best = profile_tracker.best_profile(["tp_single"], min_executions=3)
        assert best is None

    def test_fp_rate_lower_is_better(self, profile_tracker):
        """When ranking by fp_rate, lower is better."""
        s = score_strategy(StrategyOutcome(
            targets_in_scope=10, targets_covered=10,
            total_findings=10, unique_findings=10,
            high_confidence_findings=10, artifacts_produced=10, high_value_artifacts=10,
        ))
        profile_tracker.record_execution(
            profile_id="tp_lowfp", profile_type="tool", profile_name="lowfp",
            score=s, false_positives=0, total_findings=10,
        )
        profile_tracker.record_execution(
            profile_id="tp_lowfp", profile_type="tool", profile_name="lowfp",
            score=s, false_positives=0, total_findings=10,
        )
        profile_tracker.record_execution(
            profile_id="tp_lowfp", profile_type="tool", profile_name="lowfp",
            score=s, false_positives=0, total_findings=10,
        )
        profile_tracker.record_execution(
            profile_id="tp_highfp", profile_type="tool", profile_name="highfp",
            score=s, false_positives=5, total_findings=10,
        )
        profile_tracker.record_execution(
            profile_id="tp_highfp", profile_type="tool", profile_name="highfp",
            score=s, false_positives=5, total_findings=10,
        )
        profile_tracker.record_execution(
            profile_id="tp_highfp", profile_type="tool", profile_name="highfp",
            score=s, false_positives=5, total_findings=10,
        )
        best = profile_tracker.best_profile(
            ["tp_lowfp", "tp_highfp"], metric="fp_rate", min_executions=3,
        )
        assert best == "tp_lowfp"

    def test_profile_metrics_to_dict(self):
        m = ProfileMetrics(
            profile_id="tp_x", profile_type="tool", profile_name="x",
            executions=10, successes=8, total_score=7.5, total_signal=6.0,
            total_time=1000.0, total_fp=2, total_findings=50,
        )
        d = m.to_dict()
        assert d["success_rate"] == 0.8
        assert d["avg_score"] == 0.75
        assert d["fp_rate"] == 0.04

    def test_persistence_creates_file(self, profile_tracker, tmp_storage, good_outcome):
        score = score_strategy(good_outcome)
        profile_tracker.record_execution(
            profile_id="tp_persist", profile_type="tool", profile_name="persist", score=score,
        )
        metrics_file = Path(tmp_storage) / "knowledge" / "profile_metrics.jsonl"
        assert metrics_file.exists()
        lines = metrics_file.read_text().strip().split("\n")
        assert len(lines) == 1

    def test_invalid_ranking_metric(self, profile_tracker):
        with pytest.raises(ValueError, match="Invalid ranking metric"):
            profile_tracker.rank_profiles("tool", metric="nonexistent")

    def test_thread_safety(self, profile_tracker, good_outcome):
        score = score_strategy(good_outcome)
        errors = []

        def record_many():
            try:
                for _ in range(10):
                    profile_tracker.record_execution(
                        profile_id="tp_threaded", profile_type="tool",
                        profile_name="threaded", score=score,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        m = profile_tracker.get_metrics("tp_threaded")
        assert m.executions == 50


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Knowledge Curator — Lesson Production
# ═══════════════════════════════════════════════════════════════════════════════


class TestKnowledgeLessonProduction:
    """High-signal outcomes should produce knowledge lessons."""

    def test_high_score_produces_lessons(self, learner, knowledge_base, good_outcome):
        score = learner.process_outcome(
            good_outcome,
            tool_profile_id="tp_balanced_recon",
            prompt_profile_id="pp_thorough_analysis",
            agent_id="test_agent",
        )
        assert score.composite_score >= _LESSON_SCORE_THRESHOLD
        # Should have produced at least one lesson
        lessons = knowledge_base.get_lessons()
        assert len(lessons) >= 1

    def test_tool_order_lesson_produced(self, learner, knowledge_base, good_outcome):
        learner.process_outcome(
            good_outcome, tool_profile_id="tp_balanced_recon",
        )
        lessons = knowledge_base.get_lessons(lesson_type="tool_order_lesson")
        assert len(lessons) >= 1
        lesson = lessons[0]
        assert lesson.content["tool_profile_id"] == "tp_balanced_recon"

    def test_prompt_effectiveness_lesson(self, learner, knowledge_base, good_outcome):
        learner.process_outcome(
            good_outcome, prompt_profile_id="pp_thorough_analysis",
        )
        lessons = knowledge_base.get_lessons(lesson_type="prompt_effectiveness")
        assert len(lessons) >= 1

    def test_fp_indicator_lesson(self, learner, knowledge_base, good_outcome):
        learner.process_outcome(
            good_outcome, tool_profile_id="tp_balanced_recon",
        )
        lessons = knowledge_base.get_lessons(lesson_type="false_positive_indicator")
        assert len(lessons) >= 1

    def test_low_score_no_lessons(self, learner, knowledge_base, poor_outcome):
        score = learner.process_outcome(poor_outcome)
        assert score.composite_score < _LESSON_SCORE_THRESHOLD
        lessons = knowledge_base.get_lessons()
        assert len(lessons) == 0

    def test_lesson_has_provenance(self, learner, knowledge_base, good_outcome):
        learner.process_outcome(
            good_outcome,
            tool_profile_id="tp_balanced_recon",
            agent_id="agent-x",
            workflow_id="wf-001",
            program_id="prog-001",
        )
        lessons = knowledge_base.get_lessons()
        assert len(lessons) >= 1
        lesson = lessons[0]
        assert lesson.mission_id == "m-001"
        assert lesson.agent_id == "agent-x"
        assert lesson.strategy_id == "s-001"

    def test_valid_lesson_types(self):
        """All lesson types should be well-defined."""
        assert len(VALID_LESSON_TYPES) == 6
        expected = {
            "tool_order_lesson", "prompt_effectiveness", "exploit_pattern",
            "false_positive_indicator", "evidence_heuristic", "triage_pattern",
        }
        assert VALID_LESSON_TYPES == expected


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Noisy Lesson Rejection (Quarantine)
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuarantine:
    """Low-confidence lessons are quarantined, not applied."""

    def test_low_confidence_quarantined(self, knowledge_base):
        lesson = KnowledgeLesson(
            lesson_type="tool_order_lesson",
            confidence=0.3,
            summary="Low confidence lesson",
            mission_id="m-q1",
        )
        result = knowledge_base.add_lesson(lesson)
        assert result.quarantined is True
        assert knowledge_base.lesson_count() == 0
        assert knowledge_base.quarantine_count() == 1

    def test_at_threshold_not_quarantined(self, knowledge_base):
        lesson = KnowledgeLesson(
            lesson_type="tool_order_lesson",
            confidence=_QUARANTINE_THRESHOLD,
            summary="At threshold lesson",
        )
        result = knowledge_base.add_lesson(lesson)
        assert result.quarantined is False
        assert knowledge_base.lesson_count() == 1

    def test_high_confidence_active(self, knowledge_base):
        lesson = KnowledgeLesson(
            lesson_type="exploit_pattern",
            confidence=0.9,
            summary="High confidence exploit pattern",
        )
        result = knowledge_base.add_lesson(lesson)
        assert result.quarantined is False
        assert knowledge_base.lesson_count() == 1

    def test_invalid_lesson_type_rejected(self, knowledge_base):
        lesson = KnowledgeLesson(
            lesson_type="invalid_type",
            confidence=0.9,
            summary="Invalid type",
        )
        with pytest.raises(ValueError, match="Invalid lesson_type"):
            knowledge_base.add_lesson(lesson)

    def test_empty_summary_rejected(self, knowledge_base):
        lesson = KnowledgeLesson(
            lesson_type="tool_order_lesson",
            confidence=0.9,
            summary="",
        )
        with pytest.raises(ValueError, match="summary must not be empty"):
            knowledge_base.add_lesson(lesson)

    def test_out_of_range_confidence_rejected(self, knowledge_base):
        lesson = KnowledgeLesson(
            lesson_type="tool_order_lesson",
            confidence=1.5,
            summary="Bad confidence",
        )
        with pytest.raises(ValueError, match="Confidence must be in"):
            knowledge_base.add_lesson(lesson)

    def test_promote_quarantined_to_active(self, knowledge_base):
        lesson = KnowledgeLesson(
            lesson_type="tool_order_lesson",
            confidence=0.3,
            summary="Quarantined then promoted",
        )
        q = knowledge_base.add_lesson(lesson)
        assert q.quarantined is True
        promoted = knowledge_base.promote_lesson(q.lesson_id)
        assert promoted is not None
        assert promoted.quarantined is False
        assert knowledge_base.lesson_count() == 1
        assert knowledge_base.quarantine_count() == 0

    def test_promote_nonexistent_returns_none(self, knowledge_base):
        assert knowledge_base.promote_lesson("nonexistent") is None

    def test_quarantine_persisted_to_separate_file(self, knowledge_base, tmp_storage):
        lesson = KnowledgeLesson(
            lesson_type="tool_order_lesson",
            confidence=0.2,
            summary="Will be quarantined",
        )
        knowledge_base.add_lesson(lesson)
        q_path = Path(tmp_storage) / "knowledge" / "quarantine.jsonl"
        assert q_path.exists()
        lines = q_path.read_text().strip().split("\n")
        assert len(lines) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Learning Influences Only Allowed Fields
# ═══════════════════════════════════════════════════════════════════════════════


class TestLearningBoundaries:
    """Learning can only influence allowed strategy fields."""

    def test_allowed_fields_are_defined(self):
        assert "tool_order" in _ALLOWED_LEARNING_FIELDS
        assert "tool_profile_id" in _ALLOWED_LEARNING_FIELDS
        assert "prompt_profile_id" in _ALLOWED_LEARNING_FIELDS
        assert "retry_policy" in _ALLOWED_LEARNING_FIELDS
        assert "parallelism" in _ALLOWED_LEARNING_FIELDS
        assert "work_priority" in _ALLOWED_LEARNING_FIELDS

    def test_tool_profile_recommendation(self, learner, profile_tracker, good_outcome):
        score = score_strategy(good_outcome)
        for _ in range(5):
            profile_tracker.record_execution(
                profile_id="tp_a", profile_type="tool", profile_name="a", score=score,
            )
        rec = learner.recommend_tool_profile(["tp_a", "tp_b"])
        assert rec is not None
        assert rec.field == "tool_profile_id"
        assert rec.recommended_value == "tp_a"

    def test_prompt_profile_recommendation(self, learner, profile_tracker, good_outcome):
        score = score_strategy(good_outcome)
        for _ in range(5):
            profile_tracker.record_execution(
                profile_id="pp_x", profile_type="prompt", profile_name="x", score=score,
            )
        rec = learner.recommend_prompt_profile(["pp_x", "pp_y"])
        assert rec is not None
        assert rec.field == "prompt_profile_id"

    def test_tool_order_recommendation(self, learner, knowledge_base):
        # Add a high-confidence tool order lesson
        knowledge_base.add_lesson(KnowledgeLesson(
            lesson_type="tool_order_lesson",
            confidence=0.85,
            content={"tool_order": ["httpx", "subfinder", "nuclei"]},
            summary="Reordered tools for better coverage",
            phase="recon",
        ))
        rec = learner.recommend_tool_order(
            current_order=["subfinder", "httpx", "nuclei"],
            phase="recon",
        )
        assert rec is not None
        assert rec.field == "tool_order"
        assert rec.recommended_value == ["httpx", "subfinder", "nuclei"]

    def test_no_recommendation_without_data(self, learner):
        rec = learner.recommend_tool_profile(["tp_nonexistent"])
        assert rec is None

    def test_recommendation_validation_accepts_valid(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="tool_profile_id",
            recommended_value="tp_passive_recon",
            reason="Best performer",
            confidence=0.7,
            based_on_executions=10,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is None

    def test_recommendation_validation_through_governance(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="prompt_profile_id",
            recommended_value="thorough_analysis",
            reason="Best performer",
            confidence=0.7,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is None  # thorough_analysis is in allowed prompt profiles


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Forbidden Areas Cannot Be Modified
# ═══════════════════════════════════════════════════════════════════════════════


class TestForbiddenBoundaries:
    """Learning must not influence forbidden fields."""

    def test_forbidden_fields_are_defined(self):
        assert "scope" in _FORBIDDEN_LEARNING_FIELDS
        assert "targets" in _FORBIDDEN_LEARNING_FIELDS
        assert "governance_rules" in _FORBIDDEN_LEARNING_FIELDS
        assert "approval_thresholds" in _FORBIDDEN_LEARNING_FIELDS
        assert "tool_allowlist" in _FORBIDDEN_LEARNING_FIELDS
        assert "graph_topology" in _FORBIDDEN_LEARNING_FIELDS
        assert "approval_bypass" in _FORBIDDEN_LEARNING_FIELDS

    def test_scope_modification_rejected(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="scope",
            recommended_value={"targets": ["evil.com"]},
            reason="Expand scope",
            confidence=0.99,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is not None
        assert rejection.boundary_type == "forbidden_field"
        assert "forbidden" in rejection.reason.lower()

    def test_governance_rules_rejected(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="governance_rules",
            recommended_value={"approval_required": False},
            reason="Speed up",
            confidence=0.95,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is not None
        assert rejection.boundary_type == "forbidden_field"

    def test_graph_topology_rejected(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="graph_topology",
            recommended_value={"add_node": "malicious_node"},
            reason="Optimize graph",
            confidence=0.99,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is not None
        assert rejection.boundary_type == "forbidden_field"

    def test_approval_bypass_rejected(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="approval_bypass",
            recommended_value=True,
            reason="Skip approvals",
            confidence=1.0,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is not None

    def test_all_forbidden_fields_rejected(self, learner, test_strategy):
        for forbidden_field in _FORBIDDEN_LEARNING_FIELDS:
            rec = StrategyRecommendation(
                field=forbidden_field,
                recommended_value="anything",
                reason="Test",
                confidence=0.99,
            )
            rejection = learner.validate_recommendation(rec, test_strategy)
            assert rejection is not None, f"Field '{forbidden_field}' was not rejected"
            assert rejection.boundary_type == "forbidden_field"

    def test_unknown_field_rejected(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="completely_unknown_field",
            recommended_value="something",
            reason="Test",
            confidence=0.9,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is not None
        assert rejection.boundary_type == "forbidden_field"

    def test_low_confidence_recommendation_rejected(self, learner, test_strategy):
        rec = StrategyRecommendation(
            field="tool_profile_id",
            recommended_value="tp_passive_recon",
            reason="Weak signal",
            confidence=0.1,  # below 0.3 threshold
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is not None
        assert rejection.boundary_type == "low_confidence"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Telemetry Events
# ═══════════════════════════════════════════════════════════════════════════════


class TestTelemetryEvents:
    """Learning actions emit correct telemetry events."""

    def test_phase_outcome_scored_event(self, learner, good_outcome):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))

        with patch("apps.backend.src.core.praison_strategy_learning.emit", bus.emit):
            with patch("apps.backend.src.core.praison_profile_tracker.emit", bus.emit):
                learner.process_outcome(good_outcome, tool_profile_id="tp_test")

        scored_events = [e for e in events if e.event_type == EventType.PHASE_OUTCOME_SCORED.value]
        assert len(scored_events) == 1
        assert scored_events[0].detail["score"] > 0

    def test_profile_score_updated_event(self, learner, good_outcome):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))

        with patch("apps.backend.src.core.praison_strategy_learning.emit", bus.emit):
            with patch("apps.backend.src.core.praison_profile_tracker.emit", bus.emit):
                learner.process_outcome(good_outcome, tool_profile_id="tp_test")

        profile_events = [e for e in events if e.event_type == EventType.PROFILE_SCORE_UPDATED.value]
        assert len(profile_events) >= 1

    def test_knowledge_lesson_event(self, learner, knowledge_base, good_outcome):
        events = []
        bus = EventBus()
        bus.subscribe(lambda e: events.append(e))

        with patch("apps.backend.src.core.praison_strategy_learning.emit", bus.emit):
            with patch("apps.backend.src.core.praison_profile_tracker.emit", bus.emit):
                with patch("apps.backend.src.core.praison_knowledge_base.emit", bus.emit):
                    learner.process_outcome(
                        good_outcome,
                        tool_profile_id="tp_balanced_recon",
                        prompt_profile_id="pp_thorough_analysis",
                    )

        lesson_events = [
            e for e in events
            if e.event_type == EventType.KNOWLEDGE_LESSON_CREATED.value
        ]
        assert len(lesson_events) >= 1

    def test_event_types_exist(self):
        """All learning event types should be defined."""
        assert hasattr(EventType, "STRATEGY_SELECTED")
        assert hasattr(EventType, "TOOL_PROFILE_SELECTED")
        assert hasattr(EventType, "PROMPT_PROFILE_SELECTED")
        assert hasattr(EventType, "PHASE_OUTCOME_SCORED")
        assert hasattr(EventType, "KNOWLEDGE_LESSON_CREATED")
        assert hasattr(EventType, "KNOWLEDGE_LESSON_REJECTED")
        assert hasattr(EventType, "PROFILE_SCORE_UPDATED")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Full Pipeline Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """End-to-end: outcome → score → metrics → lessons → recommendation."""

    def test_full_learning_loop(self, learner, knowledge_base, profile_tracker, good_outcome):
        # Process multiple good outcomes to build up data
        for i in range(5):
            outcome = StrategyOutcome(
                mission_id=f"m-loop-{i}",
                phase="recon",
                strategy_id=f"s-loop-{i}",
                targets_in_scope=10,
                targets_covered=8,
                total_findings=20,
                unique_findings=15,
                high_confidence_findings=10,
                medium_confidence_findings=4,
                low_confidence_findings=1,
                false_positives=1,
                budgeted_seconds=3600.0,
                actual_seconds=2400.0,
                budgeted_tokens=100000,
                actual_tokens=60000,
                artifacts_produced=10,
                high_value_artifacts=7,
            )
            learner.process_outcome(
                outcome,
                tool_profile_id="tp_balanced_recon",
                prompt_profile_id="pp_thorough_analysis",
            )

        # Verify metrics accumulated
        tool_metrics = profile_tracker.get_metrics("tp_balanced_recon")
        assert tool_metrics is not None
        assert tool_metrics.executions == 5

        prompt_metrics = profile_tracker.get_metrics("pp_thorough_analysis")
        assert prompt_metrics is not None
        assert prompt_metrics.executions == 5

        # Verify knowledge lessons produced
        lessons = knowledge_base.get_lessons()
        assert len(lessons) >= 1

        # Now get recommendations
        rec = learner.recommend_tool_profile(["tp_balanced_recon", "tp_high_recall"])
        assert rec is not None
        assert rec.recommended_value == "tp_balanced_recon"
        assert rec.confidence > 0

    def test_apply_recommendations_mixed(self, learner, test_strategy):
        good_rec = StrategyRecommendation(
            field="tool_profile_id",
            recommended_value="tp_passive_recon",
            reason="Best performer",
            confidence=0.8,
        )
        bad_rec = StrategyRecommendation(
            field="scope",
            recommended_value={"targets": ["evil.com"]},
            reason="Expand scope",
            confidence=0.99,
        )
        accepted, rejected = learner.apply_recommendations(
            [good_rec, bad_rec], test_strategy,
        )
        assert len(accepted) == 1
        assert len(rejected) == 1
        assert accepted[0].field == "tool_profile_id"
        assert rejected[0].boundary_type == "forbidden_field"

    def test_learning_summary(self, learner, good_outcome):
        learner.process_outcome(
            good_outcome,
            tool_profile_id="tp_test",
            prompt_profile_id="pp_test",
        )
        summary = learner.get_learning_summary()
        assert summary["tool_profiles_tracked"] >= 1
        assert summary["prompt_profiles_tracked"] >= 1
        assert isinstance(summary["knowledge_lessons"], int)
        assert isinstance(summary["quarantined_lessons"], int)

    def test_poor_outcomes_do_not_pollute(self, learner, knowledge_base, profile_tracker):
        """Multiple poor outcomes should not produce knowledge lessons."""
        for i in range(10):
            outcome = StrategyOutcome(
                mission_id=f"m-bad-{i}",
                phase="scanning",
                targets_in_scope=10,
                targets_covered=1,
                total_findings=2,
                unique_findings=0,
                false_positives=2,
                budgeted_seconds=3600,
                actual_seconds=7200,
                budgeted_tokens=100000,
                actual_tokens=200000,
                escalation_count=5,
                blocked_count=3,
                artifacts_produced=1,
                high_value_artifacts=0,
            )
            learner.process_outcome(outcome, tool_profile_id="tp_bad")

        # No knowledge lessons should be produced from poor outcomes
        assert knowledge_base.lesson_count() == 0

        # But metrics should still be tracked
        m = profile_tracker.get_metrics("tp_bad")
        assert m is not None
        assert m.executions == 10
        assert m.avg_score < 0.5

    def test_concurrent_learning_pipeline(self, learner, good_outcome):
        """Concurrent outcome processing should be thread-safe."""
        errors = []

        def process():
            try:
                learner.process_outcome(
                    good_outcome,
                    tool_profile_id="tp_concurrent",
                    prompt_profile_id="pp_concurrent",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=process) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_governance_integration(self, learner, test_strategy):
        """Recommendations validated through governance still work correctly."""
        # Unapproved profile should be rejected by governance
        rec = StrategyRecommendation(
            field="tool_profile_id",
            recommended_value="tp_nonexistent_profile",
            reason="Test governance rejection",
            confidence=0.8,
        )
        rejection = learner.validate_recommendation(rec, test_strategy)
        assert rejection is not None
        assert rejection.boundary_type == "governance_rejected"
