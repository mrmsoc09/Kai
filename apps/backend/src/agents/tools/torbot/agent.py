from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class TorbotAgent(BaseToolAgent):
    TOOL_NAME = "torbot"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        return [
            "torbot",
            "--url",
            target,
            "--depth",
            "2",
            "--output",
            f"{artifact_dir}/torbot.json",
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

        results = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(results, list):
            return findings

        for entry in results:
            if not isinstance(entry, dict):
                continue

            url = str(entry.get("url", "")).strip()
            if not url:
                continue

            content = str(entry.get("content", "")).lower()
            target_lower = target.lower()
            has_org_mention = target_lower in content
            has_credential_pattern = any(
                pattern in content
                for pattern in ["password", "api_key", "token", "secret", "credential"]
            )

            if has_credential_pattern:
                severity = "critical"
            elif has_org_mention:
                severity = "high"
            else:
                severity = "medium"

            findings.append(
                {
                    "type": "dark_web_finding",
                    "value": url,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.85,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": content[:500],
                    "context": {
                        "has_org_mention": has_org_mention,
                        "has_credential_pattern": has_credential_pattern,
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["investigate_dark_web_exposure"],
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
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|dark_web|{value}" in known:
                noise.append(finding)
                continue

            if finding.get("context", {}).get("has_org_mention"):
                signal.append(finding)
            elif finding.get("context", {}).get("has_credential_pattern"):
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        credential_findings = [
            f
            for f in signal
            if f.get("context", {}).get("has_credential_pattern")
        ]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "credential_exposures": len(credential_findings),
            "total_dark_web_findings": len(signal),
            "operator_summary": (
                f"Torbot identified {len(signal)} dark web findings for {target}. "
                f"Credential exposures: {len(credential_findings)}. "
                "Requires manual verification of content authenticity."
            ),
        }
