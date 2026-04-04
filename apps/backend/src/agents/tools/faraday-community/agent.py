from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..base_tool_agent import BaseToolAgent


class FaradaycommunityAgent(BaseToolAgent):
    TOOL_NAME = "faraday-community"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        return []

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        return []

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for finding in findings:
            key = f"{finding['target'].lower()}|aggregated|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            signal.append(finding)

        return signal, noise

    def aggregate_findings(
        self,
        handoff_report_paths: list[str],
        artifact_dir: str,
    ) -> dict[str, Any]:
        """Aggregate findings from multiple agents, deduplicate, and boost confidence."""
        all_findings: list[dict[str, Any]] = []

        for path_str in handoff_report_paths:
            p = Path(path_str)
            if not p.exists():
                continue
            try:
                report = json.loads(p.read_text())
                all_findings.extend(report.get("high_value_findings", []))
            except Exception:
                continue

        seen: dict[tuple[str, str, str], dict[str, Any]] = {}
        for finding in all_findings:
            key = (
                finding.get("type", ""),
                finding.get("value", ""),
                finding.get("target", ""),
            )
            if key in seen:
                existing = seen[key]
                existing["confidence"] = min(
                    existing.get("confidence", 0.5) + 0.1, 1.0
                )
                existing.setdefault("confirmed_by", []).append(
                    finding.get("source_tool", "unknown")
                )
            else:
                entry = finding.copy()
                entry["confirmed_by"] = [finding.get("source_tool", "unknown")]
                seen[key] = entry

        deduplicated = list(seen.values())

        master_path = f"{artifact_dir}/master_findings.json"
        Path(master_path).parent.mkdir(parents=True, exist_ok=True)
        Path(master_path).write_text(json.dumps(deduplicated, indent=2))

        return {
            "master_findings_path": master_path,
            "total_findings": len(deduplicated),
            "high_confidence": len([f for f in deduplicated if f.get("confidence", 0) > 0.85]),
            "multi_tool_confirmed": len([f for f in deduplicated if len(f.get("confirmed_by", [])) > 1]),
        }

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "aggregated_findings": len(signal),
            "operator_summary": (
                f"Faraday aggregated {len(signal)} findings from all Wave 3 agents for {target}. "
                "Deduplicated and boosted confidence for multi-tool confirmed discoveries. "
                "Master findings written to master_findings.json."
            ),
        }
