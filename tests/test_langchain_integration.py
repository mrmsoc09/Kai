"""
LangChain Integration Layer — Production-Grade Test Suite
==========================================================
Tests for the five LangChain integration modules in apps/backend/src/core/:

  * langchain_model_factory  — K1ChatModel, K1ModelFactory, get_model_factory()
  * langchain_tool_registry  — K1GovernedTool, K1LangChainToolRegistry,
                               K1ToolContext, governance exceptions
  * langchain_middleware     — K1GovernanceCallbackHandler, K1ContextInjector,
                               K1ToolFilterMiddleware, K1MiddlewareStack,
                               make_middleware_stack
  * langchain_schemas        — all Pydantic v2 schemas, registry helpers
  * langchain_reasoning      — K1ReasoningEngine, get_reasoning_engine()

Coverage targets:
  1.  Import availability
  2.  Schema validation and constraint enforcement
  3.  K1ChatModel construction and identifying params
  4.  K1ChatModel._generate / _agenerate with mocked llm_factory
  5.  Tool registry governance — band filtering, allowlist, scope
  6.  Middleware stack — callback handler events, context injection
  7.  Dynamic tool filtering — deny-by-default policy
  8.  Reasoning engine — simulation mode determinism and error handling
  9.  Security: no bypass paths exist
  10. Regression: LangChain layer does not break existing platform imports

Design rules:
  - All tests are deterministic (no network I/O, no filesystem side effects)
  - Every external dependency is mocked
  - Suite completes in well under 5 s
  - Tests are independent (no shared mutable state between methods)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure apps/backend/src is on sys.path so that lazy imports inside
# implementation files (e.g. "from core.llm_providers import llm_factory")
# resolve correctly when executed under pytest from the repo root.
# ---------------------------------------------------------------------------
_SRC_ROOT = str(Path(__file__).resolve().parents[1] / "apps" / "backend" / "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

# ---------------------------------------------------------------------------
# Module-level imports — use the same full-path style as the rest of the
# test suite (e.g. test_langgraph_mission_runtime.py).
# ---------------------------------------------------------------------------
from apps.backend.src.core.langchain_schemas import (
    SCHEMA_REGISTRY,
    EvidenceSummary,
    ExploitAssessmentSummary,
    KnowledgeLessonCandidate,
    NodeReasoningRequest,
    NodeReasoningResult,
    PlanPatchProposal,
    PromptProfileRecommendation,
    ReportSectionOutput,
    SeverityLevel,
    ToolSelectionRationale,
    TriageResult,
    get_schema,
    validate_schema_output,
)
from apps.backend.src.core.langchain_model_factory import (
    K1ChatModel,
    K1ModelFactory,
    get_model_factory,
)
from apps.backend.src.core.langchain_tool_registry import (
    K1GovernedTool,
    K1LangChainToolRegistry,
    K1ToolContext,
    ToolBandViolationError,
    ToolNotPermittedError,
    ToolScopeViolationError,
    get_tool_registry,
)
from apps.backend.src.core.langchain_middleware import (
    K1ContextInjector,
    K1GovernanceCallbackHandler,
    K1MiddlewareStack,
    K1ToolFilterMiddleware,
    make_middleware_stack,
)
from apps.backend.src.core.langchain_reasoning import (
    K1ReasoningEngine,
    get_reasoning_engine,
)
from apps.backend.src.core.tool_registry_catalog import RetryPolicy, ToolCatalogEntry

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_entry(name: str, category: str, safety_class: str) -> ToolCatalogEntry:
    """Construct a minimal ToolCatalogEntry for testing."""
    return ToolCatalogEntry(
        name=name,
        category=category,
        execution_mode="subprocess",
        binary_path=None,
        container_image=None,
        install_verification_cmd=[],
        input_schema={},
        output_schema={},
        timeout_seconds=60,
        retry_policy=RetryPolicy(),
        safety_classification=safety_class,
        tags=[],
        dependencies=[],
        api_keys_required=[],
        enabled_by_default=True,
        allowed_extra_args=None,
    )


def _make_mock_catalog() -> MagicMock:
    """
    Return a mock catalog with four tools spanning all bands:
      passive_tool  — recon, passive   → band_0
      active_tool   — scan,  active    → band_1
      intrusive_tool — exploit, intrusive → band_2
      manual_tool   — exploit, manual_only → band_3
    """
    catalog = MagicMock()
    catalog.entries.return_value = {
        "passive_tool": _make_entry("passive_tool", "recon", "passive"),
        "active_tool": _make_entry("active_tool", "scan", "active"),
        "intrusive_tool": _make_entry("intrusive_tool", "exploit", "intrusive"),
        "manual_tool": _make_entry("manual_tool", "exploit", "manual_only"),
    }
    return catalog


def _make_tool_context(
    execution_mode: str = "tool_mock",
    allowed_tool_ids: frozenset[str] | None = None,
) -> K1ToolContext:
    """Build a K1ToolContext suitable for unit tests."""
    return K1ToolContext(
        mission_id="test_mission",
        workflow_id="test_workflow",
        program_id="test_program",
        agent_id="test_agent",
        phase="recon",
        execution_mode=execution_mode,
        allowed_tool_ids=allowed_tool_ids if allowed_tool_ids is not None else frozenset(),
    )


def _make_request(mode: str = "tool_mock") -> NodeReasoningRequest:
    """Build a NodeReasoningRequest for reasoning engine tests."""
    return NodeReasoningRequest(
        node_id="test_node",
        mission_id="test_mission",
        workflow_id="test_workflow",
        program_id="test_program",
        phase="recon",
        execution_mode=mode,
        artifacts=[{"id": "a1", "type": "subdomain", "value": "test.example.com"}],
        findings=[{"id": "f1", "title": "Test Finding", "severity": "medium"}],
        available_tools=["nmap", "subfinder"],
    )


def _make_mock_llm_response(text: str = "Test response") -> MagicMock:
    """Construct a mock LLMResponse dataclass for patching llm_factory."""
    resp = MagicMock()
    resp.text = text
    resp.tool_uses = []
    resp.usage = {"input_tokens": 10, "output_tokens": 20}
    resp.latency_ms = 100.0
    return resp


def _make_mock_llm_factory(text: str = "Test response") -> MagicMock:
    """Return a mock LLMProviderFactory with an async .complete() method."""
    factory = MagicMock()
    factory.complete = AsyncMock(return_value=_make_mock_llm_response(text))
    return factory


# ===========================================================================
# 1. TestLangChainAvailability
# ===========================================================================


class TestLangChainAvailability:
    """Verify that all LangChain integration modules are importable."""

    def test_langchain_core_importable(self) -> None:
        """langchain_core package is installed and importable."""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        assert AIMessage is not None
        assert HumanMessage is not None
        assert SystemMessage is not None
        assert ChatGeneration is not None
        assert ChatResult is not None

    def test_model_factory_module_importable(self) -> None:
        """langchain_model_factory exports K1ChatModel and K1ModelFactory."""
        # Both are already imported at module level; confirm they are not None
        assert K1ChatModel is not None, "K1ChatModel must be defined when langchain_core is present"
        assert K1ModelFactory is not None
        assert get_model_factory is not None

    def test_all_modules_importable(self) -> None:
        """All five LangChain integration modules can be imported without error."""
        # Re-import by name to verify no module-level exceptions occur
        import apps.backend.src.core.langchain_model_factory as mf
        import apps.backend.src.core.langchain_tool_registry as tr
        import apps.backend.src.core.langchain_middleware as mw
        import apps.backend.src.core.langchain_schemas as sc
        import apps.backend.src.core.langchain_reasoning as re

        # Spot-check key symbols
        assert hasattr(mf, "K1ChatModel")
        assert hasattr(tr, "K1GovernedTool")
        assert hasattr(mw, "K1MiddlewareStack")
        assert hasattr(sc, "SCHEMA_REGISTRY")
        assert hasattr(re, "K1ReasoningEngine")


# ===========================================================================
# 2. TestSchemaValidation
# ===========================================================================


class TestSchemaValidation:
    """Test all Pydantic schemas validate correct inputs and reject bad ones."""

    def test_plan_patch_proposal_valid(self) -> None:
        """Valid PlanPatchProposal data constructs without error."""
        from pydantic import ValidationError

        proposal = PlanPatchProposal(
            field="tool_order",
            current_value=["nmap", "subfinder"],
            recommended_value=["subfinder", "nmap"],
            reason="subfinder is faster for initial recon",
            confidence=0.85,
            based_on_executions=20,
        )
        assert proposal.field == "tool_order"
        assert proposal.confidence == pytest.approx(0.85)

    def test_plan_patch_proposal_confidence_bounds(self) -> None:
        """PlanPatchProposal rejects confidence values > 1.0."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlanPatchProposal(
                field="tool_order",
                current_value=[],
                recommended_value=[],
                reason="test",
                confidence=1.5,  # invalid — must be <= 1.0
                based_on_executions=1,
            )

    def test_evidence_summary_valid(self) -> None:
        """EvidenceSummary accepts all valid fields."""
        summary = EvidenceSummary(
            findings_count=5,
            high_confidence_count=2,
            severity_distribution={"high": 1, "medium": 4},
            top_findings=[{"title": "XSS", "severity": "high", "target": "example.com", "confidence": 0.9}],
            affected_targets=["example.com"],
            signal_strength="high",
            summary_text="Two significant findings identified.",
        )
        assert summary.findings_count == 5
        assert summary.signal_strength == "high"

    def test_evidence_summary_invalid_signal_strength(self) -> None:
        """EvidenceSummary rejects unrecognised signal_strength values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EvidenceSummary(
                findings_count=1,
                high_confidence_count=1,
                severity_distribution={},
                top_findings=[],
                affected_targets=[],
                signal_strength="extreme",  # invalid — must be high/medium/low/none
                summary_text="test",
            )

    def test_triage_result_valid(self) -> None:
        """TriageResult accepts all valid fields."""
        result = TriageResult(
            finding_id="f-001",
            title="SQL Injection",
            severity=SeverityLevel.HIGH,
            exploitability="confirmed",
            priority=9,
            recommendation="escalate",
            rationale="Direct database access possible via unsanitised input.",
            confidence=0.95,
        )
        assert result.finding_id == "f-001"
        assert result.severity == SeverityLevel.HIGH
        assert result.priority == 9

    def test_triage_result_severity_levels(self) -> None:
        """All SeverityLevel enum values are accepted by TriageResult."""
        for level in SeverityLevel:
            result = TriageResult(
                finding_id="f-test",
                title="Test",
                severity=level,
                exploitability="unknown",
                priority=5,
                recommendation="monitor",
                rationale="test",
                confidence=0.5,
            )
            assert result.severity == level

    def test_exploit_assessment_valid(self) -> None:
        """ExploitAssessmentSummary accepts all valid fields."""
        assessment = ExploitAssessmentSummary(
            target="192.168.1.1",
            vulnerability_description="Buffer overflow in service X.",
            cve_ids=["CVE-2024-9999"],
            cvss_score=7.5,
            is_exploitable=True,
            exploit_complexity="low",
            recommendation="patch immediately",
            mitigation_notes="Apply vendor patch P-001.",
            confidence=0.9,
        )
        assert assessment.is_exploitable is True
        assert assessment.cvss_score == pytest.approx(7.5)

    def test_report_section_valid(self) -> None:
        """ReportSectionOutput accepts all valid section types."""
        section = ReportSectionOutput(
            section_id="sec-001",
            section_type="executive_summary",
            title="Executive Summary",
            content="# Executive Summary\n\nNo critical findings.",
        )
        assert section.section_type == "executive_summary"
        assert section.word_count == 0  # default

    def test_report_section_invalid_type(self) -> None:
        """ReportSectionOutput rejects unknown section_type values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ReportSectionOutput(
                section_id="sec-001",
                section_type="unknown_type",  # invalid
                title="Test",
                content="content",
            )

    def test_tool_selection_rationale_valid(self) -> None:
        """ToolSelectionRationale accepts all valid fields."""
        rationale = ToolSelectionRationale(
            tool_id="nmap",
            tool_name="Nmap Network Scanner",
            category="network_service_scanning",
            reason="Best tool for port/service enumeration.",
            expected_output_types=["open_ports", "service_versions"],
            confidence=0.92,
        )
        assert rationale.tool_id == "nmap"
        assert rationale.requires_scope_validation is True  # default

    def test_knowledge_lesson_candidate_valid(self) -> None:
        """KnowledgeLessonCandidate accepts all valid fields."""
        lesson = KnowledgeLessonCandidate(
            lesson_type="tool_order_lesson",
            content={"order": ["subfinder", "httpx", "nuclei"], "rationale": "fastest path"},
            confidence=0.8,
            source_node_id="recon-node-01",
            source_mission_id="m-2026-001",
            evidence_count=5,
        )
        assert lesson.lesson_type == "tool_order_lesson"
        assert lesson.evidence_count >= 1

    def test_schema_registry_lookup(self) -> None:
        """get_schema() returns correct class or None for unknown names."""
        cls = get_schema("EvidenceSummary")
        assert cls is EvidenceSummary

        none_result = get_schema("nonexistent_schema_xyz")
        assert none_result is None

    def test_validate_schema_output(self) -> None:
        """validate_schema_output() coerces a valid dict to a typed instance."""
        data = {
            "finding_id": "f-validate",
            "title": "SSRF Vulnerability",
            "severity": "high",
            "exploitability": "likely",
            "priority": 8,
            "recommendation": "escalate",
            "rationale": "Server-side request forgery allows internal access.",
            "confidence": 0.88,
        }
        result = validate_schema_output("TriageResult", data)
        assert isinstance(result, TriageResult)
        assert result.finding_id == "f-validate"
        assert result.severity == SeverityLevel.HIGH


