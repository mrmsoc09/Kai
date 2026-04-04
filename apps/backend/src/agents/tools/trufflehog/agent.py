from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class TrufflehogAgent(BaseToolAgent):
    TOOL_NAME = "trufflehog"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        return [
            "trufflehog",
            "git",
            target,
            "--json",
            "--only-verified",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            secret_type = str(data.get("type", "unknown"))
            commit_hash = str(data.get("commit", ""))[:12]
            file_path = str(data.get("file", ""))

            findings.append(
                {
                    "type": "exposed_secret",
                    "value": f"{secret_type} in {file_path}",
                    "target": target,
                    "severity": "critical",
                    "confidence": 0.95,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(
                        {
                            "type": secret_type,
                            "file": file_path,
                            "commit": commit_hash,
                            "detector": data.get("detector_name", ""),
                        }
                    )[:500],
                    "context": {
                        "secret_type": secret_type,
                        "commit_hash": commit_hash,
                        "file_path": file_path,
                        "detector_name": data.get("detector_name", ""),
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
            "verified_secrets": len(signal),
            "operator_summary": (
                f"Trufflehog discovered {len(signal)} verified secrets in {target} git history. "
                "All findings are critical severity. Immediate credential rotation required."
            ),
        }
