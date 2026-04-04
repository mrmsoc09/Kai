from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class GitleaksAgent(BaseToolAgent):
    TOOL_NAME = "gitleaks"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        return [
            "gitleaks",
            "detect",
            "--source",
            target,
            "--report-format",
            "json",
            "--report-path",
            f"{artifact_dir}/gitleaks.json",
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

        results = data if isinstance(data, list) else data.get("results", [])
        if not isinstance(results, list):
            return findings

        for entry in results:
            if not isinstance(entry, dict):
                continue

            rule_id = str(entry.get("Rule", ""))
            file_path = str(entry.get("File", ""))
            commit = str(entry.get("Commit", ""))[:12]
            secret_type = rule_id.lower()

            is_test_fixture = any(
                marker in file_path.lower()
                for marker in ["test", "fixture", "fake", "mock", "example"]
            )

            if is_test_fixture:
                continue

            findings.append(
                {
                    "type": "exposed_secret",
                    "value": f"{rule_id} in {file_path}",
                    "target": target,
                    "severity": "critical",
                    "confidence": 0.9,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(
                        {
                            "rule": rule_id,
                            "file": file_path,
                            "commit": commit,
                        }
                    )[:500],
                    "context": {
                        "rule_id": rule_id,
                        "file_path": file_path,
                        "commit_hash": commit,
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["credential_rotation", "incident_response"],
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
            key = f"{finding['target'].lower()}|secret|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "detected_secrets": len(signal),
            "operator_summary": (
                f"Gitleaks identified {len(signal)} secret patterns in {target} source. "
                "All findings are critical. Complementary coverage to trufflehog via different ruleset."
            ),
        }