# ===========================================================================
# 3. TestK1ChatModelCreation
# ===========================================================================


class TestK1ChatModelCreation:
    """Test K1ChatModel construction and configuration — no LLM calls."""

    def test_k1_chat_model_instantiation(self) -> None:
        """K1ChatModel instantiates with defaults and reports correct _llm_type."""
        model = K1ChatModel()
        assert model._llm_type == "k1_chat_model"
        assert model.model_name == "default"
        assert model.temperature == pytest.approx(0.7)
        assert model.max_tokens == 2048

    def test_k1_chat_model_with_provider(self) -> None:
        """preferred_provider field is stored correctly on the model."""
        model = K1ChatModel(preferred_provider="anthropic")
        assert model.preferred_provider == "anthropic"

    def test_k1_chat_model_identifying_params(self) -> None:
        """_identifying_params() returns dict containing model_name."""
        model = K1ChatModel(model_name="recon-specialist", mission_id="m-001")
        params = model._identifying_params()
        assert isinstance(params, dict)
        assert "model_name" in params
        assert params["model_name"] == "recon-specialist"

    def test_k1_chat_model_mission_id(self) -> None:
        """mission_id is stored on the model and surfaced in identifying params."""
        model = K1ChatModel(mission_id="mission-42")
        assert model.mission_id == "mission-42"
        params = model._identifying_params()
        assert params.get("mission_id") == "mission-42"

    def test_model_factory_create(self) -> None:
        """K1ModelFactory.create() returns a K1ChatModel instance."""
        factory = K1ModelFactory()
        model = factory.create()
        assert model is not None
        assert isinstance(model, K1ChatModel)

    def test_model_factory_create_with_provider(self) -> None:
        """K1ModelFactory.create() honours preferred_provider argument."""
        factory = K1ModelFactory()
        model = factory.create(preferred_provider="openai")
        assert model is not None
        assert model.preferred_provider == "openai"

    def test_model_factory_singleton(self) -> None:
        """get_model_factory() returns the same instance on repeated calls."""
        # Reset the singleton so the test is independent
        import apps.backend.src.core.langchain_model_factory as mod

        mod._model_factory = None
        f1 = get_model_factory()
        f2 = get_model_factory()
        assert f1 is f2

    def test_k1_chat_model_temperature_range(self) -> None:
        """K1ChatModel accepts temperature=0.7 and stores it correctly."""
        model = K1ChatModel(temperature=0.7)
        assert model.temperature == pytest.approx(0.7)

        # Boundary values
        model_zero = K1ChatModel(temperature=0.0)
        assert model_zero.temperature == pytest.approx(0.0)

        model_max = K1ChatModel(temperature=2.0)
        assert model_max.temperature == pytest.approx(2.0)


