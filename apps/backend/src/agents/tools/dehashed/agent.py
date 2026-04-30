from __future__ import annotations

import base64
import json
from typing import Any

from apps.backend.src.core.secret_manager import get_secret_manager
from ..base_tool_agent import BaseToolAgent


class DehashedAgent(BaseToolAgent):
    """Dehashed credential breach database agent."""

    TOOL_NAME = "dehashed"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(
        self, target: str, options: dict[str, Any] | None = None
    ) -> list[str]:
        api_key = get_secret_manager().get_optional("DEHASHED_API_KEY") or ""
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
                    "source_tool": self.TOOL_NAME,
                    # Deliberately avoid including password/hash values in evidence payload.
                    "raw_evidence": (
                        f"email={entry.get('email')} source={entry.get('database_name')}"
                    ),
                    "context": {
                        "database": entry.get("database_name", ""),
                        "breach_date": entry.get("obtained_from", ""),
                        "has_password": bool(entry.get("password")),
                        "has_hash": bool(entry.get("hashed_password")),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["document_exposure", "notify_program"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []

        for finding in findings:
            if finding.get("context", {}).get("has_password"):
                finding["severity"] = "critical"
            elif finding.get("context", {}).get("has_hash"):
                finding["severity"] = "high"
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        critical = [item for item in signal if item.get("severity") == "critical"]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "credential_count": len(signal),
            "critical_count": len(critical),
            "operator_summary": (
                f"Dehashed found {len(signal)} credential exposures for {target}. "
                f"{len(critical)} have plaintext passwords. Document only. "
                "Never use credentials."
            ),
        }
