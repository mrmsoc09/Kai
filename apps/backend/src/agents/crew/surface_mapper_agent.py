from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SurfaceMapper:
    """
    Phase 1 surface mapping crew agent.

    Coordinates subfinder → amass → httpx_probe to build the initial
    attack surface (live subdomains, open ports, HTTP fingerprints).
    Results flow into OSINTIntelligenceAgent and downstream chain.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def execute(
        self,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        results = []
        errors = []

        for tool_name in self.get_execution_order():
            try:
                tool_context = self.build_tool_context(
                    tool_name, mission_context, prior_findings
                )
                if tool_context.get("skip"):
                    continue

                tool_agent = self._load_tool_agent(tool_name)
                if tool_agent is None:
                    errors.append(f"{tool_name}: agent not found")
                    continue

                result = tool_agent.execute(
                    target=tool_context.get(
                        "target", mission_context.get("target", "")
                    ),
                    options=tool_context,
                    mission_id=mission_context.get("mission_id", "mission-001"),
                )
                results.append({
                    "tool": tool_name,
                    "result": result,
                    "finding_count": len(result.findings),
                    "parsed_findings": [f.model_dump() for f in result.findings],
                })

            except Exception as e:
                logger.error(
                    "Tool agent %s failed in SurfaceMapper: %s", tool_name, str(e)
                )
                errors.append(f"{tool_name}: {str(e)}")

        aggregated = self.aggregate_tool_results(results, mission_context)
        aggregated["errors"] = errors
        aggregated["tools_executed"] = [r["tool"] for r in results]
        return aggregated

    def _load_tool_agent(self, tool_name: str) -> Any | None:
        module_name = tool_name.replace("-", "_")
        try:
            module = importlib.import_module(
                f"apps.backend.src.agents.tools.{module_name}.agent"
            )
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr_name.endswith("Agent")
                    and attr_name != "BaseToolAgent"
                ):
                    return attr()
            logger.warning("No agent class found in %s", module_name)
            return None
        except ImportError as e:
            logger.warning("Could not import tool agent %s: %s", tool_name, str(e))
            return None

    def get_execution_order(self) -> list[str]:
        return ["subfinder", "amass", "httpx_probe"]

    def build_tool_context(
        self,
        tool_name: str,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        return {
            "target": mission_context.get("target", ""),
            "scan_id": mission_context.get("scan_id"),
            "mission_id": mission_context.get("mission_id"),
            "artifact_dir": mission_context.get("artifact_dir"),
            "timeout": mission_context.get("timeout", 600),
            "prior_phase_findings": prior_findings,
        }

    def aggregate_tool_results(
        self,
        tool_results: list[dict],
        mission_context: dict,
    ) -> dict:
        subdomains: list[str] = []
        live_hosts: list[str] = []
        open_ports: list[dict] = []

        for tr in tool_results:
            for finding in tr.get("parsed_findings", []):
                value = finding.get("value", "")
                ftype = str(finding.get("finding_type", "")).lower()
                context = finding.get("raw_evidence", {}) or {}
                if "subdomain" in ftype or "subdomain" in str(context).lower():
                    if value and value not in subdomains:
                        subdomains.append(value)
                if "live" in ftype or tr["tool"] == "httpx_probe":
                    if value and value not in live_hosts:
                        live_hosts.append(value)
                if "port" in ftype:
                    open_ports.append({"host": value, "context": context})

        return {
            "surface_mapping_complete": True,
            "subdomains": subdomains,
            "live_hosts": live_hosts,
            "open_ports": open_ports,
            "total_surface_nodes": len(subdomains) + len(live_hosts),
        }
