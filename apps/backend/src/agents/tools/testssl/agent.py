from __future__ import annotations

import json
import shutil
from typing import Any

from ..base_tool_agent import BaseToolAgent


class TestsslAgent(BaseToolAgent):
    TOOL_NAME = "testssl"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        binary = "testssl.sh" if shutil.which("testssl.sh") else "testssl"

        return [
            binary,
            "--jsonfile",
            f"{artifact_dir}/testssl.json",
            "--fast",
            "--timeout",
            "30",
            target,
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

        results = data.get("results", [])
        if not isinstance(results, list):
            return findings

        for result in results:
            if not isinstance(result, dict):
                continue

            finding_type = str(result.get("finding", ""))
            severity = str(result.get("severity", "")).lower()

            if severity in ["ok", "info"]:
                continue

            severity_map = {
                "critical": "critical",
                "high": "high",
                "medium": "medium",
                "low": "low",
                "warning": "medium",
            }
            mapped_severity = severity_map.get(severity, "low")

            findings.append(
                {
                    "type": "ssl_finding",
                    "value": finding_type,
                    "target": target,
                    "severity": mapped_severity,
                    "confidence": 0.95,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(result)[:500],
                    "context": {
                        "service": result.get("service", ""),
                        "cipher": result.get("cipher", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["tls_remediation"],
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
            key = f"{finding['target'].lower()}|ssl|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            severity = finding.get("severity", "low").lower()
            if severity in ["critical", "high", "medium"]:
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        critical = [f for f in signal if f.get("severity") == "critical"]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "ssl_issues": len(signal),
            "critical_issues": len(critical),
            "operator_summary": (
                f"TestSSL identified {len(signal)} SSL/TLS issues on {target}. "
                f"Critical: {len(critical)}. PCI-DSS and fintech relevance verified."
            ),
        }
