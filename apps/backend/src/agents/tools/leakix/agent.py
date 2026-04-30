from __future__ import annotations

import json
from typing import Any

from apps.backend.src.core.secret_manager import get_secret_manager
from ..base_tool_agent import BaseToolAgent


class LeakIXAgent(BaseToolAgent):
    """LeakIX exposed service and leak indexing agent."""

    TOOL_NAME = "leakix"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = get_secret_manager().get_optional("LEAKIX_API_KEY") or ""
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
except Exception:
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

            leak_type = item.get("leak", "")
            findings.append(
                {
                    "type": "exposed_service",
                    "value": item.get("host", ""),
                    "target": target,
                    "severity": "high" if leak_type else "info",
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": str(item)[:500],
                    "context": {
                        "leak_type": leak_type,
                        "port": item.get("port", ""),
                        "protocol": item.get("protocol", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["investigate_leak"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []

        for finding in findings:
            if finding.get("context", {}).get("leak_type"):
                finding["severity"] = "high"
                finding["confidence"] = max(float(finding.get("confidence", 0.8)), 0.9)
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "operator_summary": (
                f"LeakIX found {len(signal)} exposed services for {target}. "
                "Leak findings require immediate responsible disclosure review."
            ),
        }
