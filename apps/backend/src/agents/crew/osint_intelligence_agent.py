from __future__ import annotations

from typing import Any


class OSINTIntelligenceAgent:
    """Coordinates Phase 4 OSINT tool agents."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def execute(
        self,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        """Execute OSINT intelligence phase."""
        results = self.aggregate_tool_results([], mission_context)
        return results

    def get_tool_agents(self) -> list[str]:
        return [
            "spiderfoot", "sherlock",
            "phoneinfoga", "social-analyzer", "reconftw"
        ]

    def get_execution_order(
        self,
        prior_findings: dict,
    ) -> list[list[str]]:
        return [[
            "spiderfoot", "sherlock",
            "phoneinfoga", "social-analyzer", "reconftw"
        ]]

    def build_tool_context(
        self,
        tool_name: str,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        base = {
            "target": mission_context.get("target"),
            "target_type": mission_context.get(
                "target_type", "domain"
            ),
            "scan_id": mission_context.get("scan_id"),
            "mission_id": mission_context.get("mission_id"),
            "artifact_dir": mission_context.get(
                "artifact_dir"
            ),
            "rate_limit": mission_context.get(
                "rate_limit", 5
            ),
            "timeout": mission_context.get("timeout", 300),
            "api_config_path": mission_context.get(
                "api_config_path", ""
            ),
            "prior_phase_findings": prior_findings,
        }
        if tool_name == "spiderfoot":
            base["org_name"] = mission_context.get(
                "org_name",
                mission_context.get("target", "")
            )
        elif tool_name == "sherlock":
            base["usernames"] = prior_findings.get(
                "discovered_usernames", []
            )
        return base

    def aggregate_tool_results(
        self,
        tool_results: list[dict],
        mission_context: dict,
    ) -> dict:
        intel = {
            "osint_complete": True,
            "credential_exposures": [],
            "employee_profiles": [],
            "social_accounts": [],
            "org_intelligence": {},
        }
        for result in tool_results:
            for f in result.get("high_value_findings", []):
                ftype = f.get("type", "")
                sev = f.get("severity", "")
                if "credential" in ftype.lower() \
                   or sev == "critical":
                    intel["credential_exposures"].append(f)
                elif "social_profile" in ftype:
                    intel["social_accounts"].append(f)
                else:
                    intel["org_intelligence"].setdefault(
                        "findings", []
                    ).append(f)
        return intel
