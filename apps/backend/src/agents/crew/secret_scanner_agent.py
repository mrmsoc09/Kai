from __future__ import annotations

import logging
from typing import Any


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
            results = self.aggregate_tool_results([], mission_context)
            return results
        except Exception as e:
            logging.getLogger(__name__).error(
                f"SecretScannerAgent failed: {e}", exc_info=True
            )
            return {
                "secret_scan_complete": False,
                "error": str(e),
                "verified_secrets": [],
                "unverified_secrets": [],
                "secret_count": 0,
            }

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
