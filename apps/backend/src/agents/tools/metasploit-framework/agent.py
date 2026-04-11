from __future__ import annotations

import re
from typing import Any

from ..base_tool_agent import BaseToolAgent


class MetasploitFrameworkAgent(BaseToolAgent):
    TOOL_NAME = "metasploit-framework"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        module = str(opts.get("module", "auxiliary/scanner/http/http_version"))
        return [
            "msfconsole",
            "-q",
            "-x",
            f"use {module}; set RHOSTS {target}; run; exit -y",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            text = line.strip()
            if not text:
                continue
            sev = "info"
            if re.search(r"\b(vulnerable|exploit|meterpreter|session opened)\b", text, re.I):
                sev = "high"
            findings.append(
                {
                    "type": "metasploit_result",
                    "value": text[:300],
                    "target": target,
                    "severity": sev,
                    "confidence": 0.8 if sev == "high" else 0.6,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": text[:1000],
                    "context": {"record_type": "console_line"},
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["manual_validation"],
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
            key = f"{finding['target'].lower()}|metasploit|{value}"
            if key in known:
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        high = [f for f in signal if str(f.get("severity", "")).lower() == "high"]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "high_signal_count": len(high),
            "operator_summary": (
                f"Metasploit produced {len(signal)} records for {target}. "
                f"High-signal lines: {len(high)}. Validate manually before escalation."
            ),
        }
