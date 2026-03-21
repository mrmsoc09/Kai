from __future__ import annotations

import json

from apps.backend.src.core.decision_engine.decision_policy import (
    DecisionAction,
    DecisionContext,
    DecisionPolicy,
)
from apps.backend.src.core.decision_engine.decision_trace import DecisionTraceRecorder
from apps.backend.src.core.decision_engine.hypothesis_engine import HypothesisEngine
from apps.backend.src.core.decision_engine.opportunity_reasoner import (
    OpportunityReasoner,
    OpportunitySignal,
)
from apps.backend.src.core.praison_strategy_scoring import (
    StrategyOutcome,
    recommend_next_action_from_outcome,
)
from apps.backend.src.core.vulnerability_validation import (
    ValidationEvidence,
    ValidationResult,
    decide_validation_next_action,
)


def test_hypothesis_generation_from_findings_clusters_memory():
    engine = HypothesisEngine()
    hypotheses = engine.generate_hypotheses(
        findings=[
            {
                "finding_id": "f-sqli-1",
                "vuln_type": "sqli",
                "validated_vulnerability": True,
                "response_similarity": 0.9,
                "memory_match_strength": 0.8,
            },
            {
                "finding_id": "f-xss-1",
                "vuln_type": "xss",
                "validated_vulnerability": False,
                "response_similarity": 0.4,
                "memory_match_strength": 0.2,
            },
        ],
        clusters=[
            {
                "cluster_id": "c-sqli-1",
                "vuln_type": "sqli",
                "count": 3,
                "response_similarity": 0.85,
            }
        ],
        memory_hits=[
            {
                "memory_id": "m-sqli-1",
                "vuln_type": "sqli",
                "confirmed": True,
                "match_strength": 0.95,
            }
        ],
    )
    assert hypotheses
    assert hypotheses[0].vuln_type == "sqli"
    assert "f-sqli-1" in hypotheses[0].evidence_ids
    assert "c-sqli-1" in hypotheses[0].evidence_ids
    assert "m-sqli-1" in hypotheses[0].evidence_ids


def test_decision_policy_selects_exploit_for_validated_signal():
    decision = DecisionPolicy().decide(
        DecisionContext(
            top_confidence=0.88,
            noise_ratio=0.08,
            duplicate_risk=0.15,
            budget_remaining_ratio=0.8,
            time_remaining_ratio=0.8,
            has_validated_finding=True,
            hypothesis_count=2,
            opportunity_signal=0.4,
        )
    )
    assert decision.chosen_action == DecisionAction.EXPLOIT


def test_decision_policy_can_select_generate_opportunity():
    decision = DecisionPolicy().decide(
        DecisionContext(
            top_confidence=0.8,
            noise_ratio=0.15,
            duplicate_risk=0.1,
            budget_remaining_ratio=0.9,
            time_remaining_ratio=0.9,
            has_validated_finding=False,
            hypothesis_count=3,
            opportunity_signal=0.95,
        )
    )
    assert decision.chosen_action == DecisionAction.GENERATE_OPPORTUNITY


def test_opportunity_reasoner_triggers_reasoned_opportunity():
    reasoner = OpportunityReasoner()
    opportunities = reasoner.generate(
        [
            OpportunitySignal(
                source_memory_id="mem-1",
                source_pattern_id="sig-1",
                vuln_type="sqli",
                candidate_targets=["a.example.com", "b.example.com"],
                target_scores={"a.example.com": 0.9, "b.example.com": 0.8},
                pattern_signature_strength=0.9,
                repeated_findings=4,
                tech_stack_similarity=0.75,
                duplicate_risk=0.1,
            )
        ],
        min_confidence=0.5,
    )
    assert len(opportunities) == 1
    assert opportunities[0].status == "proposed"
    assert opportunities[0].estimated_yield > 0
    assert opportunities[0].confidence_score >= 0.5


def test_strategy_scoring_integration_recommends_action_and_writes_trace(tmp_path):
    recorder = DecisionTraceRecorder(path=tmp_path / "decision_trace.jsonl")
    decision = recommend_next_action_from_outcome(
        StrategyOutcome(
            mission_id="mission-1",
            strategy_id="strat-1",
            total_findings=10,
            false_positives=1,
            validated_vulnerabilities=4,
            budgeted_seconds=600.0,
            actual_seconds=150.0,
            budgeted_tokens=1000,
            actual_tokens=250,
        ),
        duplicate_risk=0.1,
        top_hypothesis_confidence=0.9,
        hypothesis_count=2,
        trace_recorder=recorder,
    )
    assert decision.chosen_action == DecisionAction.EXPLOIT
    rows = [json.loads(line) for line in (tmp_path / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["chosen_action"] == "exploit"


def test_vulnerability_pipeline_integration_selects_exploit():
    decision = decide_validation_next_action(
        ValidationResult(
            finding_id="finding-1",
            validated_vulnerability=True,
            confidence_score=0.8,
            validation_evidence=[
                ValidationEvidence(
                    check="sqli_error_pattern",
                    passed=True,
                    detail="SQLi pattern found",
                    confidence_contribution=0.6,
                )
            ],
        ),
        clusters=[{"cluster_id": "cluster-1", "vuln_type": "sqli", "count": 4}],
        memory_hits=[{"memory_id": "mem-1", "vuln_type": "sqli", "match_strength": 0.9, "confirmed": True}],
        duplicate_risk=0.1,
        budget_remaining_ratio=0.9,
        time_remaining_ratio=0.9,
    )
    assert decision.chosen_action == DecisionAction.EXPLOIT
