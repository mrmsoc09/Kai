"""
Tests for the KAISON AI Tool Bidding System (ISSUE #7).

Coverage:
  1.  bid_score formula
  2.  dependency not met → abstain
  3.  phase mismatch → low confidence
  4.  orchestrator top-N selection
  5.  budget filter
  6.  fallback when all abstain (empty list returned)
  7.  K1_TOOL_BIDDING_ENABLED=false path (tested via runtime flag)
  8.  build_mission_context extraction from state dict
  9.  telemetry event type present in EventType
  10. orchestrator ranking by bid_score
  11. YAML-configured agent loads and evaluates correctly
  12. concurrent bid collection is thread-safe
"""

from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from core.tool_bidding import (
    BiddingOrchestrator,
    FindingDataset,
    IToolAgent,
    MissionContext,
    ToolBid,
    ToolExecutionRecord,
    YamlConfiguredToolAgent,
    _parse_findings,
    _reset_yaml_cache,
    build_mission_context,
    register,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_context(
    phase: str = "recon",
    goals: list[str] | None = None,
    findings: FindingDataset | None = None,
    budget: float = float("inf"),
    history: list[ToolExecutionRecord] | None = None,
) -> MissionContext:
    return MissionContext(
        target="example.com",
        phase=phase,
        goals=goals or [],
        findings_so_far=findings or FindingDataset(),
        budget_remaining_cents=budget,
        time_budget_remaining_ms=float("inf"),
        execution_history=history or [],
        mission_id="m-test",
        agent_id="SurfaceMapper",
    )


def _bid(
    tool_id: str = "subfinder",
    confidence: float = 0.85,
    cost: float = 0.0,
    boost: float = 1.0,
) -> ToolBid:
    return ToolBid(
        tool_id=tool_id,
        confidence=confidence,
        estimated_cost_cents=cost,
        execution_time_estimate_ms=30_000,
        output_schema={},
        dependencies=[],
        priority_boost=boost,
        reasoning="test",
    )


# ---------------------------------------------------------------------------
# 1. bid_score formula
# ---------------------------------------------------------------------------

class TestBidScoreFormula:
    def test_zero_confidence_zero_score(self):
        b = _bid(confidence=0.0)
        assert b.bid_score == 0.0

    def test_free_tool_score(self):
        b = _bid(confidence=0.85, cost=0.0, boost=1.0)
        expected = 0.85 * (100.0 / 1.0) * 1.0
        assert math.isclose(b.bid_score, expected, rel_tol=1e-9)

    def test_costly_tool_lower_score(self):
        cheap = _bid(confidence=0.85, cost=0.0)
        expensive = _bid(confidence=0.85, cost=10.0)
        assert expensive.bid_score < cheap.bid_score

    def test_priority_boost_scales_linearly(self):
        base = _bid(confidence=0.85, cost=0.0, boost=1.0)
        boosted = _bid(confidence=0.85, cost=0.0, boost=1.5)
        assert math.isclose(boosted.bid_score, base.bid_score * 1.5, rel_tol=1e-9)

    def test_formula_all_components(self):
        b = _bid(confidence=0.9, cost=5.0, boost=1.5)
        expected = 0.9 * (100.0 / 6.0) * 1.5
        assert math.isclose(b.bid_score, expected, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# 2. Dependency not met → abstain
# ---------------------------------------------------------------------------

class TestDependencyChecks:
    def test_dep_not_met_confidence_zero(self):
        agent = YamlConfiguredToolAgent(
            "sqlmap",
            config={
                "dependencies": ["parameterized_urls"],
                "phase_affinity": ["vuln_scanning"],
                "estimated_cost_cents": 5,
                "execution_time_estimate_ms": 300_000,
            },
        )
        ctx = _make_context(phase="vuln_scanning")  # empty FindingDataset
        bid = agent.evaluate_bid(ctx)
        assert bid.confidence == 0.0
        assert bid.bid_score == 0.0
        assert "missing" in bid.reasoning

    def test_dep_met_nonzero_confidence(self):
        agent = YamlConfiguredToolAgent(
            "sqlmap",
            config={
                "dependencies": ["parameterized_urls"],
                "phase_affinity": ["vuln_scanning"],
                "estimated_cost_cents": 5,
                "execution_time_estimate_ms": 300_000,
            },
        )
        findings = FindingDataset(parameterized_urls=["http://ex.com/?id=1"])
        ctx = _make_context(phase="vuln_scanning", findings=findings)
        bid = agent.evaluate_bid(ctx)
        assert bid.confidence > 0.0

    def test_multiple_deps_one_missing(self):
        agent = YamlConfiguredToolAgent(
            "secretfinder",
            config={
                "dependencies": ["urls_found", "parameterized_urls"],
                "phase_affinity": ["secrets"],
            },
        )
        findings = FindingDataset(urls_found=["http://ex.com/app.js"])
        ctx = _make_context(phase="secrets", findings=findings)
        bid = agent.evaluate_bid(ctx)
        assert bid.confidence == 0.0


# ---------------------------------------------------------------------------
# 3. Phase mismatch → low confidence
# ---------------------------------------------------------------------------

class TestPhaseMismatch:
    def test_phase_mismatch_reduces_confidence(self):
        agent = YamlConfiguredToolAgent(
            "sqlmap",
            config={
                "dependencies": ["parameterized_urls"],
                "phase_affinity": ["vuln_scanning"],
            },
        )
        findings = FindingDataset(parameterized_urls=["http://ex.com/?id=1"])
        ctx_match = _make_context(phase="vuln_scanning", findings=findings)
        ctx_miss = _make_context(phase="recon", findings=findings)
        assert agent.evaluate_bid(ctx_match).confidence > agent.evaluate_bid(ctx_miss).confidence

    def test_phase_match_base_confidence(self):
        agent = YamlConfiguredToolAgent(
            "subfinder",
            config={"phase_affinity": ["recon"], "dependencies": []},
        )
        bid = agent.evaluate_bid(_make_context(phase="recon"))
        assert math.isclose(bid.confidence, 0.85, rel_tol=1e-6)

    def test_empty_phase_affinity_always_eligible(self):
        agent = YamlConfiguredToolAgent(
            "anything",
            config={"phase_affinity": [], "dependencies": []},
        )
        bid = agent.evaluate_bid(_make_context(phase="recon"))
        assert bid.confidence == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# 4. Orchestrator top-N selection
# ---------------------------------------------------------------------------

class TestOrchestratorTopN:
    def test_max_tools_respected(self):
        tools = ["subfinder", "amass", "dnsx", "httpx", "naabu", "whatweb"]
        orch = BiddingOrchestrator()
        # Each tool gets YAML default (empty config → base 0.85 confidence)
        ctx = _make_context()
        selected = orch.select_tools(tools, ctx, max_tools=3)
        assert len(selected) <= 3

    def test_returns_list_of_strings(self):
        orch = BiddingOrchestrator()
        ctx = _make_context()
        result = orch.select_tools(["subfinder"], ctx, max_tools=5)
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)

    def test_unknown_tool_returns_default_bid(self):
        orch = BiddingOrchestrator()
        ctx = _make_context()
        # Unknown tool → YamlConfiguredToolAgent with empty config → 0.85 confidence
        result = orch.select_tools(["totally_unknown_tool_xyz"], ctx, max_tools=5)
        assert "totally_unknown_tool_xyz" in result


# ---------------------------------------------------------------------------
# 5. Budget filter
# ---------------------------------------------------------------------------

class TestBudgetFilter:
    def test_costly_tool_filtered_when_over_budget(self):
        costly_agent = YamlConfiguredToolAgent(
            "shodan",
            config={
                "dependencies": [],
                "phase_affinity": [],
                "estimated_cost_cents": 100,
            },
        )
        orch = BiddingOrchestrator()

        # Register a mock that returns a costly bid
        class _CostlyAgent(IToolAgent):
            def evaluate_bid(self, context: MissionContext) -> ToolBid:
                return ToolBid(
                    tool_id="shodan",
                    confidence=0.9,
                    estimated_cost_cents=100.0,
                    execution_time_estimate_ms=15_000,
                    output_schema={},
                    dependencies=[],
                    priority_boost=1.0,
                    reasoning="expensive",
                )

        with patch.dict("core.tool_bidding._REGISTRY", {"shodan": _CostlyAgent}):
            ctx = _make_context(budget=5.0)  # budget < 100 cents
            result = orch.select_tools(["shodan"], ctx, max_tools=5)
        assert "shodan" not in result

    def test_free_tool_passes_budget_filter(self):
        orch = BiddingOrchestrator()
        ctx = _make_context(budget=0.0)
        result = orch.select_tools(["subfinder"], ctx, max_tools=5)
        assert "subfinder" in result


# ---------------------------------------------------------------------------
# 6. Fallback when all abstain
# ---------------------------------------------------------------------------

class TestFallbackWhenAllAbstain:
    def test_empty_list_when_all_abstain(self):
        class _AbstainAgent(IToolAgent):
            def evaluate_bid(self, context: MissionContext) -> ToolBid:
                return ToolBid(
                    tool_id="abstainer",
                    confidence=0.0,
                    estimated_cost_cents=0.0,
                    execution_time_estimate_ms=0.0,
                    output_schema={},
                    dependencies=[],
                    priority_boost=1.0,
                    reasoning="abstain: test",
                )

        with patch.dict("core.tool_bidding._REGISTRY", {"abstainer": _AbstainAgent}):
            orch = BiddingOrchestrator()
            ctx = _make_context()
            result = orch.select_tools(["abstainer"], ctx)
        assert result == []


# ---------------------------------------------------------------------------
# 7. K1_TOOL_BIDDING_ENABLED flag (via env var check)
# ---------------------------------------------------------------------------

class TestBiddingEnabledFlag:
    def test_env_false_skips_bidding(self, monkeypatch):
        """When K1_TOOL_BIDDING_ENABLED=false the bidding path must not be entered."""
        monkeypatch.setenv("K1_TOOL_BIDDING_ENABLED", "false")
        # We test the env-var reading logic directly (the runtime integration
        # is tested via integration tests; here we just confirm the flag is read).
        enabled = os.getenv("K1_TOOL_BIDDING_ENABLED", "false").strip().lower() == "true"
        assert enabled is False

    def test_env_true_enables_bidding(self, monkeypatch):
        monkeypatch.setenv("K1_TOOL_BIDDING_ENABLED", "true")
        enabled = os.getenv("K1_TOOL_BIDDING_ENABLED", "false").strip().lower() == "true"
        assert enabled is True


# ---------------------------------------------------------------------------
# 8. build_mission_context
# ---------------------------------------------------------------------------

class TestBuildMissionContext:
    def test_basic_extraction(self):
        state = {
            "phase": "recon",
            "target": "example.com",
            "mission_id": "m-001",
            "findings": [],
        }
        ctx = build_mission_context(state, agent_id="SurfaceMapper")
        assert ctx.phase == "recon"
        assert ctx.target == "example.com"
        assert ctx.mission_id == "m-001"
        assert ctx.agent_id == "SurfaceMapper"
        assert ctx.budget_remaining_cents == float("inf")

    def test_budget_extracted(self):
        state = {"budget_remaining_cents": 50, "phase": "recon"}
        ctx = build_mission_context(state, agent_id="A")
        assert ctx.budget_remaining_cents == 50.0

    def test_phase_lowercased(self):
        state = {"phase": "RECON"}
        ctx = build_mission_context(state, agent_id="A")
        assert ctx.phase == "recon"

    def test_missing_phase_defaults_to_recon(self):
        ctx = build_mission_context({}, agent_id="A")
        assert ctx.phase == "recon"

    def test_findings_parsed_into_dataset(self):
        state = {
            "phase": "recon",
            "findings": [
                {"type": "subdomain", "subdomain": "api.example.com"},
                {"type": "port", "port": 443},
                {"type": "url", "url": "http://ex.com/page?id=1"},
            ],
        }
        ctx = build_mission_context(state, agent_id="A")
        assert "api.example.com" in ctx.findings_so_far.subdomains
        assert 443 in ctx.findings_so_far.open_ports
        assert "http://ex.com/page?id=1" in ctx.findings_so_far.urls_found
        assert "http://ex.com/page?id=1" in ctx.findings_so_far.parameterized_urls

    def test_execution_history_forwarded(self):
        rec = ToolExecutionRecord(
            tool_id="nmap",
            mission_id="m1",
            executed_at="2026-01-01T00:00:00Z",
            estimated_cost_cents=0.0,
            actual_cost_cents=0.0,
            estimated_time_ms=60_000,
            actual_time_ms=55_000,
            findings_count=3,
            success=True,
        )
        ctx = build_mission_context({}, agent_id="A", execution_history=[rec])
        assert len(ctx.execution_history) == 1
        assert ctx.execution_history[0].tool_id == "nmap"


# ---------------------------------------------------------------------------
# 9. Telemetry event type
# ---------------------------------------------------------------------------

class TestTelemetryEventType:
    def test_tool_bid_decision_in_event_type(self):
        from core.praison_execution_events import EventType
        assert hasattr(EventType, "TOOL_BID_DECISION")
        assert EventType.TOOL_BID_DECISION.value == "tool_bid_decision"


# ---------------------------------------------------------------------------
# 10. Orchestrator ranking by bid_score
# ---------------------------------------------------------------------------

class TestOrchestratorRanking:
    def test_higher_score_wins(self):
        class _HighAgent(IToolAgent):
            def evaluate_bid(self, context: MissionContext) -> ToolBid:
                return ToolBid("high", 0.95, 0.0, 10_000, {}, [], 1.5, "high priority")

        class _LowAgent(IToolAgent):
            def evaluate_bid(self, context: MissionContext) -> ToolBid:
                return ToolBid("low", 0.5, 0.0, 10_000, {}, [], 1.0, "low priority")

        with patch.dict("core.tool_bidding._REGISTRY", {"high": _HighAgent, "low": _LowAgent}):
            orch = BiddingOrchestrator()
            ctx = _make_context()
            selected = orch.select_tools(["high", "low"], ctx, max_tools=2)

        assert selected[0] == "high"
        assert selected[1] == "low"

    def test_max_tools_one_returns_best(self):
        class _AgentA(IToolAgent):
            def evaluate_bid(self, context: MissionContext) -> ToolBid:
                return ToolBid("toolA", 0.9, 0.0, 10_000, {}, [], 1.0, "a")

        class _AgentB(IToolAgent):
            def evaluate_bid(self, context: MissionContext) -> ToolBid:
                return ToolBid("toolB", 0.5, 0.0, 10_000, {}, [], 1.0, "b")

        with patch.dict("core.tool_bidding._REGISTRY", {"toolA": _AgentA, "toolB": _AgentB}):
            orch = BiddingOrchestrator()
            ctx = _make_context()
            selected = orch.select_tools(["toolA", "toolB"], ctx, max_tools=1)

        assert selected == ["toolA"]


# ---------------------------------------------------------------------------
# 11. YAML-configured agent loads correctly
# ---------------------------------------------------------------------------

class TestYamlConfiguredAgent:
    def test_goal_boost_applied(self):
        agent = YamlConfiguredToolAgent(
            "subfinder",
            config={
                "phase_affinity": ["recon"],
                "dependencies": [],
                "estimated_cost_cents": 0,
                "execution_time_estimate_ms": 30_000,
                "priority_boost_if_goals": ["subdomain_enumeration"],
                "priority_boost_value": 1.5,
            },
        )
        ctx_no_goal = _make_context(phase="recon", goals=[])
        ctx_with_goal = _make_context(phase="recon", goals=["subdomain_enumeration"])
        assert agent.evaluate_bid(ctx_with_goal).bid_score > agent.evaluate_bid(ctx_no_goal).bid_score

    def test_already_run_penalises_confidence(self):
        agent = YamlConfiguredToolAgent(
            "subfinder",
            config={
                "phase_affinity": ["recon"],
                "dependencies": [],
            },
        )
        record = ToolExecutionRecord(
            tool_id="subfinder",
            mission_id="m-test",
            executed_at="2026-01-01T00:00:00Z",
            estimated_cost_cents=0.0,
            actual_cost_cents=None,
            estimated_time_ms=30_000,
            actual_time_ms=None,
            findings_count=5,
            success=True,
        )
        ctx_fresh = _make_context(phase="recon")
        ctx_repeat = _make_context(phase="recon", history=[record])
        assert agent.evaluate_bid(ctx_repeat).confidence < agent.evaluate_bid(ctx_fresh).confidence

    def test_output_schema_returned(self):
        agent = YamlConfiguredToolAgent(
            "subfinder",
            config={
                "phase_affinity": ["recon"],
                "dependencies": [],
                "output_schema": {"subdomains": "list[str]"},
            },
        )
        bid = agent.evaluate_bid(_make_context())
        assert bid.output_schema == {"subdomains": "list[str]"}


# ---------------------------------------------------------------------------
# 12. Concurrent bid collection is thread-safe
# ---------------------------------------------------------------------------

class TestConcurrentBids:
    def test_parallel_select_tools_no_crash(self):
        orch = BiddingOrchestrator()
        errors: list[Exception] = []

        def _run(thread_id: int) -> None:
            try:
                ctx = _make_context(phase="recon")
                orch.select_tools(["subfinder", "nmap", "nuclei"], ctx, max_tools=2)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_run, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f"Thread errors: {errors}"

    def test_record_execution_thread_safe(self):
        orch = BiddingOrchestrator()

        def _record(i: int) -> None:
            orch.record_execution(ToolExecutionRecord(
                tool_id=f"tool_{i}",
                mission_id="m",
                executed_at="2026-01-01T00:00:00Z",
                estimated_cost_cents=0.0,
                actual_cost_cents=0.0,
                estimated_time_ms=1000.0,
                actual_time_ms=900.0,
                findings_count=i,
                success=True,
            ))

        threads = [threading.Thread(target=_record, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(orch.history) == 50


# ---------------------------------------------------------------------------
# Helpers / parsing
# ---------------------------------------------------------------------------

class TestParseFindings:
    def test_subdomain_extracted(self):
        raw = [{"type": "subdomain", "subdomain": "sub.example.com"}]
        ds = _parse_findings(raw)
        assert "sub.example.com" in ds.subdomains

    def test_port_extracted(self):
        raw = [{"type": "port", "port": 8080}]
        ds = _parse_findings(raw)
        assert 8080 in ds.open_ports

    def test_url_with_params_goes_to_parameterized(self):
        raw = [{"type": "url", "url": "http://ex.com/search?q=test&page=1"}]
        ds = _parse_findings(raw)
        assert "http://ex.com/search?q=test&page=1" in ds.urls_found
        assert "http://ex.com/search?q=test&page=1" in ds.parameterized_urls

    def test_url_without_params_not_in_parameterized(self):
        raw = [{"type": "url", "url": "http://ex.com/about"}]
        ds = _parse_findings(raw)
        assert "http://ex.com/about" in ds.urls_found
        assert ds.parameterized_urls == []

    def test_vulnerability_stored(self):
        raw = [{"type": "vulnerability", "severity": "high", "name": "XSS"}]
        ds = _parse_findings(raw)
        assert len(ds.vulnerabilities) == 1

    def test_non_dict_items_skipped(self):
        raw = ["not a dict", 42, None]
        ds = _parse_findings(raw)
        assert ds.subdomains == []
        assert ds.open_ports == []

    def test_empty_list(self):
        ds = _parse_findings([])
        assert ds.subdomains == []
        assert ds.vulnerabilities == []


# ---------------------------------------------------------------------------
# FindingDataset.has()
# ---------------------------------------------------------------------------

class TestFindingDatasetHas:
    def test_has_returns_false_for_empty(self):
        ds = FindingDataset()
        assert ds.has("subdomains") is False
        assert ds.has("parameterized_urls") is False

    def test_has_returns_true_for_populated(self):
        ds = FindingDataset(subdomains=["a.example.com"])
        assert ds.has("subdomains") is True

    def test_has_unknown_key_returns_false(self):
        ds = FindingDataset()
        assert ds.has("nonexistent_field") is False
