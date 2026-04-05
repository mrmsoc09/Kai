from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class FaradayCoordinatorAgent:
    """Coordinates Phase 9 aggregation."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def execute(
        self,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        """Execute aggregation phase."""
        results = []
        errors = []

        # Faraday is special — it aggregates handoff
        # reports from prior phases, not tool agents
        handoff_paths = prior_findings.get(
            "all_handoff_report_paths", []
        )

        # Try to load and use FaradayAgent
        try:
            tool_agent = self._load_tool_agent(
                "faraday-community"
            )
            if tool_agent is None:
                errors.append(
                    "faraday-community: agent not found"
                )
            else:
                # Build context for Faraday
                tool_context = self.build_tool_context(
                    "faraday-community",
                    mission_context,
                    prior_findings,
                )

                # Execute Faraday agent
                result = tool_agent.execute(
                    target=tool_context.get(
                        "target",
                        mission_context.get("target", "")
                    ),
                    options=tool_context,
                    mission_id=mission_context.get(
                        "mission_id",
                        "mission-001"
                    ),
                )
                results.append({
                    "tool": "faraday-community",
                    "result": result,
                    "finding_count": len(result.findings),
                    "high_value_findings": [
                        f.model_dump()
                        for f in result.findings
                        if f.severity in ("critical", "high")
                    ],
                    "parsed_findings": [
                        f.model_dump()
                        for f in result.findings
                    ],
                })

        except Exception as e:
            logger.error(
                "Faraday aggregation failed: %s", str(e)
            )
            errors.append(f"faraday-community: {str(e)}")

        # Aggregate all collected findings
        aggregated = self.aggregate_tool_results(
            results, mission_context
        )
        aggregated["errors"] = errors
        aggregated["tools_executed"] = [
            r["tool"] for r in results
        ]
        aggregated["handoff_reports_processed"] = (
            len(handoff_paths)
        )
        return aggregated

    def _load_tool_agent(self, tool_name: str):
        """
        Dynamically load a tool agent by name.
        Returns None if agent cannot be loaded.
        """
        # Normalize tool name to module name
        module_name = tool_name.replace("-", "_")

        try:
            module = importlib.import_module(
                f"apps.backend.src.agents.tools.{module_name}.agent"
            )
            # Find the agent class
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr_name.endswith("Agent")
                    and attr_name != "BaseToolAgent"
                ):
                    return attr()
            logger.warning(
                "No agent class found in %s", module_name
            )
            return None
        except ImportError as e:
            logger.warning(
                "Could not import tool agent %s: %s",
                tool_name, str(e)
            )
            return None

    def get_tool_agents(self) -> list[str]:
        return ["faraday-community"]

    def get_execution_order(
        self,
        prior_findings: dict,
    ) -> list[list[str]]:
        return [["faraday-community"]]

    def build_tool_context(
        self,
        tool_name: str,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        return {
            "target": mission_context.get("target"),
            "scan_id": mission_context.get("scan_id"),
            "mission_id": mission_context.get("mission_id"),
            "artifact_dir": mission_context.get(
                "artifact_dir"
            ),
            "timeout": 300,
            "handoff_report_paths": prior_findings.get(
                "all_handoff_report_paths", []
            ),
            "prior_phase_findings": prior_findings,
        }

    def aggregate_tool_results(
        self,
        tool_results: list[dict],
        mission_context: dict,
    ) -> dict:
        master = []
        for result in tool_results:
            master.extend(
                result.get("parsed_findings", [])
            )
        return {
            "aggregation_complete": True,
            "master_findings": master,
            "master_findings_count": len(master),
            "master_findings_path": (
                f"{mission_context.get('artifact_dir', '')}"
                "/master_findings.json"
            ),
        }
