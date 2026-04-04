from __future__ import annotations

import json
import shutil
from typing import Any

from ..base_tool_agent import BaseToolAgent


class CaidoAgent(BaseToolAgent):
    TOOL_NAME = "caido"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        if not shutil.which("caido"):
            return []

        return [
            "caido",
            "scan",
            "--target",
            target,
            "--output",
            f"{artifact_dir}/caido.json",
            "--timeout",
            "300",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        if not raw_output.strip():
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        issues = data.get("issues", [])
        if not isinstance(issues, list):
            return findings

        for issue in issues:
            if not isinstance(issue, dict):
                continue

            title = str(issue.get("title", ""))
            severity = str(issue.get("severity", "")).lower()

            findings.append(
                {
                    "type": "proxy_finding",
                    "value": title,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(issue)[:500],
                    "context": {
                        "issue_type": issue.get("type", ""),
                        "evidence": issue.get("evidence", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["issue_validation"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for finding in findings:
            key = f"{finding['target'].lower()}|caido|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "proxy_findings": len(signal),
            "operator_summary": (
                f"Caido proxy analyzer found {len(signal)} issues on {target}. "
                "Modern proxy-based approach complements traditional scanners."
            ),
        }
