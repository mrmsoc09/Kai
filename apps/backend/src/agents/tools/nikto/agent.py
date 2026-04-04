from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class NiktoAgent(BaseToolAgent):
    TOOL_NAME = "nikto"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        waf_detected = bool(opts.get("waf_detected", False))

        cmd = [
            "nikto",
            "-h",
            target,
            "-o",
            f"{artifact_dir}/nikto.json",
            "-Format",
            "json",
            "-Tuning",
            "1234569",
            "-maxtime",
            "300",
            "-timeout",
            "10",
        ]
        if waf_detected:
            cmd.extend(["-evasion", "1"])
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        vulnerabilities = data.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            return findings

        for vuln in vulnerabilities:
            if not isinstance(vuln, dict):
                continue

            osvdb_id = str(vuln.get("id", ""))
            title = str(vuln.get("title", ""))
            uri = str(vuln.get("uri", ""))

            severity_map = {
                "1": "critical",
                "2": "high",
                "3": "medium",
                "4": "low",
            }
            severity = severity_map.get(str(vuln.get("severity", "4")), "low")

            findings.append(
                {
                    "type": "vulnerability_finding",
                    "value": title,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": uri[:500],
                    "context": {
                        "osvdb_id": osvdb_id,
                        "uri": uri,
                        "method": vuln.get("method", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent", "nuclei_scan"],
                    "recommended_next_actions": ["vulnerability_validation"],
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
            key = f"{finding['target'].lower()}|vuln|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            severity = finding.get("severity", "low").lower()
            if severity in ["critical", "high"]:
                signal.append(finding)
            elif severity == "medium":
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
        high = [f for f in signal if f.get("severity") == "high"]
        return {
            "next_agents": ["EvidenceAnalystAgent", "nuclei_scan"],
            "critical_vulns": len(critical),
            "high_vulns": len(high),
            "operator_summary": (
                f"Nikto found {len(signal)} vulnerabilities on {target}. "
                f"Critical: {len(critical)}, High: {len(high)}."
            ),
        }
