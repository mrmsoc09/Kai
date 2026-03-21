from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

from apps.backend.src.core.decision_engine.decision_policy import (
    DecisionAction,
    PolicyDecision,
)
from apps.backend.src.core.praison_node_executors import (
    make_evidence_analysis_executor,
    make_handoff_liaison_executor,
)
from apps.backend.src.core.praison_state import make_initial_state


def _base_state() -> dict:
    return dict(
        make_initial_state(
            tenant_id=uuid.uuid4(),
            workflow_id="wf-runtime-decision",
            program_id="api.example.com",
            mission_id="mission-runtime-decision",
            execution_mode="live",
        )
    )


def _read_traces(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_evidence_analysis_wires_validation_decision_and_trace(monkeypatch, tmp_path):
    trace_path = tmp_path / "decision_trace.jsonl"
    monkeypatch.setenv("K1_DECISION_TRACE_PATH", str(trace_path))

    def analysis_agent(_state):
        return {
            "findings": [
                {
                    "finding_id": "finding-1",
                    "vuln_type": "sqli",
                    "severity": "high",
                    "confidence_score": 0.92,
                    "validated": True,
                    "target": "api.example.com",
                }
            ]
        }

    executor = make_evidence_analysis_executor(analysis_agent)
    state = _base_state()
    state["runtime_metrics"] = {
        "budget_remaining_ratio": 0.9,
        "time_remaining_ratio": 0.9,
    }
    result = executor(state)

    assert result["decision_action"] in {
        "continue",
        "validate",
        "exploit",
        "pivot",
        "stop",
        "generate_opportunity",
    }
    assert any(
        isinstance(row, dict)
        and row.get("type") == "runtime_decision"
        and row.get("node_id") == "evidence_analysis"
        for row in result.get("policy_events", [])
    )
    rows = _read_traces(trace_path)
    assert rows
    assert rows[-1]["chosen_action"] == result["decision_action"]


def test_evidence_analysis_stop_prevents_wasteful_execution(monkeypatch, tmp_path):
    trace_path = tmp_path / "decision_trace.jsonl"
    monkeypatch.setenv("K1_DECISION_TRACE_PATH", str(trace_path))

    def analysis_agent(_state):
        return {
            "findings": [
                {
                    "finding_id": "finding-low",
                    "vuln_type": "xss",
                    "severity": "low",
                    "confidence_score": 0.2,
                    "validated": False,
                    "target": "api.example.com",
                    "false_positive": True,
                }
            ]
        }

    executor = make_evidence_analysis_executor(analysis_agent)
    state = _base_state()
    state["runtime_metrics"] = {
        "budget_remaining_ratio": 0.0,
        "time_remaining_ratio": 0.5,
    }
    result = executor(state)

    assert result["decision_action"] == "stop"
    assert result["completed"] is True
    assert str(result.get("error", "")).startswith("Decision engine stop:")


def test_generate_opportunity_branch_routes_to_opportunity_engine(monkeypatch, tmp_path):
    trace_path = tmp_path / "decision_trace.jsonl"
    monkeypatch.setenv("K1_DECISION_TRACE_PATH", str(trace_path))

    fake_decision = PolicyDecision(
        chosen_action=DecisionAction.GENERATE_OPPORTUNITY,
        reason_code="opportunity_signal_detected",
        score=0.88,
        rejected_alternatives=[],
    )
    decide_mock = MagicMock(return_value=fake_decision)
    monkeypatch.setattr(
        "apps.backend.src.core.praison_node_executors.decide_validation_next_action",
        decide_mock,
    )

    class _FakeOpportunity:
        def to_dict(self):
            return {
                "opportunity_id": "opp-runtime-1",
                "vuln_type": "sqli",
                "candidate_targets": ["api.example.com"],
            }

    class _FakeDetectionResult:
        opportunities = [_FakeOpportunity()]

    fake_engine = MagicMock()
    fake_engine.detect.return_value = _FakeDetectionResult()
    monkeypatch.setattr(
        "apps.backend.src.core.praison_node_executors.get_opportunity_engine",
        lambda: fake_engine,
    )
    monkeypatch.setattr(
        "apps.backend.src.core.praison_node_executors._extract_domains_from_findings",
        lambda findings, state: ["api.example.com"],
    )

    def analysis_agent(_state):
        return {
            "findings": [
                {
                    "finding_id": "finding-2",
                    "vuln_type": "sqli",
                    "severity": "high",
                    "confidence_score": 0.85,
                    "validated": False,
                    "target": "api.example.com",
                }
            ]
        }

    executor = make_evidence_analysis_executor(analysis_agent)
    result = executor(_base_state())

    assert decide_mock.called
    assert result["decision_action"] == "generate_opportunity"
    assert result["generated_opportunities"][0]["opportunity_id"] == "opp-runtime-1"
    assert fake_engine.detect.called


def test_handoff_wires_strategy_decision_and_records_trace(monkeypatch, tmp_path):
    trace_path = tmp_path / "decision_trace.jsonl"
    monkeypatch.setenv("K1_DECISION_TRACE_PATH", str(trace_path))

    fake_decision = PolicyDecision(
        chosen_action=DecisionAction.PIVOT,
        reason_code="high_noise_or_duplicate_pressure",
        score=0.73,
        rejected_alternatives=[],
    )
    strategy_mock = MagicMock(return_value=fake_decision)
    monkeypatch.setattr(
        "apps.backend.src.core.praison_node_executors.recommend_next_action_from_outcome",
        strategy_mock,
    )

    executor = make_handoff_liaison_executor()
    state = _base_state()
    state["findings"] = [
        {
            "finding_id": "f-1",
            "vuln_type": "xss",
            "severity": "medium",
            "confidence_score": 0.55,
            "target": "api.example.com",
        }
    ]
    result = executor(state)

    assert strategy_mock.called
    assert result["completed"] is True
    assert result["next_action_recommendation"]["chosen_action"] == "pivot"
    assert any(
        isinstance(row, dict)
        and row.get("node_id") == "handoff_liaison"
        and row.get("type") == "runtime_decision"
        for row in result.get("policy_events", [])
    )
    rows = _read_traces(trace_path)
    assert rows
    assert rows[-1]["chosen_action"] == "pivot"
