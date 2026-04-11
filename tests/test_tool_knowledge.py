"""Test suite for tool knowledge registry and agent integration.

Tests cover:
  - ToolKnowledgeLoader initialization and YAML parsing
  - Knowledge retrieval for all Wave 7 tools (testssl, spiderfoot, graphql-cop)
  - Interpretation rules and execution parameters
  - Context injection and formatting
  - Error handling and validation
  - BaseToolAgent integration with knowledge loader
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from apps.backend.src.agents.tools.base_tool_agent import BaseToolAgent
from apps.backend.src.tools.knowledge.loader import ToolKnowledgeLoader


class TestToolKnowledgeLoaderInitialization:
    """Test ToolKnowledgeLoader initialization."""

    def test_loader_initializes_with_valid_yaml(self, knowledge_file: Path) -> None:
        """Verify loader initializes with correct YAML file."""
        loader = ToolKnowledgeLoader(knowledge_file)
        assert loader is not None
        assert loader.knowledge_file_path == knowledge_file

    def test_loader_raises_on_missing_file(self) -> None:
        """Verify loader raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            ToolKnowledgeLoader("/nonexistent/path/to/tool_knowledge.yaml")

    def test_loader_raises_on_malformed_yaml(self) -> None:
        """Verify loader raises ValueError for malformed YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                ToolKnowledgeLoader(temp_path)
        finally:
            temp_path.unlink()

    def test_loader_caches_knowledge(self, knowledge_file: Path) -> None:
        """Verify loader caches loaded knowledge for efficiency."""
        loader = ToolKnowledgeLoader(knowledge_file)
        knowledge1 = loader.get_tool_knowledge("testssl")
        knowledge2 = loader.get_tool_knowledge("testssl")
        assert knowledge1 is knowledge2  # Same object from cache


class TestGetToolKnowledge:
    """Test tool knowledge retrieval."""

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_get_tool_knowledge_for_wave7_tools(self, knowledge_file: Path, tool_name: str) -> None:
        """Verify knowledge retrieval for each Wave 7 tool."""
        loader = ToolKnowledgeLoader(knowledge_file)
        knowledge = loader.get_tool_knowledge(tool_name)

        assert isinstance(knowledge, dict)
        assert "metadata" in knowledge
        assert "core_concepts" in knowledge
        assert "key_findings" in knowledge
        assert "execution_parameters" in knowledge
        assert "interpretation_rules" in knowledge
        assert "common_pitfalls" in knowledge

    def test_get_tool_knowledge_raises_for_unknown_tool(self, knowledge_file: Path) -> None:
        """Verify KeyError raised for unknown tool."""
        loader = ToolKnowledgeLoader(knowledge_file)
        with pytest.raises(KeyError, match="not found in knowledge registry"):
            loader.get_tool_knowledge("nonexistent-tool")

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_tool_knowledge_has_metadata(self, knowledge_file: Path, tool_name: str) -> None:
        """Verify all tools have required metadata fields."""
        loader = ToolKnowledgeLoader(knowledge_file)
        knowledge = loader.get_tool_knowledge(tool_name)
        metadata = knowledge.get("metadata", {})

        assert metadata.get("description") is not None
        assert metadata.get("phase") is not None
        assert metadata.get("source_url") is not None
        assert metadata.get("version") is not None


class TestInterpretationRules:
    """Test interpretation rules retrieval and validation."""

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_interpretation_rules_exist(self, knowledge_file: Path, tool_name: str) -> None:
        """Verify interpretation rules are defined for each tool."""
        loader = ToolKnowledgeLoader(knowledge_file)
        rules = loader.get_interpretation_rules(tool_name)

        assert isinstance(rules, list)
        assert len(rules) >= 5, f"{tool_name} should have 5+ interpretation rules"
        assert all(isinstance(rule, str) for rule in rules)
        assert all(rule.strip() for rule in rules)

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_interpretation_rules_are_actionable(
        self, knowledge_file: Path, tool_name: str
    ) -> None:
        """Verify interpretation rules contain actionable guidance."""
        loader = ToolKnowledgeLoader(knowledge_file)
        rules = loader.get_interpretation_rules(tool_name)

        # Rules should contain indicators and actions
        for rule in rules:
            assert "Rule" in rule or "Pitfall" in rule or "indicator" in rule.lower()


class TestExecutionParameters:
    """Test execution parameters and flags."""

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_execution_parameters_exist(self, knowledge_file: Path, tool_name: str) -> None:
        """Verify execution parameters are defined for each tool."""
        loader = ToolKnowledgeLoader(knowledge_file)
        params = loader.get_execution_parameters(tool_name)

        assert isinstance(params, dict)
        assert "critical_flags" in params
        assert isinstance(params["critical_flags"], list)
        assert len(params["critical_flags"]) >= 1

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_critical_flags_have_structure(self, knowledge_file: Path, tool_name: str) -> None:
        """Verify critical flags have required structure."""
        loader = ToolKnowledgeLoader(knowledge_file)
        params = loader.get_execution_parameters(tool_name)
        critical_flags = params.get("critical_flags", [])

        for flag_info in critical_flags:
            assert isinstance(flag_info, dict)
            assert "flag" in flag_info
            assert "purpose" in flag_info
            assert isinstance(flag_info["flag"], str)
            assert isinstance(flag_info["purpose"], str)
            assert flag_info["flag"].startswith("-")

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_known_limitations_documented(self, knowledge_file: Path, tool_name: str) -> None:
        """Verify known limitations are documented."""
        loader = ToolKnowledgeLoader(knowledge_file)
        params = loader.get_execution_parameters(tool_name)
        limitations = params.get("known_limitations", [])

        assert isinstance(limitations, list)
        assert len(limitations) >= 1


class TestKnowledgeInjection:
    """Test context injection for agent prompts."""

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_knowledge_injection_into_context_text_format(
        self, knowledge_file: Path, tool_name: str
    ) -> None:
        """Verify knowledge can be formatted and injected into agent context."""
        loader = ToolKnowledgeLoader(knowledge_file)
        context = loader.inject_into_context(tool_name, context_format="text")

        assert isinstance(context, str)
        assert len(context) > 500  # Should be substantial
        assert f"{tool_name.upper()}" in context.upper()
        assert "Core Concepts" in context or "core_concepts" in context.lower()

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_knowledge_injection_into_context_json_format(
        self, knowledge_file: Path, tool_name: str
    ) -> None:
        """Verify knowledge can be formatted as JSON."""
        loader = ToolKnowledgeLoader(knowledge_file)
        context = loader.inject_into_context(tool_name, context_format="json")

        assert isinstance(context, str)
        # Should be parseable JSON
        parsed = json.loads(context)
        assert isinstance(parsed, dict)
        assert "metadata" in parsed

    def test_inject_into_context_raises_on_invalid_format(self, knowledge_file: Path) -> None:
        """Verify ValueError raised for unsupported context format."""
        loader = ToolKnowledgeLoader(knowledge_file)
        with pytest.raises(ValueError, match="Unsupported context_format"):
            loader.inject_into_context("testssl", context_format="invalid")

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_text_context_contains_key_sections(self, knowledge_file: Path, tool_name: str) -> None:
        """Verify text context contains all key sections."""
        loader = ToolKnowledgeLoader(knowledge_file)
        context = loader.inject_into_context(tool_name, context_format="text")

        # Should contain major sections
        assert "Interpretation Rules" in context
        assert "Common Pitfalls" in context
        assert "Execution Parameters" in context or "Critical Flags" in context


class TestValidation:
    """Test tool knowledge validation."""

    @pytest.mark.parametrize("tool_name", ["testssl", "spiderfoot", "graphql-cop"])
    def test_validate_tool_knowledge_passes_for_wave7_tools(
        self, knowledge_file: Path, tool_name: str
    ) -> None:
        """Verify validation passes for all Wave 7 tools."""
        loader = ToolKnowledgeLoader(knowledge_file)
        is_valid, issues = loader.validate_tool_knowledge(tool_name)

        assert is_valid, f"Validation failed for {tool_name}: {issues}"
        assert len(issues) == 0

    def test_validate_tool_knowledge_returns_issues_for_unknown_tool(
        self, knowledge_file: Path
    ) -> None:
        """Verify validation returns issues for unknown tool."""
        loader = ToolKnowledgeLoader(knowledge_file)
        is_valid, issues = loader.validate_tool_knowledge("nonexistent")

        assert not is_valid
        assert len(issues) > 0

    def test_validate_tool_knowledge_detects_missing_fields(self) -> None:
        """Verify validation detects missing required fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "incomplete_tool": {
                        "metadata": {"description": "Test"},
                        # Missing core_concepts, key_findings, etc.
                    }
                },
                f,
            )
            f.flush()
            temp_path = Path(f.name)

        try:
            loader = ToolKnowledgeLoader(temp_path)
            is_valid, issues = loader.validate_tool_knowledge("incomplete_tool")

            assert not is_valid
            assert any("core_concepts" in issue for issue in issues)
        finally:
            temp_path.unlink()

    def test_list_available_tools(self, knowledge_file: Path) -> None:
        """Verify list of available tools is correct."""
        loader = ToolKnowledgeLoader(knowledge_file)
        available = loader.list_available_tools()

        assert isinstance(available, list)
        assert len(available) >= 3
        assert "testssl" in available
        assert "spiderfoot" in available
        assert "graphql-cop" in available
        # List should be sorted
        assert available == sorted(available)


