"""Tool knowledge registry loader for agent context injection.

This module loads and manages tool-specific knowledge from the centralized
tool_knowledge.yaml registry. Agents use this loader to:
  - Retrieve tool-specific execution parameters
  - Access interpretation rules for output analysis
  - Inject domain expertise into execution context
  - Validate tool knowledge completeness
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ToolKnowledgeLoader:
    """Load and manage tool-specific knowledge for agent context injection."""

    def __init__(self, knowledge_file_path: str | Path) -> None:
        """Initialize loader with path to tool_knowledge.yaml.

        Args:
            knowledge_file_path: Path to the tool knowledge registry YAML file.

        Raises:
            FileNotFoundError: If knowledge file does not exist.
            yaml.YAMLError: If knowledge file is malformed YAML.
        """
        self.knowledge_file_path = Path(knowledge_file_path)
        if not self.knowledge_file_path.exists():
            raise FileNotFoundError(f"Tool knowledge file not found: {self.knowledge_file_path}")

        try:
            with self.knowledge_file_path.open("r", encoding="utf-8") as f:
                self._registry = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in knowledge file: {e}") from e

        self._cache: dict[str, dict[str, Any]] = {}
        logger.info(f"Loaded tool knowledge registry with {len(self._registry)} tools")

    def get_tool_knowledge(self, tool_name: str) -> dict[str, Any]:
        """Retrieve complete knowledge structure for a specific tool.

        Args:
            tool_name: Name of the tool (e.g., 'testssl', 'spiderfoot', 'graphql-cop').

        Returns:
            Dictionary containing tool knowledge (metadata, concepts, findings, rules, etc.).

        Raises:
            KeyError: If tool is not registered in the knowledge base.
        """
        if tool_name in self._cache:
            return self._cache[tool_name]

        if tool_name not in self._registry:
            available = ", ".join(self.list_available_tools())
            raise KeyError(
                f"Tool '{tool_name}' not found in knowledge registry. "
                f"Available tools: {available}"
            )

        knowledge = self._registry[tool_name]
        self._cache[tool_name] = knowledge
        return knowledge

    def get_interpretation_rules(self, tool_name: str) -> list[str]:
        """Get interpretation rules for analyzing tool output.

        Args:
            tool_name: Name of the tool.

        Returns:
            List of interpretation rule strings (actionable rules for result analysis).

        Raises:
            KeyError: If tool is not registered or has no interpretation rules.
        """
        knowledge = self.get_tool_knowledge(tool_name)
        rules = knowledge.get("interpretation_rules", [])
        if not isinstance(rules, list):
            logger.warning(
                f"Tool '{tool_name}' interpretation_rules is not a list; returning empty"
            )
            return []
        return rules

    def get_execution_parameters(self, tool_name: str) -> dict[str, Any]:
        """Get optimal parameters (flags, configurations) for tool execution.

        Args:
            tool_name: Name of the tool.

        Returns:
            Dictionary containing 'critical_flags', 'optional_flags', and 'known_limitations'.

        Raises:
            KeyError: If tool is not registered or has no execution parameters.
        """
        knowledge = self.get_tool_knowledge(tool_name)
        params = knowledge.get("execution_parameters", {})
        if not isinstance(params, dict):
            logger.warning(
                f"Tool '{tool_name}' execution_parameters is not a dict; returning empty"
            )
            return {}
        return params

    def inject_into_context(
        self,
        tool_name: str,
        context_format: str = "text",
    ) -> str:
        """Generate agent-ready context string with tool knowledge.

        Returns formatted text that can be injected into agent prompts,
        including core concepts, key findings, and interpretation rules.

        Args:
            tool_name: Name of the tool.
            context_format: Format of output ('text' or 'json').

        Returns:
            Formatted string ready for injection into agent context/prompts.

        Raises:
            KeyError: If tool is not registered.
            ValueError: If context_format is not supported.
        """
        if context_format not in {"text", "json"}:
            raise ValueError(f"Unsupported context_format: {context_format}")

        knowledge = self.get_tool_knowledge(tool_name)

        if context_format == "text":
            return self._format_text_context(tool_name, knowledge)
        else:
            import json

            return json.dumps(knowledge, indent=2)

    def validate_tool_knowledge(self, tool_name: str) -> tuple[bool, list[str]]:
        """Validate that tool knowledge is complete and consistent.

        Checks for required fields and valid structure.

        Args:
            tool_name: Name of the tool to validate.

        Returns:
            Tuple of (is_valid, list_of_issues).
            - is_valid: True if knowledge is valid, False otherwise.
            - list_of_issues: List of validation error messages.
        """
        issues: list[str] = []

        try:
            knowledge = self.get_tool_knowledge(tool_name)
        except KeyError as e:
            return False, [str(e)]

        # Check required top-level keys
        required_keys = {
            "metadata",
            "core_concepts",
            "key_findings",
            "execution_parameters",
            "interpretation_rules",
            "common_pitfalls",
        }
        for key in required_keys:
            if key not in knowledge:
                issues.append(f"Missing required key: {key}")

        # Validate metadata
        if "metadata" in knowledge:
            metadata = knowledge["metadata"]
            if not isinstance(metadata, dict):
                issues.append("metadata must be a dictionary")
            else:
                required_metadata = {"description", "phase", "source_url", "version"}
                for key in required_metadata:
                    if key not in metadata:
                        issues.append(f"metadata missing required field: {key}")

        # Validate core_concepts
        if "core_concepts" in knowledge:
            concepts = knowledge["core_concepts"]
            if not isinstance(concepts, list):
                issues.append("core_concepts must be a list")
            elif len(concepts) < 3:
                issues.append(f"core_concepts should have 3-5 items; found {len(concepts)}")

        # Validate key_findings
        if "key_findings" in knowledge:
            findings = knowledge["key_findings"]
            if not isinstance(findings, dict):
                issues.append("key_findings must be a dictionary")
            elif len(findings) < 3:
                issues.append(f"key_findings should have multiple entries; found {len(findings)}")

        # Validate interpretation_rules
        if "interpretation_rules" in knowledge:
            rules = knowledge["interpretation_rules"]
            if not isinstance(rules, list):
                issues.append("interpretation_rules must be a list")
            elif len(rules) < 5:
                issues.append(f"interpretation_rules should have 5+ rules; found {len(rules)}")

        # Validate common_pitfalls
        if "common_pitfalls" in knowledge:
            pitfalls = knowledge["common_pitfalls"]
            if not isinstance(pitfalls, list):
                issues.append("common_pitfalls must be a list")
            elif len(pitfalls) < 3:
                issues.append(f"common_pitfalls should have 3+ items; found {len(pitfalls)}")

        # Validate execution_parameters
        if "execution_parameters" in knowledge:
            params = knowledge["execution_parameters"]
            if not isinstance(params, dict):
                issues.append("execution_parameters must be a dictionary")
            else:
                if "critical_flags" not in params:
                    issues.append("execution_parameters missing critical_flags")
                elif not isinstance(params["critical_flags"], list):
                    issues.append("critical_flags must be a list")
                elif len(params["critical_flags"]) < 1:
                    issues.append("critical_flags should have at least 1 entry")

        return len(issues) == 0, issues

    def list_available_tools(self) -> list[str]:
        """Return list of all tools with registered knowledge.

        Returns:
            Sorted list of tool names registered in the knowledge base.
        """
        return sorted(self._registry.keys())

    @staticmethod
    def _format_text_context(tool_name: str, knowledge: dict[str, Any]) -> str:
        """Format tool knowledge as human-readable text context.

        Args:
            tool_name: Name of the tool.
            knowledge: Tool knowledge dictionary.

        Returns:
            Formatted text string ready for agent injection.
        """
        lines: list[str] = []

        # Header
        metadata = knowledge.get("metadata", {})
        lines.append(f"# Tool Knowledge: {tool_name.upper()}")
        lines.append(f"## {metadata.get('description', 'N/A')}")
        lines.append(
            f"Phase: {metadata.get('phase', 'N/A')} | Version: {metadata.get('version', 'N/A')}"
        )
        lines.append("")

        # Core Concepts
        lines.append("## Core Concepts")
        for concept in knowledge.get("core_concepts", []):
            lines.append(f"- {concept}")
        lines.append("")

        # Key Findings
        lines.append("## Key Findings")
        findings = knowledge.get("key_findings", {})
        for finding_name, description in findings.items():
            lines.append(f"- **{finding_name}**: {description}")
        lines.append("")

        # Execution Parameters
        lines.append("## Execution Parameters")
        params = knowledge.get("execution_parameters", {})
        if "critical_flags" in params:
            lines.append("### Critical Flags")
            for flag_info in params["critical_flags"]:
                if isinstance(flag_info, dict):
                    lines.append(
                        f"- `{flag_info.get('flag', 'N/A')}`: {flag_info.get('purpose', 'N/A')}"
                    )
        if "optional_flags" in params:
            lines.append("### Optional Flags")
            for flag_info in params["optional_flags"]:
                if isinstance(flag_info, dict):
                    lines.append(
                        f"- `{flag_info.get('flag', 'N/A')}`: {flag_info.get('purpose', 'N/A')}"
                    )
        if "known_limitations" in params:
            lines.append("### Known Limitations")
            for limitation in params["known_limitations"]:
                lines.append(f"- {limitation}")
        lines.append("")

        # Interpretation Rules
        lines.append("## Interpretation Rules")
        for rule in knowledge.get("interpretation_rules", []):
            lines.append(f"- {rule}")
        lines.append("")

        # Common Pitfalls
        lines.append("## Common Pitfalls")
        for pitfall in knowledge.get("common_pitfalls", []):
            lines.append(f"- {pitfall}")

        return "\n".join(lines)