# ===========================================================================
# 4. TestK1ChatModelGenerate
# ===========================================================================


class TestK1ChatModelGenerate:
    """Test K1ChatModel._generate and _agenerate with a mocked llm_factory."""

    def test_generate_with_human_message(self) -> None:
        """_generate converts HumanMessage to ChatResult containing AIMessage."""
        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_core.outputs import ChatResult

        mock_factory = _make_mock_llm_factory("Test response")
        with patch("core.llm_providers.llm_factory", mock_factory):
            model = K1ChatModel()
            result = model._generate([HumanMessage(content="scan example.com")])

        assert isinstance(result, ChatResult)
        assert len(result.generations) == 1
        ai_msg = result.generations[0].message
        assert isinstance(ai_msg, AIMessage)
        assert ai_msg.content == "Test response"

    def test_generate_extracts_system_message(self) -> None:
        """SystemMessage is extracted and passed to complete() as system= kwarg."""
        from langchain_core.messages import HumanMessage, SystemMessage

        mock_factory = _make_mock_llm_factory()
        with patch("core.llm_providers.llm_factory", mock_factory):
            model = K1ChatModel()
            model._generate([
                SystemMessage(content="You are a bug bounty hunter."),
                HumanMessage(content="recon example.com"),
            ])

        call_kwargs = mock_factory.complete.call_args.kwargs
        # SystemMessage must be extracted into the system parameter
        assert call_kwargs["system"] == "You are a bug bounty hunter."
        # And must NOT appear in the messages list
        for msg in call_kwargs["messages"]:
            assert msg.get("role") != "system"

    def test_generate_uses_system_prompt_fallback(self) -> None:
        """When no SystemMessage is present, model.system_prompt is used."""
        from langchain_core.messages import HumanMessage

        mock_factory = _make_mock_llm_factory()
        with patch("core.llm_providers.llm_factory", mock_factory):
            model = K1ChatModel(system_prompt="Fallback system context.")
            model._generate([HumanMessage(content="hello")])

        call_kwargs = mock_factory.complete.call_args.kwargs
        assert call_kwargs["system"] == "Fallback system context."

    def test_agenerate_async_path(self) -> None:
        """_agenerate calls complete() directly without asyncio.run nesting."""
        from langchain_core.messages import HumanMessage
        from langchain_core.outputs import ChatResult

        mock_factory = _make_mock_llm_factory("Async response")

        async def run() -> ChatResult:
            with patch("core.llm_providers.llm_factory", mock_factory):
                model = K1ChatModel()
                return await model._agenerate([HumanMessage(content="async test")])

        result = asyncio.run(run())
        assert result.generations[0].message.content == "Async response"
        # Verify complete was awaited (AsyncMock tracks this)
        assert mock_factory.complete.await_count == 1

    def test_generate_with_tool_uses(self) -> None:
        """Response with tool_uses populates AIMessage.additional_kwargs['tool_calls']."""
        from langchain_core.messages import HumanMessage

        mock_resp = _make_mock_llm_response("Call a tool")
        mock_resp.tool_uses = [{"name": "nmap", "input": {"target": "example.com"}}]
        mock_factory = MagicMock()
        mock_factory.complete = AsyncMock(return_value=mock_resp)

        with patch("core.llm_providers.llm_factory", mock_factory):
            model = K1ChatModel()
            result = model._generate([HumanMessage(content="scan")])

        ai_msg = result.generations[0].message
        assert "tool_calls" in ai_msg.additional_kwargs
        tool_calls = ai_msg.additional_kwargs["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "nmap"

    def test_generate_provider_mapping(self) -> None:
        """preferred_provider='anthropic' resolves to LLMProvider.ANTHROPIC."""
        from langchain_core.messages import HumanMessage

        mock_factory = _make_mock_llm_factory()
        with patch("core.llm_providers.llm_factory", mock_factory):
            model = K1ChatModel(preferred_provider="anthropic")
            model._generate([HumanMessage(content="test")])

        call_kwargs = mock_factory.complete.call_args.kwargs
        # The resolved provider must be the ANTHROPIC enum value
        from core.llm_providers import LLMProvider

        assert call_kwargs["preferred_provider"] == LLMProvider.ANTHROPIC

    def test_generate_unknown_provider_logs_warning(self) -> None:
        """Unknown preferred_provider logs a warning and falls back to None."""
        from langchain_core.messages import HumanMessage

        mock_factory = _make_mock_llm_factory()
        with patch("core.llm_providers.llm_factory", mock_factory):
            model = K1ChatModel(preferred_provider="unknown_xyz")
            model._generate([HumanMessage(content="test")])

        call_kwargs = mock_factory.complete.call_args.kwargs
        # Fallback: provider is None when unrecognised
        assert call_kwargs["preferred_provider"] is None

    def test_generate_empty_messages_handled(self) -> None:
        """_generate with an empty messages list does not raise."""
        mock_factory = _make_mock_llm_factory("empty response")
        with patch("core.llm_providers.llm_factory", mock_factory):
            model = K1ChatModel()
            result = model._generate([])

        assert result.generations[0].text == "empty response"
        call_kwargs = mock_factory.complete.call_args.kwargs
        assert call_kwargs["messages"] == []


# ===========================================================================
# 5. TestK1ToolRegistryGovernance
# ===========================================================================


class TestK1ToolRegistryGovernance:
    """Test tool registry governance enforcement using a mocked catalog."""

    def test_tool_registry_get_tools_for_context(self) -> None:
        """get_tools_for_context() returns K1GovernedTool instances for allowed bands."""
        ctx = _make_tool_context()
        registry = K1LangChainToolRegistry()
        with patch("apps.backend.src.core.langchain_tool_registry.get_tool_catalog", return_value=_make_mock_catalog()):
            tools = registry.get_tools_for_context(ctx)
        names = {t.name for t in tools}
        # band_0 and band_1 tools should be present
        assert "passive_tool" in names
        assert "active_tool" in names

    def test_tool_registry_excludes_band3(self) -> None:
        """band_3 (manual_only) tools are never returned by get_tools_for_context()."""
        ctx = _make_tool_context()
        registry = K1LangChainToolRegistry()
        with patch("apps.backend.src.core.langchain_tool_registry.get_tool_catalog", return_value=_make_mock_catalog()):
            tools = registry.get_tools_for_context(ctx)
        names = {t.name for t in tools}
        assert "manual_tool" not in names

    def test_tool_registry_filters_by_allowed_ids(self) -> None:
        """filter_by_authority() returns only tools in the allowlist."""
        ctx = _make_tool_context(allowed_tool_ids=frozenset({"passive_tool"}))
        registry = K1LangChainToolRegistry()
        with patch("apps.backend.src.core.langchain_tool_registry.get_tool_catalog", return_value=_make_mock_catalog()):
            tools = registry.get_tools_for_context(ctx)
        names = {t.name for t in tools}
        # Only passive_tool is in the allowlist; active_tool must be excluded
        assert "passive_tool" in names
        assert "active_tool" not in names

    def test_governed_tool_graph_only_mode(self) -> None:
        """In graph_only mode, _run returns a structural mock without governance checks."""
        ctx = _make_tool_context(execution_mode="graph_only")
        entry = _make_entry("passive_tool", "recon", "passive")
        tool = K1GovernedTool(name="passive_tool", description="desc", catalog_entry=entry, context=ctx)

        result = tool._run("example.com")
        parsed = json.loads(result)
        assert parsed["status"] == "graph_only"
        assert parsed["tool_id"] == "passive_tool"

    def test_governed_tool_tool_mock_mode(self) -> None:
        """In tool_mock mode, _run returns a mock result after band check."""
        ctx = _make_tool_context(execution_mode="tool_mock")
        entry = _make_entry("passive_tool", "recon", "passive")
        tool = K1GovernedTool(name="passive_tool", description="desc", catalog_entry=entry, context=ctx)

        result = tool._run("example.com")
        parsed = json.loads(result)
        assert parsed["status"] == "mock"
        assert parsed["tool_id"] == "passive_tool"

    def test_governed_tool_band3_raises(self) -> None:
        """Calling a band_3 tool in live mode raises ToolBandViolationError."""
        # Empty allowlist so the allowlist check does not fire first
        ctx = _make_tool_context(execution_mode="live", allowed_tool_ids=frozenset())
        entry = _make_entry("manual_tool", "exploit", "manual_only")
        tool = K1GovernedTool(name="manual_tool", description="desc", catalog_entry=entry, context=ctx)

        with pytest.raises(ToolBandViolationError):
            tool._run("example.com")

    def test_governed_tool_not_in_allowlist_raises(self) -> None:
        """Tool not in allowed_tool_ids raises ToolNotPermittedError."""
        ctx = _make_tool_context(execution_mode="live", allowed_tool_ids=frozenset({"other_tool"}))
        entry = _make_entry("passive_tool", "recon", "passive")
        tool = K1GovernedTool(name="passive_tool", description="desc", catalog_entry=entry, context=ctx)

        with pytest.raises(ToolNotPermittedError):
            tool._run("example.com")

    def test_governed_tool_scope_violation_raises(self) -> None:
        """scope_validator returning False raises ToolScopeViolationError."""
        ctx = _make_tool_context(execution_mode="live", allowed_tool_ids=frozenset())
        entry = _make_entry("passive_tool", "recon", "passive")
        tool = K1GovernedTool(name="passive_tool", description="desc", catalog_entry=entry, context=ctx)

        with patch("apps.backend.src.core.langchain_tool_registry.scope_validator", return_value=False):
            with patch("apps.backend.src.core.langchain_tool_registry.emit"):
                with pytest.raises(ToolScopeViolationError):
                    tool._run("out-of-scope.com")

    def test_governed_tool_scope_check_called(self) -> None:
        """scope_validator is called with the correct target and program_id."""
        ctx = _make_tool_context(execution_mode="live", allowed_tool_ids=frozenset())
        entry = _make_entry("passive_tool", "recon", "passive")
        tool = K1GovernedTool(name="passive_tool", description="desc", catalog_entry=entry, context=ctx)

        with patch("apps.backend.src.core.langchain_tool_registry.scope_validator", return_value=True) as mock_sv:
            with patch("apps.backend.src.core.langchain_tool_registry.emit"):
                tool._run("scope-checked.example.com")

        mock_sv.assert_called_once()
        call_args = mock_sv.call_args
        assert call_args[0][0] == "scope-checked.example.com"  # positional target
        assert call_args[0][1] == "test_program"               # positional program_id

    def test_get_tools_for_phase_recon(self) -> None:
        """get_tools_for_phase('recon') returns only recon/osint category tools."""
        # Use a catalog where each tool has a distinct category
        catalog = MagicMock()
        catalog.entries.return_value = {
            "recon_tool": _make_entry("recon_tool", "recon", "passive"),
            "osint_tool": _make_entry("osint_tool", "osint", "passive"),
            "scan_tool": _make_entry("scan_tool", "network_service_scanning", "active"),
        }
        ctx = _make_tool_context()
        registry = K1LangChainToolRegistry()

        with patch("apps.backend.src.core.langchain_tool_registry.get_tool_catalog", return_value=catalog):
            tools = registry.get_tools_for_phase(ctx, "recon")

        names = {t.name for t in tools}
        assert "recon_tool" in names
        assert "osint_tool" in names
        # network_service_scanning belongs to "scan" phase, not "recon"
        assert "scan_tool" not in names

    def test_tool_registry_singleton(self) -> None:
        """get_tool_registry() returns the same instance on repeated calls."""
        import apps.backend.src.core.langchain_tool_registry as mod

        mod._registry = None  # reset for test isolation
        r1 = get_tool_registry()
        r2 = get_tool_registry()
        assert r1 is r2

    def test_tool_context_immutable(self) -> None:
        """K1ToolContext is a frozen dataclass — field assignment raises FrozenInstanceError."""
        from dataclasses import FrozenInstanceError

        ctx = _make_tool_context()
        with pytest.raises(FrozenInstanceError):
            ctx.mission_id = "tampered"  # type: ignore[misc]


# ===========================================================================
# 6. TestMiddlewareStack
# ===========================================================================


class TestMiddlewareStack:
    """Test callback handlers and middleware stack components."""

    def _make_handler(self) -> K1GovernanceCallbackHandler:
        """Construct a fully-configured K1GovernanceCallbackHandler for testing."""
        return K1GovernanceCallbackHandler(
            mission_id="m1",
            workflow_id="wf1",
            program_id="p1",
            agent_id="agent1",
            node_id="node1",
            phase="recon",
        )

    def test_governance_handler_on_llm_start(self) -> None:
        """on_llm_start() emits an llm_invocation_started event."""
        handler = self._make_handler()
        with patch("apps.backend.src.core.langchain_middleware.emit") as mock_emit:
            handler.on_llm_start({"name": "k1_chat_model"}, ["prompt text"])

        assert mock_emit.call_count == 1
        emitted_event = mock_emit.call_args[0][0]
        assert emitted_event.event_type == "llm_invocation_started"
        assert emitted_event.mission_id == "m1"

    def test_governance_handler_on_llm_end(self) -> None:
        """on_llm_end() stores an event in the handler's recent_events list."""
        handler = self._make_handler()
        with patch("apps.backend.src.core.langchain_middleware.emit"):
            response_mock = MagicMock()
            response_mock.llm_output = {"token_usage": {"total_tokens": 30}}
            handler.on_llm_end(response_mock)

        events = handler.get_recent_events()
        assert len(events) == 1
        assert events[0].event_type == "llm_invocation_completed"

    def test_governance_handler_on_tool_start(self) -> None:
        """on_tool_start() emits a tool_invocation_started event."""
        handler = self._make_handler()
        with patch("apps.backend.src.core.langchain_middleware.emit") as mock_emit:
            handler.on_tool_start({"name": "nmap"}, '{"target": "example.com"}')

        assert mock_emit.call_count == 1
        emitted_event = mock_emit.call_args[0][0]
        assert emitted_event.event_type == "tool_invocation_started"
        assert emitted_event.detail.get("tool_name") == "nmap"

    def test_governance_handler_on_tool_error(self) -> None:
        """on_tool_error() emits a node_failed event."""
        handler = self._make_handler()
        with patch("apps.backend.src.core.langchain_middleware.emit") as mock_emit:
            handler.on_tool_error(RuntimeError("network timeout"))

        assert mock_emit.call_count == 1
        emitted_event = mock_emit.call_args[0][0]
        assert emitted_event.event_type == "node_failed"
        assert "network timeout" in emitted_event.detail.get("error", "")

    def test_context_injector_prepends_system(self) -> None:
        """inject() prepends a SystemMessage when none exists in the list."""
        from langchain_core.messages import HumanMessage, SystemMessage

        injector = K1ContextInjector(
            mission_id="m1", workflow_id="wf1", program_id="p1",
            phase="recon", node_id="n1", execution_mode="live",
        )
        messages = [HumanMessage(content="recon example.com")]
        result = injector.inject(messages)

        assert len(result) == 2
        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], HumanMessage)

    def test_context_injector_extends_existing_system(self) -> None:
        """inject() extends an existing SystemMessage rather than replacing it."""
        from langchain_core.messages import HumanMessage, SystemMessage

        injector = K1ContextInjector(
            mission_id="m1", workflow_id="wf1", program_id="p1",
            phase="recon", node_id="n1", execution_mode="live",
        )
        messages = [
            SystemMessage(content="Existing system context."),
            HumanMessage(content="hello"),
        ]
        result = injector.inject(messages)

        assert len(result) == 2
        system_content = result[0].content
        assert "Existing system context." in system_content
        assert "m1" in system_content  # governance block is prepended

    def test_context_injector_as_runnable(self) -> None:
        """as_runnable() returns a LangChain RunnableLambda."""
        from langchain_core.runnables import RunnableLambda

        injector = K1ContextInjector(
            mission_id="m1", workflow_id="wf1", program_id="p1",
            phase="recon", node_id="n1", execution_mode="live",
        )
        runnable = injector.as_runnable()
        assert isinstance(runnable, RunnableLambda)

    def test_context_injector_contains_mission_id(self) -> None:
        """Injected governance context embeds the mission_id."""
        from langchain_core.messages import HumanMessage

        injector = K1ContextInjector(
            mission_id="unique-mission-id-xyz",
            workflow_id="wf1", program_id="p1",
            phase="recon", node_id="n1", execution_mode="live",
        )
        result = injector.inject([HumanMessage(content="test")])
        assert "unique-mission-id-xyz" in result[0].content

    def test_middleware_stack_for_mission(self) -> None:
        """K1MiddlewareStack.for_mission() creates a fully wired stack."""
        stack = K1MiddlewareStack.for_mission(
            mission_id="m-stack-test",
            workflow_id="wf1",
            program_id="p1",
            agent_id="agent1",
            phase="recon",
            execution_mode="tool_mock",
        )
        assert isinstance(stack, K1MiddlewareStack)
        callbacks = stack.callbacks()
        assert len(callbacks) == 1
        assert isinstance(callbacks[0], K1GovernanceCallbackHandler)
        assert stack.tool_filter is not None

    def test_make_middleware_stack_factory(self) -> None:
        """Module-level make_middleware_stack() factory creates a working stack."""
        stack = make_middleware_stack(
            mission_id="m-factory-test",
            workflow_id="wf1",
            program_id="p1",
            agent_id="agent1",
            phase="scan",
            execution_mode="live",
        )
        assert isinstance(stack, K1MiddlewareStack)
        events = stack.get_events()
        assert isinstance(events, list)
        assert len(events) == 0  # no events before any callbacks fire


