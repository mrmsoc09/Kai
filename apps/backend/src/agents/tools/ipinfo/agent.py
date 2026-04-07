from __future__ import annotations

import json
import os
from typing import Any

from ..base_tool_agent import BaseToolAgent


class IpInfoAgent(BaseToolAgent):
    """IPInfo IP geolocation and hosting intelligence agent."""

    TOOL_NAME = "ipinfo"

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = os.environ.get("IPINFO_API_KEY", "")
        return [
            "python3",
            "-c",
            f"""
import requests, json
try:
    r = requests.get(
        f'https://ipinfo.io/{target}/json',
        params={{'token': '{api_key}'}},
        timeout=15
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

        if not isinstance(data, dict) or not data.get("ip"):
            return findings

        org = data.get("org", "")
        asn = org.split()[0] if org else ""

        cloud_providers = [
            "amazon",
            "google",
            "microsoft",
            "cloudflare",
            "fastly",
            "akamai",
        ]
        hosting = (
            "cloud" if any(p in org.lower() for p in cloud_providers) else "other"
        )

        findings.append(
            {
                "type": "ip_intelligence",
                "value": data.get("ip", ""),
                "target": target,
                "severity": "info",
                "confidence": 0.95,
                "source_tool": "ipinfo",
                "raw_evidence": str(data)[:500],
                "context": {
                    "org": org,
                    "asn": asn,
                    "city": data.get("city", ""),
                    "country": data.get("country", ""),
                    "hosting": hosting,
                },
                "recommended_next_tools": ["nmap", "masscan"],
                "recommended_next_actions": [
                    "correlate_asn_range",
                    "map_hosting_provider",
                ],
            }
        )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]], target: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal = []
        noise = []

        for f in findings:
            if f["context"].get("hosting") == "cloud":
                f["context"]["note"] = "Cloud hosted — WAF likely present"
            signal.append(f)

        return signal, noise

    def _generate_next_agent_instructions(
        self, result: dict[str, Any], target: str
    ) -> dict[str, Any]:
        return {
            "next_agents": ["nmap", "masscan"],
            "operator_summary": (
                f"IPInfo resolved {target} to ASN and hosting provider context."
            ),
        }
