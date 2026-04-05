from __future__ import annotations

from typing import Any


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
        results = self.aggregate_tool_results([], mission_context)
        return results

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
