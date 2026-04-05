from __future__ import annotations

from typing import Any


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
        results = self.aggregate_tool_results([], mission_context)
        return results

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
