from __future__ import annotations

import base64
import json
import os
from typing import Any

from ..base_tool_agent import BaseToolAgent


class DehashedAgent(BaseToolAgent):
    """Dehashed credential breach database agent."""

    TOOL_NAME = "dehashed"

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = os.environ.get("DEHASHED_API_KEY", "")
        creds = base64.b64encode(f"username:{api_key}".encode()).decode()
        return [
            "python3",
            "-c",
            f"""
import requests, json
headers = {{
    'Authorization': 'Basic {creds}',
    'Accept': 'application/json'
}}
try:
    r = requests.get(
        'https://api.dehashed.com/search',
        params={{'query': 'domain:{target}', 'size': 100}},
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

        entries = data.get("entries", [])
        if not isinstance(entries, list):
            return findings

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            findings.append(
                {
                    "type": "credential_exposure",
                    "value": entry.get("email", ""),
                    "target": target,
                    "severity": "high",
                    "confidence": 0.9,
                    "source_tool": "dehashed",
                    "raw_evidence": (
                        f"email={entry.get('email')} "
                        f"source={entry.get('database_name')}"
                    ),
                    "context": {
                        "database": entry.get("database_name", ""),
                        "breach_date": entry.get("obtained_from", ""),
                        "has_password": bool(entry.get("password")),
                        "has_hash": bool(entry.get("hashed_password")),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": [
                        "document_exposure",
                        "notify_program",
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
            if f["context"].get("has_password"):
                f["severity"] = "critical"
                signal.append(f)
            elif f["context"].get("has_hash"):
                f["severity"] = "high"
                signal.append(f)
            else:
                signal.append(f)

        return signal, noise

    def _generate_next_agent_instructions(
        self, result: dict[str, Any], target: str
    ) -> dict[str, Any]:
        findings = result.get("findings", [])
        critical = [f for f in findings if f.get("severity") == "critical"]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "credential_count": len(findings),
            "critical_count": len(critical),
            "operator_summary": (
                f"Dehashed found {len(findings)} credential exposures for {target}. "
                f"{len(critical)} have plaintext passwords. Document only. "
                f"Never use credentials."
            ),
        }
