from __future__ import annotations

from typing import Any


class APISecurityAgent:
    """Coordinates Phase 8 API and auth testing tool agents."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def execute(
        self,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        """Execute API security testing phase."""
        results = self.aggregate_tool_results([], mission_context)
        return results

    def get_tool_agents(self) -> list[str]:
        return [
            "jwt_tool", "kiterunner",
            "graphql-cop", "clairvoyance",
            "owasp-zap", "caido"
        ]

    def get_execution_order(
        self,
        prior_findings: dict,
    ) -> list[list[str]]:
        graphql = bool(
            prior_findings.get("graphql_endpoints", [])
        )
        if graphql:
            return [
                ["kiterunner", "jwt_tool", "owasp-zap"],
                ["graphql-cop"],
                ["clairvoyance"],
                ["caido"],
            ]
        return [
            ["kiterunner", "jwt_tool",
             "owasp-zap", "caido"],
        ]

    def build_tool_context(
        self,
        tool_name: str,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        graphql_eps = prior_findings.get("graphql_endpoints", [])
        base = {
            "target": mission_context.get("target"),
            "scan_id": mission_context.get("scan_id"),
            "mission_id": mission_context.get("mission_id"),
            "artifact_dir": mission_context.get(
                "artifact_dir"
            ),
            "rate_limit": mission_context.get(
                "rate_limit", 5
            ),
            "timeout": mission_context.get("timeout", 600),
            "api_config_path": mission_context.get(
                "api_config_path", ""
            ),
            "prior_phase_findings": prior_findings,
        }
        if tool_name in ("graphql-cop", "clairvoyance"):
            if graphql_eps:
                base["target"] = graphql_eps[0]
                base["graphql_endpoint"] = graphql_eps[0]
            else:
                base["skip"] = True
        return base

    def aggregate_tool_results(
        self,
        tool_results: list[dict],
        mission_context: dict,
    ) -> dict:
        return {
            "api_security_complete": True,
            "api_findings": [],
            "graphql_findings": [],
            "auth_findings": [],
        }
