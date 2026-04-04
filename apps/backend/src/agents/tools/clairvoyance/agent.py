from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class ClairvoyanceAgent(BaseToolAgent):
    TOOL_NAME = "clairvoyance"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        endpoint = str(opts.get("graphql_endpoint", target))
        wordlist = (
            "/usr/share/seclists/Discovery/Web-Content/graphql.txt"
        )
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        return [
            "clairvoyance",
            "-u",
            endpoint,
            "-w",
            wordlist,
            "-o",
            f"{artifact_dir}/clairvoyance.json",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        recovered_fields = data.get("fields", [])
        if not isinstance(recovered_fields, list):
            return findings

        sensitive_keywords = {
            "password",
            "token",
            "secret",
            "admin",
            "internal",
            "key",
            "private",
            "credential",
        }

        for field_name in recovered_fields:
            field_lower = str(field_name).lower()
            is_sensitive = any(kw in field_lower for kw in sensitive_keywords)

            severity = "medium" if is_sensitive else "low"
            severity = "high" if "admin" in field_lower or "internal" in field_lower else severity

            findings.append(
                {
                    "type": "graphql_schema_recovery",
                    "value": field_name,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.85,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps({"recovered_field": field_name})[:500],
                    "context": {
                        "is_sensitive": is_sensitive,
                        "field_name": field_name,
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["schema_analysis"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        common_fields = {"id", "name", "email", "created_at", "updated_at"}

        for finding in findings:
            key = f"{finding['target'].lower()}|graphql|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            field_name = str(finding.get("value", "")).lower()
            if field_name in common_fields:
                noise.append(finding)
            elif finding.get("context", {}).get("is_sensitive"):
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        sensitive = [f for f in signal if f.get("context", {}).get("is_sensitive")]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "recovered_fields": len(signal),
            "sensitive_fields": len(sensitive),
            "operator_summary": (
                f"Clairvoyance recovered {len(signal)} schema fields from {target}. "
                f"Sensitive field discovery: {len(sensitive)}. "
                "Schema recovery successful when introspection disabled."
            ),
        }