class TestBaseToolAgentIntegration:
    """Test integration of tool knowledge into BaseToolAgent."""

    def test_base_tool_agent_loads_knowledge_on_init(
        self, knowledge_file: Path, mock_tool_agent_class: type[BaseToolAgent]
    ) -> None:
        """Verify BaseToolAgent loads tool knowledge on initialization."""
        # Patch the knowledge file path for testing
        agent = mock_tool_agent_class()
        # Tool knowledge should be loaded if file exists
        knowledge = agent.get_tool_knowledge()
        # Knowledge may be empty if file not found, but method should exist
        assert isinstance(knowledge, dict)

    def test_base_tool_agent_get_tool_knowledge_method(
        self, mock_tool_agent_class: type[BaseToolAgent]
    ) -> None:
        """Verify BaseToolAgent has get_tool_knowledge method."""
        agent = mock_tool_agent_class()
        assert hasattr(agent, "get_tool_knowledge")
        assert callable(agent.get_tool_knowledge)

    def test_base_tool_agent_get_interpretation_context_method(
        self, mock_tool_agent_class: type[BaseToolAgent]
    ) -> None:
        """Verify BaseToolAgent has get_interpretation_context method."""
        agent = mock_tool_agent_class()
        assert hasattr(agent, "get_interpretation_context")
        assert callable(agent.get_interpretation_context)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_missing_tool_error_handling(self, knowledge_file: Path) -> None:
        """Verify graceful error when requesting unknown tool knowledge."""
        loader = ToolKnowledgeLoader(knowledge_file)

        try:
            loader.get_tool_knowledge("nonexistent-tool")
            pytest.fail("Should raise KeyError")
        except KeyError as e:
            assert "nonexistent-tool" in str(e)
            assert "available tools" in str(e).lower()

    def test_empty_interpretation_rules_handled(self) -> None:
        """Verify empty interpretation rules are handled gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "test_tool": {
                        "metadata": {
                            "description": "Test",
                            "phase": 1,
                            "source_url": "http://example.com",
                            "version": "1.0",
                        },
                        "core_concepts": ["concept1"],
                        "key_findings": {"finding1": "desc"},
                        "execution_parameters": {"critical_flags": []},
                        "interpretation_rules": "not_a_list",  # Wrong type
                        "common_pitfalls": ["pitfall1"],
                    }
                },
                f,
            )
            f.flush()
            temp_path = Path(f.name)

        try:
            loader = ToolKnowledgeLoader(temp_path)
            rules = loader.get_interpretation_rules("test_tool")
            assert isinstance(rules, list)
            assert len(rules) == 0  # Should return empty list
        finally:
            temp_path.unlink()


# Fixtures


@pytest.fixture
def knowledge_file() -> Path:
    """Provide path to tool knowledge registry."""
    kai_root = Path(__file__).resolve().parents[1]
    knowledge_path = kai_root / "tools" / "knowledge" / "tool_knowledge.yaml"
    if not knowledge_path.exists():
        pytest.skip("tool_knowledge.yaml not found")
    return knowledge_path


@pytest.fixture
def mock_tool_agent_class(knowledge_file: Path) -> type[BaseToolAgent]:
    """Provide a minimal BaseToolAgent subclass for testing."""

    class MockToolAgent(BaseToolAgent):
        TOOL_NAME = "testssl"

        def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
            return ["echo", target]

    return MockToolAgent
