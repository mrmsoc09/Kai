from __future__ import annotations

import json
import os
from typing import Any

from ..base_tool_agent import BaseToolAgent


class LeakIXAgent(BaseToolAgent):
    """LeakIX exposed service and leak indexing agent."""

    TOOL_NAME = "leakix"

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = os.environ.get("LEAKIX_API_KEY", "")
        return [
            "python3",
            "-c",
            f"""
import requests, json
headers = {{'api-key': '{api_key}'}}
try:
    r = requests.get(
        'https://leakix.net/api/subdomains/{target}',
        headers=headers,
        timeout=30
    )
    print(json.dumps(r.json() if r.ok else [], default=str))
except Exception as e:
    print(json.dumps([], default=str))
""",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        try:
            data = json.loads(raw_output.strip())
        except (json.JSONDecodeError, TypeError):
            return findings

        if not isinstance(data, list):
            return findings

        for item in data:
            if not isinstance(item, dict):
                continue

            severity = "info"
            if item.get("leak"):
                severity = "high"

            findings.append(
                {
                    "type": "exposed_service",
                    "value": item.get("host", ""),
                    "target": target,
                    "severity": severity,
                    "confidence": 0.8,
                    "source_tool": "leakix",
                    "raw_evidence": str(item)[:500],
                    "context": {
                        "leak_type": item.get("leak", ""),
                        "port": item.get("port", ""),
                        "protocol": item.get("protocol", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["investigate_leak"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]], target: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal = []
        noise = []

        for f in findings:
            if f["context"].get("leak_type"):
                f["severity"] = "high"
                signal.append(f)
            else:
                signal.append(f)

        return signal, noise

    def _generate_next_agent_instructions(
        self, result: dict[str, Any], target: str
    ) -> dict[str, Any]:
        finding_count = len(result.get("findings", []))
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "operator_summary": (
                f"LeakIX found {finding_count} exposed services for {target}. "
                f"Leak findings require immediate responsible disclosure review."
            ),
        }