# ===========================================================================
# 7. TestDynamicToolFiltering
# ===========================================================================


class TestDynamicToolFiltering:
    """Test deny-by-default tool filtering via K1ToolFilterMiddleware."""

    def _make_middleware(
        self,
        allowed: frozenset[str] | None = None,
        execution_mode: str = "live",
    ) -> K1ToolFilterMiddleware:
        ctx = K1ToolContext(
            mission_id="m1", workflow_id="wf1", program_id="p1",
            agent_id="a1", phase="recon",
            execution_mode=execution_mode,
            allowed_tool_ids=allowed if allowed is not None else frozenset(),
        )
        return K1ToolFilterMiddleware(context=ctx)

    def test_filter_middleware_deny_unlisted(self) -> None:
        """Tool not in allowed_tool_ids is denied when allowlist is non-empty."""
        mw = self._make_middleware(allowed=frozenset({"tool_a"}))
        assert mw.is_tool_permitted("tool_b") is False

    def test_filter_middleware_permit_listed(self) -> None:
        """Tool in allowed_tool_ids is permitted."""
        mw = self._make_middleware(allowed=frozenset({"tool_a", "tool_b"}))
        assert mw.is_tool_permitted("tool_a") is True
        assert mw.is_tool_permitted("tool_b") is True

    def test_filter_middleware_empty_allowlist_permits_all(self) -> None:
        """Empty allowlist (frozenset()) permits every named tool."""
        mw = self._make_middleware(allowed=frozenset())
        assert mw.is_tool_permitted("any_tool_name") is True
        assert mw.is_tool_permitted("nmap") is True

    def test_filter_middleware_execution_mode_graph_only(self) -> None:
        """In graph_only mode, the allowlist still applies at the middleware level."""
        mw = self._make_middleware(allowed=frozenset({"tool_a"}), execution_mode="graph_only")
        # Allowlist is enforced regardless of execution_mode at middleware level
        assert mw.is_tool_permitted("tool_a") is True
        assert mw.is_tool_permitted("tool_b") is False

    def test_filter_band3_always_denied(self) -> None:
        """K1LangChainToolRegistry never returns band_3 tools via get_tools_for_context."""
        # Even with an empty allowlist (all bands potentially permitted) and
        # include_bands explicitly containing band_3, it is stripped out.
        catalog = MagicMock()
        catalog.entries.return_value = {
            "manual_tool": _make_entry("manual_tool", "exploit", "manual_only"),
        }
        ctx = _make_tool_context(execution_mode="live", allowed_tool_ids=frozenset())
        registry = K1LangChainToolRegistry()

        with patch("apps.backend.src.core.langchain_tool_registry.get_tool_catalog", return_value=catalog):
            # Attempt to include band_3 explicitly — it must still be excluded
            tools = registry.get_tools_for_context(ctx, include_bands=frozenset({"band_3"}))

        assert len(tools) == 0


