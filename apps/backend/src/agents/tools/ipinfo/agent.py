from __future__ import annotations

import json
from typing import Any

from apps.backend.src.core.secret_manager import get_secret_manager
from ..base_tool_agent import BaseToolAgent


class IpInfoAgent(BaseToolAgent):
    """IPInfo IP geolocation and hosting intelligence agent."""

    TOOL_NAME = "ipinfo"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = get_secret_manager().get_optional("IPINFO_API_KEY") or ""
        return [
            "python3",
            "-c",
            f"""
import requests, json
try:
    r = requests.get(
        'https://ipinfo.io/{target}/json',
        params={{'token': '{api_key}'}},
        timeout=15
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

        if not isinstance(data, dict) or not data.get("ip"):
            return findings

        org = data.get("org", "")
        asn = org.split()[0] if org else ""

        cloud_providers = ["amazon", "google", "microsoft", "cloudflare", "fastly", "akamai"]
        hosting = "cloud" if any(provider in org.lower() for provider in cloud_providers) else "other"

        findings.append(
            {
                "type": "ip_intelligence",
                "value": data.get("ip", ""),
                "target": target,
                "severity": "info",
                "confidence": 0.95,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": str(data)[:500],
                "context": {
                    "org": org,
                    "asn": asn,
                    "city": data.get("city", ""),
                    "country": data.get("country", ""),
                    "hosting": hosting,
                },
                "recommended_next_tools": ["nmap", "masscan"],
                "recommended_next_actions": ["correlate_asn_range", "map_hosting_provider"],
            }
        )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []

        for finding in findings:
            if finding.get("context", {}).get("hosting") == "cloud":
                finding.setdefault("context", {})["note"] = "Cloud hosted - WAF likely present"
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agents": ["nmap", "masscan"],
            "operator_summary": (
                f"IPInfo resolved {target} to ASN and hosting provider context."
            ),
        }
