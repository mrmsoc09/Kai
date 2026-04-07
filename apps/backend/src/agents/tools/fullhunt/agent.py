from __future__ import annotations

import json
import os
from typing import Any

from ..base_tool_agent import BaseToolAgent


class FullHuntAgent(BaseToolAgent):
    """FullHunt attack surface intelligence agent."""

    TOOL_NAME = "fullhunt"

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = os.environ.get("FULLHUNT_API_KEY", "")
        return [
            "python3",
            "-c",
            f"""
import requests, json, sys
headers = {{'X-API-KEY': '{api_key}'}}
try:
    r = requests.get(
        'https://fullhunt.io/api/v1/domain/subdomains',
        params={{'domain': '{target}'}},
        headers=headers,
        timeout=30
    )
    print(json.dumps(r.json() if r.ok else {{}}, default=str))
except Exception as e:
    print(json.dumps({{}}, default=str))
""",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        try:
            data = json.loads(raw_output.strip())
        except (json.JSONDecodeError, TypeError):
            return findings

        if not isinstance(data, dict):
            return findings

        hosts = data.get("hosts", [])
        for host in hosts:
            if not isinstance(host, dict):
                continue

            findings.append(
                {
                    "type": "subdomain",
                    "value": host.get("host", ""),
                    "target": target,
                    "severity": "info",
                    "confidence": 0.85,
                    "source_tool": "fullhunt",
                    "raw_evidence": str(host)[:500],
                    "context": {
                        "ip": host.get("ip", ""),
                        "cdn": host.get("cdn", False),
                        "cloud": host.get("cloud", {}),
                        "ports": host.get("ports", []),
                    },
                    "recommended_next_tools": ["dnsx", "httpx_probe"],
                    "recommended_next_actions": [
                        "resolve_dns",
                        "probe_http",
                    ],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]], target: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal = []
        noise = []
        high_value = [
            "admin",
            "api",
            "dev",
            "staging",
            "internal",
            "backend",
            "portal",
        ]

        for f in findings:
            val = f["value"].lower()
            if any(p in val for p in high_value):
                f["severity"] = "medium"
                f["confidence"] = 0.9
                signal.append(f)
            elif f["context"].get("ports"):
                signal.append(f)
            else:
                signal.append(f)

        return signal, noise

    def _generate_next_agent_instructions(
        self, result: dict[str, Any], target: str
    ) -> dict[str, Any]:
        finding_count = len(result.get("findings", []))
        return {
            "next_agents": ["dnsx", "httpx_probe"],
            "operator_summary": (
                f"FullHunt found {finding_count} hosts for {target} "
                f"with port and cloud context."
            ),
        }
