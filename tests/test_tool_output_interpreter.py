"""Test suite for tool output interpreter and knowledge-aware executor.

Tests cover:
  - ToolOutputInterpreter initialization and functionality
  - Interpretation of output from all Wave 7 tools (testssl, spiderfoot, graphql-cop)
  - Severity assessment and confidence scoring
  - Next steps generation
  - KnowledgeAwareExecutor initialization and execution
  - BaseToolAgent integration with knowledge-aware execution
  - Error handling and graceful degradation
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from apps.backend.src.agents.tools.base_tool_agent import BaseToolAgent
from apps.backend.src.tools.knowledge.executor import KnowledgeAwareExecutor
from apps.backend.src.tools.knowledge.interpreter import ToolOutputInterpreter
from apps.backend.src.tools.knowledge.loader import ToolKnowledgeLoader


class TestToolOutputInterpreterInitialization:
    """Test ToolOutputInterpreter initialization."""

    def test_interpreter_initializes_with_loader(
        self, knowledge_loader: ToolKnowledgeLoader
    ) -> None:
        """Verify ToolOutputInterpreter initializes with loader."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        assert interpreter is not None
        assert interpreter.knowledge_loader is knowledge_loader


class TestOutputInterpretation:
    """Test output interpretation for all Wave 7 tools."""

    @pytest.mark.parametrize(
        "tool_name,output",
        [
            (
                "testssl",
                "Testing TLS on example.com:443\n"
                "Protocol TLS 1.2 supported\n"
                "Cipher Suite: AES-256-GCM - Grade A\n"
                "Cipher Suite: DES-CBC - Grade F\n"
                "Certificate: Expired\n"
                "HSTS: Disabled\n",
            ),
            (
                "spiderfoot",
                "Scanning example.com\n"
                "subdomain: api.example.com\n"
                "subdomain: dev.example.com\n"
                "email: admin@example.com\n"
                "asn: AS12345\n"
                "Zone transfer: successful\n",
            ),
            (
                "graphql-cop",
                "Testing GraphQL: example.com/graphql\n"
                "Introspection: enabled\n"
                "Query depth limit: not set\n"
                "Batch queries: supported\n"
                "Mutations: 5 found\n",
            ),
        ],
    )
    def test_interpret_output_produces_findings(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        tool_name: str,
        output: str,
    ) -> None:
        """Verify interpretation produces findings for each tool."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        result = interpreter.interpret_output(tool_name, output, target="example.com")

        assert isinstance(result, dict)
        assert "raw_output" in result
        assert "findings" in result
        assert "summary" in result
        assert result["raw_output"] == output
        assert isinstance(result["findings"], list)

    def test_interpret_output_with_execution_time(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify interpretation includes execution time."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        output = "Test output"
        exec_time = 5.5

        result = interpreter.interpret_output(
            "testssl",
            output,
            target="example.com",
            execution_time=exec_time,
        )

        assert result["execution_time"] == exec_time

    def test_interpret_empty_output_returns_empty_findings(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify empty output produces empty findings."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        result = interpreter.interpret_output("testssl", "", target="example.com")

        assert result["findings"] == []
        assert result["interpretation_quality"] == 0.0


class TestSeverityAssessment:
    """Test severity assessment for findings."""

    @pytest.mark.parametrize(
        "tool_name,finding,expected_severity",
        [
            ("testssl", "Cipher Suite: DES-CBC - Grade F", "CRITICAL"),
            ("testssl", "Protocol TLS 1.0 supported", "MEDIUM"),
            ("testssl", "Protocol TLS 1.3 supported", "INFO"),
            ("spiderfoot", "Zone transfer: successful", "HIGH"),
            ("spiderfoot", "subdomain: api.example.com", "INFO"),
            ("graphql-cop", "Introspection: enabled", "MEDIUM"),
            ("graphql-cop", "Query depth limit: not set", "HIGH"),
        ],
    )
    def test_severity_assessment(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        tool_name: str,
        finding: str,
        expected_severity: str,
    ) -> None:
        """Verify severity is assessed correctly."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        severity = interpreter._assess_severity(tool_name, "unknown", finding)
        assert severity == expected_severity

    def test_critical_severity_for_expired_cert(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify expired certificate is CRITICAL."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        severity = interpreter._assess_severity("testssl", "certificate", "Certificate: Expired")
        assert severity == "CRITICAL"


class TestConfidenceScoring:
    """Test confidence score calculation."""

    @pytest.mark.parametrize(
        "tool_name,finding",
        [
            ("testssl", "Cipher Suite: AES-256-GCM - Grade A"),
            ("spiderfoot", "subdomain: api.example.com"),
            ("graphql-cop", "Introspection: enabled"),
        ],
    )
    def test_confidence_in_range(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        tool_name: str,
        finding: str,
    ) -> None:
        """Verify confidence score is in valid range [0.0, 1.0]."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        confidence = interpreter._calculate_confidence(tool_name, finding, finding)

        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_high_confidence_for_known_tools(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        tool_name: str,
    ) -> None:
        """Verify high confidence for findings from known tools."""
        interpreter = ToolOutputInterpreter(knowledge_loader)

        if tool_name == "testssl":
            finding = "Cipher Suite: DES - Grade F"
        elif tool_name == "spiderfoot":
            finding = "subdomain: test.example.com"
        else:  # graphql-cop
            finding = "Introspection: enabled"

        confidence = interpreter._calculate_confidence(tool_name, finding, finding)
        # Known tools should have reasonably high confidence
        assert confidence >= 0.5


class TestCategorization:
    """Test finding categorization."""

    @pytest.mark.parametrize(
        "tool_name,finding,expected_category",
        [
            ("testssl", "Cipher Suite: AES-256 - Grade A", "cipher"),
            ("testssl", "Certificate: Expired", "certificate"),
            ("testssl", "Protocol TLS 1.2", "protocol"),
            ("spiderfoot", "subdomain: api.example.com", "subdomain"),
            ("spiderfoot", "email: admin@example.com", "email"),
            ("graphql-cop", "Introspection: enabled", "introspection"),
            ("graphql-cop", "Query depth limit: not set", "query_limits"),
        ],
    )
    def test_finding_categorization(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        tool_name: str,
        finding: str,
        expected_category: str,
    ) -> None:
        """Verify findings are categorized correctly."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        category = interpreter._categorize_finding(tool_name, finding)
        assert category == expected_category


class TestNextStepsGeneration:
    """Test next steps generation."""

    @pytest.mark.parametrize(
        "tool_name,category,severity",
        [
            ("testssl", "cipher", "CRITICAL"),
            ("testssl", "certificate", "CRITICAL"),
            ("spiderfoot", "dns_misconfiguration", "HIGH"),
            ("graphql-cop", "introspection", "MEDIUM"),
        ],
    )
    def test_next_steps_generated(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        tool_name: str,
        category: str,
        severity: str,
    ) -> None:
        """Verify next steps are generated for findings."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        next_steps = interpreter._generate_next_steps(tool_name, category, severity)

        assert isinstance(next_steps, list)
        assert len(next_steps) > 0
        assert all(isinstance(step, str) for step in next_steps)


class TestKnowledgeAwareExecutor:
    """Test KnowledgeAwareExecutor functionality."""

    def test_executor_initializes(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify KnowledgeAwareExecutor initializes correctly."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        executor = KnowledgeAwareExecutor(knowledge_loader, interpreter)

        assert executor is not None
        assert executor.knowledge_loader is knowledge_loader
        assert executor.interpreter is interpreter

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_execute_with_knowledge_without_executor(
        self,
        knowledge_loader: ToolKnowledgeLoader,
        tool_name: str,
    ) -> None:
        """Verify execute_with_knowledge produces expected structure."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        executor = KnowledgeAwareExecutor(knowledge_loader, interpreter)

        result = executor.execute_with_knowledge(
            tool_name,
            "example.com",
            parameters=None,
            timeout=300,
            tool_executor=None,  # Will use mock execution
        )

        assert isinstance(result, dict)
        assert "tool_name" in result
        assert "target" in result
        assert "status" in result
        assert "raw_output" in result
        assert "interpreted_findings" in result
        assert "summary" in result
        assert "execution_time" in result
        assert "knowledge_applied" in result
        assert "severity_distribution" in result

        assert result["tool_name"] == tool_name
        assert result["target"] == "example.com"
        assert result["status"] == "success"
        assert result["knowledge_applied"] is True

    def test_severity_distribution_in_result(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify severity distribution is included in results."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        executor = KnowledgeAwareExecutor(knowledge_loader, interpreter)

        result = executor.execute_with_knowledge(
            "testssl",
            "example.com",
            tool_executor=None,
        )

        distribution = result["severity_distribution"]
        assert isinstance(distribution, dict)
        assert all(k in distribution for k in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"])
        assert all(isinstance(v, int) for v in distribution.values())

    def test_execution_log_tracking(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify execution log is tracked."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        executor = KnowledgeAwareExecutor(knowledge_loader, interpreter)

        assert len(executor.get_execution_log()) == 0

        executor.execute_with_knowledge("testssl", "example.com")
        executor.execute_with_knowledge("spiderfoot", "example.com")

        log = executor.get_execution_log()
        assert len(log) == 2
        assert log[0]["tool_name"] == "testssl"
        assert log[1]["tool_name"] == "spiderfoot"

        executor.clear_execution_log()
        assert len(executor.get_execution_log()) == 0


class TestBaseToolAgentIntegration:
    """Test integration with BaseToolAgent."""

    def test_base_tool_agent_has_execute_with_knowledge(
        self,
        mock_tool_agent_class: type[BaseToolAgent],
    ) -> None:
        """Verify BaseToolAgent has execute_with_knowledge method."""
        agent = mock_tool_agent_class()
        assert hasattr(agent, "execute_with_knowledge")
        assert callable(agent.execute_with_knowledge)

    def test_base_tool_agent_has_get_interpretation_summary(
        self,
        mock_tool_agent_class: type[BaseToolAgent],
    ) -> None:
        """Verify BaseToolAgent has get_interpretation_summary method."""
        agent = mock_tool_agent_class()
        assert hasattr(agent, "get_interpretation_summary")
        assert callable(agent.get_interpretation_summary)

    def test_base_tool_agent_interpretation_summary_initialized(
        self,
        mock_tool_agent_class: type[BaseToolAgent],
    ) -> None:
        """Verify interpretation summary is initialized to empty string."""
        agent = mock_tool_agent_class()
        summary = agent.get_interpretation_summary()
        assert isinstance(summary, str)


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    def test_interpreter_handles_missing_output(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify interpreter handles empty/missing output gracefully."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        result = interpreter.interpret_output("testssl", "")

        assert result is not None
        assert isinstance(result, dict)
        assert result["findings"] == []

    def test_interpreter_handles_unknown_tool(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify interpreter handles unknown tools gracefully."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        output = "Some test output"

        # Should not raise exception, fallback to generic extraction
        result = interpreter.interpret_output("unknown-tool", output)

        assert result is not None
        assert isinstance(result["findings"], list)

    def test_executor_handles_missing_knowledge(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify executor handles missing knowledge gracefully."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        executor = KnowledgeAwareExecutor(knowledge_loader, interpreter)

        # Execute tool that doesn't have knowledge
        result = executor.execute_with_knowledge(
            "unknown-tool",
            "example.com",
            tool_executor=None,
        )

        assert result["status"] == "success"  # Should still succeed
        assert isinstance(result["interpreted_findings"], list)


class TestPerformance:
    """Test performance characteristics."""

    def test_interpretation_time_under_threshold(
        self,
        knowledge_loader: ToolKnowledgeLoader,
    ) -> None:
        """Verify interpretation adds minimal overhead."""
        interpreter = ToolOutputInterpreter(knowledge_loader)
        output = "Test output " * 100  # Larger output

        start = time.time()
        result = interpreter.interpret_output("testssl", output, target="example.com")
        elapsed = time.time() - start

        # Interpretation should be fast (under 1 second for reasonable output)
        assert elapsed < 1.0
        assert "interpretation_time" in result
        assert result["interpretation_time"] < 1.0


# Fixtures


@pytest.fixture
def knowledge_loader() -> ToolKnowledgeLoader:
    """Provide ToolKnowledgeLoader instance."""
    kai_root = Path(__file__).resolve().parents[1]
    knowledge_path = kai_root / "tools" / "knowledge" / "tool_knowledge.yaml"
    if not knowledge_path.exists():
        pytest.skip("tool_knowledge.yaml not found")
    return ToolKnowledgeLoader(knowledge_path)


@pytest.fixture
def mock_tool_agent_class(knowledge_loader: ToolKnowledgeLoader) -> type[BaseToolAgent]:
    """Provide a minimal BaseToolAgent subclass for testing."""

    class MockToolAgent(BaseToolAgent):
        TOOL_NAME = "testssl"

        def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
            return ["echo", target]

    return MockToolAgent