# ===========================================================================
# 8. TestReasoningEngine
# ===========================================================================


class TestReasoningEngine:
    """Test K1ReasoningEngine node-local reasoning helpers in simulation mode."""

    def test_summarize_artifact_bundle_mock_mode(self) -> None:
        """mock mode returns an EvidenceSummary fixture without LLM calls."""
        engine = K1ReasoningEngine()
        request = _make_request(mode="tool_mock")
        result = asyncio.run(engine.summarize_artifact_bundle(request))

        assert result.success is True
        assert result.reasoning_type == "evidence_summary"
        assert isinstance(result.output, dict)
        # Validate the output matches EvidenceSummary schema
        summary = EvidenceSummary.model_validate(result.output)
        assert summary.signal_strength in {"high", "medium", "low", "none"}

    def test_classify_finding_mock_mode(self) -> None:
        """mock mode returns a TriageResult fixture for classify_finding."""
        engine = K1ReasoningEngine()
        request = _make_request(mode="tool_mock")
        finding = {"id": "f-001", "title": "XSS in login form", "severity": "medium"}
        result = asyncio.run(engine.classify_finding(request, finding))

        assert result.success is True
        assert result.reasoning_type == "triage"
        triage = TriageResult.model_validate(result.output)
        assert triage.finding_id == "f-001"
        assert triage.title == "XSS in login form"

    def test_generate_evidence_digest_mock_mode(self) -> None:
        """mock mode returns a digest string in the output dict."""
        engine = K1ReasoningEngine()
        request = _make_request(mode="tool_mock")
        result = asyncio.run(engine.generate_evidence_digest(request))

        assert result.success is True
        assert result.reasoning_type == "evidence_digest"
        assert "digest" in result.output
        assert isinstance(result.output["digest"], str)
        assert len(result.output["digest"]) > 0

    def test_rank_candidate_tools_mock_mode(self) -> None:
        """mock mode returns one ranking entry per available_tool."""
        engine = K1ReasoningEngine()
        request = _make_request(mode="tool_mock")
        result = asyncio.run(engine.rank_candidate_tools(request))

        assert result.success is True
        assert result.reasoning_type == "tool_selection"
        rankings = result.output.get("rankings", [])
        # One ranking per available_tool in the request
        assert len(rankings) == len(request.available_tools)

    def test_select_prompt_profile_mock_mode(self) -> None:
        """mock mode returns a PromptProfileRecommendation fixture."""
        engine = K1ReasoningEngine()
        request = _make_request(mode="tool_mock")
        profiles = [
            {"profile_id": "recon-focused", "profile_type": "prompt_profile"},
            {"profile_id": "scan-thorough", "profile_type": "prompt_profile"},
        ]
        result = asyncio.run(engine.select_prompt_profile(request, profiles))

        assert result.success is True
        assert result.reasoning_type == "prompt_profile_selection"
        rec = PromptProfileRecommendation.model_validate(result.output)
        # Must recommend one of the provided candidate profiles
        assert rec.profile_id == "recon-focused"

    def test_produce_structured_triage_mock_mode(self) -> None:
        """mock mode returns a triage_results list with one entry per finding."""
        engine = K1ReasoningEngine()
        request = _make_request(mode="tool_mock")
        result = asyncio.run(engine.produce_structured_triage(request))

        assert result.success is True
        assert result.reasoning_type == "structured_triage"
        triage_results = result.output.get("triage_results", [])
        assert len(triage_results) == len(request.findings)
        # Validate each result conforms to the schema
        for item in triage_results:
            tr = TriageResult.model_validate(item)
            assert tr.finding_id == request.findings[0]["id"]

    def test_reasoning_engine_singleton(self) -> None:
        """get_reasoning_engine() returns a consistent instance across calls."""
        import apps.backend.src.core.langchain_reasoning as mod

        mod._reasoning_engine = None  # reset for test isolation
        e1 = get_reasoning_engine()
        e2 = get_reasoning_engine()
        assert e1 is e2

    def test_reasoning_engine_error_handling(self) -> None:
        """
        When the model factory raises, the result has success=False and
        a non-empty error string.
        """
        engine = K1ReasoningEngine()
        # Live mode so the LLM path is taken; force an error via mock
        request = _make_request(mode="live")

        mock_factory = MagicMock()
        mock_factory.create.side_effect = RuntimeError("injected test error")

        with patch.object(engine, "_get_model_factory", return_value=mock_factory):
            result = asyncio.run(engine.summarize_artifact_bundle(request))

        assert result.success is False
        assert "injected test error" in result.error
        assert result.reasoning_type == "evidence_summary"


