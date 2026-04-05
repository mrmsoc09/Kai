from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SecretScannerAgent:
    """Coordinates Phase 6 secret scanning tool agents."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def execute(
        self,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        """Execute secret scanning phase."""
        try:
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
                            "SecretScannerAgent: %s",
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

        except Exception as e:
            logger.error(
                f"SecretScannerAgent failed: {e}", exc_info=True
            )
            return {
                "secret_scan_complete": False,
                "error": str(e),
                "verified_secrets": [],
                "unverified_secrets": [],
                "secret_count": 0,
            }

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
        return ["trufflehog", "gitleaks"]

    def get_execution_order(
        self,
        prior_findings: dict,
    ) -> list[list[str]]:
        return [["trufflehog", "gitleaks"]]

    def build_tool_context(
        self,
        tool_name: str,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        github_org = mission_context.get(
            "github_org",
            mission_context.get("target", "")
        )
        return {
            "target": f"https://github.com/{github_org}",
            "scan_id": mission_context.get("scan_id"),
            "mission_id": mission_context.get("mission_id"),
            "artifact_dir": mission_context.get(
                "artifact_dir"
            ),
            "timeout": 600,
            "prior_phase_findings": prior_findings,
        }

    def aggregate_tool_results(
        self,
        tool_results: list[dict],
        mission_context: dict,
    ) -> dict:
        secrets = {
            "secret_scan_complete": True,
            "verified_secrets": [],
            "unverified_secrets": [],
            "secret_count": 0,
        }
        for result in tool_results:
            for f in result.get("parsed_findings", []):
                if f.get("confidence", 0) >= 0.9:
                    secrets["verified_secrets"].append(f)
                else:
                    secrets["unverified_secrets"].append(f)
        secrets["secret_count"] = (
            len(secrets["verified_secrets"]) +
            len(secrets["unverified_secrets"])
        )
        if secrets["verified_secrets"]:
            secrets["escalate_immediately"] = True
            secrets["escalation_reason"] = (
                "Verified credentials found. "
                "Document only. Never use."
            )
        return secrets
