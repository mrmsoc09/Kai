from __future__ import annotations

import json
from typing import Any

from apps.backend.src.core.secret_manager import get_secret_manager
from ..base_tool_agent import BaseToolAgent


class FullHuntAgent(BaseToolAgent):
    """FullHunt attack surface intelligence agent."""

    TOOL_NAME = "fullhunt"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = get_secret_manager().get_optional("FULLHUNT_API_KEY") or ""
        return [
            "python3",
            "-c",
            f"""
import requests, json
headers = {{'X-API-KEY': '{api_key}'}}
try:
    r = requests.get(
        'https://fullhunt.io/api/v1/domain/subdomains',
        params={{'domain': '{target}'}},
        headers=headers,
        timeout=30
    )
    print(json.dumps(r.json() if r.ok else {{}}, default=str))
except Exception:
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
        if not isinstance(hosts, list):
            return findings

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
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": str(host)[:500],
                    "context": {
                        "ip": host.get("ip", ""),
                        "cdn": host.get("cdn", False),
                        "cloud": host.get("cloud", {}),
                        "ports": host.get("ports", []),
                    },
                    "recommended_next_tools": ["dnsx", "httpx_probe"],
                    "recommended_next_actions": ["resolve_dns", "probe_http"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        high_value = [
            "admin",
            "api",
            "dev",
            "staging",
            "internal",
            "backend",
            "portal",
        ]

        for finding in findings:
            value = str(finding.get("value", "")).lower()
            ports = finding.get("context", {}).get("ports", [])
            if any(token in value for token in high_value):
                finding["severity"] = "medium"
                finding["confidence"] = 0.9
            if ports:
                finding["confidence"] = max(float(finding.get("confidence", 0.85)), 0.9)
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agents": ["dnsx", "httpx_probe"],
            "operator_summary": (
                f"FullHunt found {len(signal)} hosts for {target} with port "
                f"and cloud context."
            ),
        }