# ===========================================================================
# 9. TestNoBypassPaths
# ===========================================================================


class TestNoBypassPaths:
    """Security: prove that no bypass paths exist in the LangChain layer."""

    def test_langchain_model_uses_kai_provider_chain(self) -> None:
        """K1ChatModel._generate calls llm_factory.complete — no direct HTTP."""
        import inspect
        from apps.backend.src.core import langchain_model_factory

        generate_src = inspect.getsource(langchain_model_factory.K1ChatModel._generate)
        agenerate_src = inspect.getsource(langchain_model_factory.K1ChatModel._agenerate)

        # Must reference the Kai provider factory
        assert "llm_factory" in generate_src
        assert "llm_factory" in agenerate_src

        # Must NOT contain direct HTTP call mechanisms
        for forbidden in ("requests.", "http.client", "urllib.request", "httpx."):
            assert forbidden not in generate_src, f"Direct HTTP found in _generate: {forbidden}"
            assert forbidden not in agenerate_src, f"Direct HTTP found in _agenerate: {forbidden}"

    def test_tool_governance_cannot_be_skipped_in_live_mode(self) -> None:
        """In live mode, _enforce_governance always runs the full check pipeline."""
        ctx = _make_tool_context(execution_mode="live", allowed_tool_ids=frozenset())
        entry = _make_entry("passive_tool", "recon", "passive")
        tool = K1GovernedTool(name="passive_tool", description="desc", catalog_entry=entry, context=ctx)

        # Scope validator returns False — must raise even with no allowlist restriction
        with patch("apps.backend.src.core.langchain_tool_registry.scope_validator", return_value=False):
            with patch("apps.backend.src.core.langchain_tool_registry.emit"):
                with pytest.raises(ToolScopeViolationError):
                    tool._run("example.com")

    def test_band3_never_surfaced(self) -> None:
        """K1LangChainToolRegistry.get_tools_for_context never returns band_3 tools."""
        catalog = MagicMock()
        # Catalog contains only a band_3 tool
        catalog.entries.return_value = {
            "manual_tool": _make_entry("manual_tool", "exploit", "manual_only"),
        }
        ctx = _make_tool_context(execution_mode="live", allowed_tool_ids=frozenset())
        registry = K1LangChainToolRegistry()

        with patch("apps.backend.src.core.langchain_tool_registry.get_tool_catalog", return_value=catalog):
            # Default bands only include band_0 + band_1
            tools_default = registry.get_tools_for_context(ctx)
            assert len(tools_default) == 0

            # Explicitly passing all bands still excludes band_3 (denied unconditionally)
            tools_all_bands = registry.get_tools_for_context(
                ctx,
                include_bands=frozenset({"band_0", "band_1", "band_2", "band_3"}),
            )
            assert all(t.name != "manual_tool" for t in tools_all_bands)

    def test_forbidden_patch_fields_rejected_at_schema(self) -> None:
        """
        PlanPatchProposal with a known allowed field validates successfully.
        Runtime-level field restriction lives in praison_strategy_learning, not the schema.
        """
        from pydantic import ValidationError

        # Valid field from _ALLOWED_LEARNING_FIELDS passes schema validation
        proposal = PlanPatchProposal(
            field="tool_order",
            current_value=[],
            recommended_value=["subfinder"],
            reason="known-good field",
            confidence=0.9,
            based_on_executions=3,
        )
        assert proposal.field == "tool_order"

        # Schema-level extra-field guard: extra keys are forbidden
        with pytest.raises(ValidationError):
            PlanPatchProposal.model_validate(
                {
                    "field": "tool_order",
                    "current_value": [],
                    "recommended_value": [],
                    "reason": "test",
                    "confidence": 0.5,
                    "based_on_executions": 1,
                    "unexpected_extra_field": "injected",  # forbidden by extra="forbid"
                }
            )

    def test_event_emission_on_all_tool_invocations(self) -> None:
        """
        Every K1GovernanceCallbackHandler tool invocation (including mocked ones)
        emits at least one event when on_tool_start is called.
        """
        handler = K1GovernanceCallbackHandler(
            mission_id="m1", workflow_id="wf1", program_id="p1",
            agent_id="a1", node_id="n1", phase="recon",
        )
        with patch("apps.backend.src.core.langchain_middleware.emit"):
            handler.on_tool_start({"name": "mock_tool"}, '{"target": "example.com"}')
            handler.on_tool_end('{"status": "mock"}')

        events = handler.get_recent_events()
        assert len(events) >= 1, "At least one event must be emitted per tool invocation"


