from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class OwaspZapAgent(BaseToolAgent):
    TOOL_NAME = "owasp-zap"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        timeout_secs = str(opts.get("timeout_seconds", 600))
        return [
            "zap-cli",
            "quick-scan",
            "--self-contained",
            "--timeout",
            timeout_secs,
            "--start-options",
            "-config api.disablekey=true",
            "-u",
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

        alerts = data.get("site", [{}])[0].get("alerts", [])
        if not isinstance(alerts, list):
            return findings

        for alert in alerts:
            if not isinstance(alert, dict):
                continue

            name = str(alert.get("name", ""))
            risk = str(alert.get("riskcode", "")).lower()

            risk_map = {"3": "high", "2": "medium", "1": "low", "0": "info"}
            severity = risk_map.get(risk, "info")

            if severity == "info":
                continue

            findings.append(
                {
                    "type": "web_vulnerability",
                    "value": name,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.85,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(alert)[:500],
                    "context": {
                        "risk": risk,
                        "description": alert.get("description", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["vulnerability_remediation"],
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
            key = f"{finding['target'].lower()}|zap|{finding['value'].lower()}"
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
        high = [f for f in signal if f.get("severity") == "high"]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "total_vulnerabilities": len(signal),
            "high_severity": len(high),
            "operator_summary": (
                f"OWASP ZAP identified {len(signal)} vulnerabilities on {target}. "
                f"High severity: {len(high)}. Active scan mode provides deep coverage."
            ),
        }
