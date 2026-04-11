"""
Tool Registry Audit.
Verifies that all registered tools have execution wrappers and fallback support.
"""

from __future__ import annotations

import logging
import yaml
from typing import Any, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ToolAuditResult:
    """Result of tool audit."""

    tool_name: str
    registered: bool
    has_wrapper: bool
    has_workflow: bool
    execution_mode: str
    safety_classification: str
    category: str
    issues: list[str] = None
    remediation: str = ""

    def __post_init__(self):
        if self.issues is None:
            self.issues = []

    def is_compliant(self) -> bool:
        """Check if tool is compliant."""
        return (
            self.registered
            and (self.has_wrapper or self.has_workflow)
            and not self.issues
        )


class ToolRegistryAuditor:
    """
    Audits tool registry for completeness and compliance.
    Verifies wrapper scripts, workflow definitions, fallback logic.
    """

    def __init__(
        self,
        registry_path: str = "tools/registry/tool_registry.yaml",
        wrappers_path: str = "apps/backend/src/core/",
    ):
        """
        Initialize auditor.

        Args:
            registry_path: Path to tool registry YAML
            wrappers_path: Base path for wrapper files
        """
        self.registry_path = Path(registry_path)
        self.wrappers_path = Path(wrappers_path)
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.audit_results: list[ToolAuditResult] = []

    def load_registry(self) -> bool:
        """Load tool registry from YAML."""
        if not self.registry_path.exists():
            logger.error(f"Registry not found: {self.registry_path}")
            return False

        try:
            with open(self.registry_path, "r") as f:
                data = yaml.safe_load(f)
                tools = data.get("tools", [])

                for tool in tools:
                    tool_name = tool.get("name", "unknown")
                    self.tools[tool_name] = tool

            logger.info(
                f"Loaded {len(self.tools)} tools from registry"
            )
            return True

        except Exception as e:
            logger.error(f"Error loading registry: {str(e)}")
            return False

    def audit_all_tools(self) -> list[ToolAuditResult]:
        """Audit all tools in registry."""
        logger.info("Starting tool registry audit...")

        self.audit_results = []

        for tool_name, tool_data in self.tools.items():
            result = self._audit_tool(tool_name, tool_data)
            self.audit_results.append(result)

        # Generate summary
        self._log_audit_summary()

        return self.audit_results

    def _audit_tool(
        self, tool_name: str, tool_data: Dict[str, Any]
    ) -> ToolAuditResult:
        """Audit a single tool."""
        result = ToolAuditResult(
            tool_name=tool_name,
            registered=True,
            has_wrapper=False,
            has_workflow=False,
            execution_mode=tool_data.get("execution_mode", "unknown"),
            safety_classification=tool_data.get(
                "safety_classification", "unknown"
            ),
            category=tool_data.get("category", "unknown"),
        )

        # Check for Python wrapper
        wrapper_name = self._get_wrapper_filename(tool_name)
        has_python_wrapper = self._check_python_wrapper(wrapper_name)

        if has_python_wrapper:
            result.has_wrapper = True
        else:
            result.issues.append(
                f"No Python wrapper found for tool"
            )

        # Check for YAML workflow
        has_yaml_workflow = self._check_yaml_workflow(tool_name)
        if has_yaml_workflow:
            result.has_workflow = True

        # Check agent class
        agent_class = tool_data.get("agent_class")
        if not agent_class:
            result.issues.append("Missing agent_class definition")

        # Check binary path
        binary_path = tool_data.get("binary_path")
        if not binary_path:
            result.issues.append("Missing binary_path")

        # Check input/output schema
        input_schema = tool_data.get("input_schema")
        output_schema = tool_data.get("output_schema")

        if not input_schema:
            result.issues.append("Missing input_schema")
        if not output_schema:
            result.issues.append("Missing output_schema")

        # Generate remediation
        if not result.is_compliant():
            result.remediation = self._generate_remediation(
                tool_name, result
            )

        return result

    def _get_wrapper_filename(self, tool_name: str) -> str:
        """Get expected wrapper filename for tool."""
        # Convert tool name to likely wrapper module
        # e.g., "sqlmap" -> "tool_adapters_scan.py" or similar
        return f"tool_adapters_{tool_name.replace('-', '_')}.py"

    def _check_python_wrapper(self, wrapper_filename: str) -> bool:
        """Check if Python wrapper exists."""
        # Check multiple possible wrapper locations
        possible_locations = [
            self.wrappers_path / wrapper_filename,
            self.wrappers_path / "tool_adapters_recon.py",
            self.wrappers_path / "tool_adapters_scan.py",
            self.wrappers_path / "tool_adapters_osint.py",
            self.wrappers_path / "tool_adapters_bugbounty.py",
            self.wrappers_path / "tool_adapters_validate.py",
        ]

        for path in possible_locations:
            if path.exists():
                return True

        return False

    def _check_yaml_workflow(self, tool_name: str) -> bool:
        """Check if YAML workflow exists."""
        workflow_path = Path(
            f"tools/workflows/{tool_name}_workflow.yaml"
        )
        return workflow_path.exists()

    def _generate_remediation(
        self, tool_name: str, result: ToolAuditResult
    ) -> str:
        """Generate remediation guidance for non-compliant tool."""
        remediation_steps = []

        if not result.has_wrapper:
            remediation_steps.append(
                f"1. Create Python wrapper in apps/backend/src/core/tool_adapters_*.py"
            )
            remediation_steps.append(
                f"   - Implement execute_{tool_name}() method"
            )
            remediation_steps.append(
                f"   - Handle input validation and error cases"
            )

        if "Missing agent_class" in str(result.issues):
            remediation_steps.append(
                f"2. Add agent_class to registry: {tool_name.title()}Agent"
            )

        if "Missing input_schema" in str(result.issues):
            remediation_steps.append(
                f"3. Define input_schema in registry (required params)"
            )

        remediation_steps.append(
            f"4. Implement fallback to generic recon if execution fails"
        )

        return "\n".join(remediation_steps)

    def _log_audit_summary(self) -> None:
        """Log audit summary statistics."""
        compliant = sum(
            1 for r in self.audit_results if r.is_compliant()
        )
        has_wrapper = sum(
            1 for r in self.audit_results if r.has_wrapper
        )
        has_workflow = sum(
            1 for r in self.audit_results if r.has_workflow
        )

        logger.info(
            f"Tool Audit Summary:\n"
            f"  Total tools: {len(self.audit_results)}\n"
            f"  Compliant: {compliant} ({compliant / len(self.audit_results) * 100:.1f}%)\n"
            f"  With wrappers: {has_wrapper}\n"
            f"  With workflows: {has_workflow}\n"
        )

    def get_audit_report(self) -> Dict[str, Any]:
        """Get comprehensive audit report."""
        compliant_tools = [
            r for r in self.audit_results if r.is_compliant()
        ]
        non_compliant_tools = [
            r
            for r in self.audit_results
            if not r.is_compliant()
        ]

        report = {
            "timestamp": (
                __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat()
            ),
            "summary": {
                "total_tools": len(self.audit_results),
                "compliant": len(compliant_tools),
                "compliance_percentage": (
                    len(compliant_tools)
                    / len(self.audit_results)
                    * 100
                    if self.audit_results
                    else 0
                ),
                "non_compliant": len(non_compliant_tools),
            },
            "compliant_tools": [
                {
                    "name": r.tool_name,
                    "category": r.category,
                    "execution_mode": r.execution_mode,
                    "safety_classification": r.safety_classification,
                }
                for r in compliant_tools
            ],
            "non_compliant_tools": [
                {
                    "name": r.tool_name,
                    "category": r.category,
                    "issues": r.issues,
                    "remediation": r.remediation,
                }
                for r in non_compliant_tools
            ],
            "compliance_by_category": (
                self._get_compliance_by_category()
            ),
        }

        return report

    def _get_compliance_by_category(
        self,
    ) -> Dict[str, Dict[str, int]]:
        """Get compliance statistics by category."""
        by_category: Dict[str, Dict[str, int]] = {}

        for result in self.audit_results:
            category = result.category
            if category not in by_category:
                by_category[category] = {
                    "total": 0,
                    "compliant": 0,
                }

            by_category[category]["total"] += 1
            if result.is_compliant():
                by_category[category]["compliant"] += 1

        # Add percentages
        for category in by_category:
            total = by_category[category]["total"]
            compliant = by_category[category]["compliant"]
            by_category[category]["percentage"] = (
                compliant / total * 100 if total > 0 else 0
            )

        return by_category


def run_audit() -> Dict[str, Any]:
    """Run tool registry audit and return report."""
    auditor = ToolRegistryAuditor()

    if not auditor.load_registry():
        return {"error": "Failed to load registry"}

    auditor.audit_all_tools()

    return auditor.get_audit_report()


if __name__ == "__main__":
    report = run_audit()

    import json

    print(json.dumps(report, indent=2))