# ===========================================================================
# 10. TestRegressionIntegration
# ===========================================================================


class TestRegressionIntegration:
    """Prove LangChain integration layer does not break existing platform imports."""

    def test_langchain_imports_dont_break_praison_imports(self) -> None:
        """
        praison_state and praison_node_executors can be imported after all
        LangChain modules have already been loaded.
        """
        # LangChain modules are already imported at module level above.
        # Importing praison modules here verifies no import-time side effects.
        from apps.backend.src.core.praison_state import K1GraphState, make_initial_state
        from apps.backend.src.core.praison_node_executors import (
            make_node_executor,
            make_specialist_cluster_executor,
        )

        assert K1GraphState is not None
        assert make_node_executor is not None
        assert make_specialist_cluster_executor is not None

    def test_langchain_schemas_not_in_k1graph_state(self) -> None:
        """
        K1GraphState from praison_state is independent of langchain_schemas;
        no schema classes should appear in K1GraphState's field annotations.
        """
        from apps.backend.src.core.praison_state import K1GraphState

        # Collect all type annotation names in K1GraphState
        annotation_values = set()
        for v in K1GraphState.__annotations__.values():
            annotation_values.add(str(v))

        langchain_schema_names = {
            "PlanPatchProposal", "EvidenceSummary", "TriageResult",
            "ExploitAssessmentSummary", "ReportSectionOutput",
            "ToolSelectionRationale", "KnowledgeLessonCandidate",
            "NodeReasoningRequest", "NodeReasoningResult",
        }
        # None of the LangChain schema names should appear as field types in K1GraphState
        overlap = langchain_schema_names & {v.split(".")[-1] for v in annotation_values}
        assert len(overlap) == 0, (
            f"LangChain schema types found in K1GraphState annotations: {overlap}"
        )

    def test_langgraph_runtime_still_imports(self) -> None:
        """
        praison_mission_runtime can be imported alongside all LangChain modules
        without import errors or attribute collisions.
        """
        from apps.backend.src.core.praison_mission_runtime import MissionRuntime, MissionStatus

        assert MissionRuntime is not None
        assert MissionStatus is not None

        # Verify that the LangChain factory singleton is also intact
        factory = get_model_factory()
        assert isinstance(factory, K1ModelFactory)
