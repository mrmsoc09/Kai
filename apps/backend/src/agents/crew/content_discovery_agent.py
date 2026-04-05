from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContentDiscoveryAgent:
    """Coordinates Phase 3 content discovery tool agents."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def execute(
        self,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        """Execute content discovery phase."""
        results = []
        errors = []

        execution_groups = self.get_execution_order(
            prior_findings
        )

        for group in execution_groups:
            group_results = []
            for tool_name in group:
                try:
                    tool_context = self.build_tool_context(
                        tool_name,
                        mission_context,
                        prior_findings,
                    )

                    # Check if tool should be skipped
                    if tool_context.get("skip"):
                        continue

                    # Import and instantiate the tool agent
                    tool_agent = self._load_tool_agent(
                        tool_name
                    )
                    if tool_agent is None:
                        errors.append(
                            f"{tool_name}: agent not found"
                        )
                        continue

                    # Execute the tool agent
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
                    group_results.append({
                        "tool": tool_name,
                        "result": result,
                        "finding_count": len(result.findings),
                        "high_value_findings": [
                            f.model_dump()
                            for f in result.findings
                            if f.severity
                            in ("critical", "high")
                        ],
                        "parsed_findings": [
                            f.model_dump()
                            for f in result.findings
                        ],
                    })

                except Exception as e:
                    logger.error(
                        "Tool agent %s failed in "
                        "ContentDiscoveryAgent: %s",
                        tool_name,
                        str(e),
                    )
                    errors.append(
                        f"{tool_name}: {str(e)}"
                    )
                    continue

            results.extend(group_results)

        aggregated = self.aggregate_tool_results(
            results, mission_context
        )
        aggregated["errors"] = errors
        aggregated["tools_executed"] = [
            r["tool"] for r in results
        ]
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
        return [
            "feroxbuster", "katana", "paramspider",
            "arjun", "hakrawler", "ffuf", "gf"
        ]

    def get_execution_order(
        self,
        prior_findings: dict,
    ) -> list[list[str]]:
        return [
            ["feroxbuster", "katana",
             "hakrawler", "paramspider"],
            ["arjun", "ffuf"],
            ["gf"],
        ]

    def build_tool_context(
        self,
        tool_name: str,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        live_hosts = prior_findings.get("live_hosts", [])
        waf = prior_findings.get("waf_detected", False)
        base = {
            "target": (
                live_hosts[0] if live_hosts
                else mission_context.get("target")
            ),
            "scan_id": mission_context.get("scan_id"),
            "mission_id": mission_context.get("mission_id"),
            "artifact_dir": mission_context.get(
                "artifact_dir"
            ),
            "rate_limit": 2 if waf else 10,
            "timeout": mission_context.get("timeout", 600),
            "api_config_path": mission_context.get(
                "api_config_path", ""
            ),
            "prior_phase_findings": prior_findings,
        }
        if tool_name == "gf":
            base["combined_urls_file"] = (
                f"{mission_context['artifact_dir']}"
                "/combined_urls.txt"
            )
        return base

    def aggregate_tool_results(
        self,
        tool_results: list[dict],
        mission_context: dict,
    ) -> dict:
        return {
            "content_discovery_complete": True,
            "discovered_paths": [],
            "parameterized_urls": [],
            "graphql_endpoints": [],
            "categorized_params": {
                "sqli": [], "xss": [],
                "ssrf": [], "redirect": [],
            },
            "js_files": [],
        }
