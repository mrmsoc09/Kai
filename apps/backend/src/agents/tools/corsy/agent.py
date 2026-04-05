from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class CorsyAgent(BaseToolAgent):
    TOOL_NAME = "corsy"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # Test for CORS misconfigurations
        cmd = ["corsy", "-u", target]
        
        if opts.get("header"):
            cmd += ["-H", opts["header"]]
            
        if opts.get("threads"):
            cmd += ["-t", str(opts["threads"])]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        # Corsy output format usually identifies vulnerable headers: 
        # [!] Vulnerability: ... [Vulnerable Header: ...]
        if "[!]" in raw_output or "Vulnerability" in raw_output:
            findings.append({
                "type": "vulnerability",
                "value": target,
                "target": target,
                "severity": "medium",
                "confidence": 0.75,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": raw_output[:2000],
                "context": {
                    "vulnerability_type": "cors_misconfig",
                    "evidence": "Arbitrary origin reflection detected",
                },
                "recommended_next_tools": ["EvidenceAnalystAgent"],
                "recommended_next_actions": ["check_cors_exploitability"],
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        for item in findings:
            value = item["value"].lower()
            if f"{item['target'].lower()}|vulnerability|{value}" in known:
                noise.append(item)
                continue

            if item["context"].get("vulnerability_type") == "cors_misconfig":
                item["signal_reason"] = "origin_reflection_with_credentials"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "check_cors_exploitability",
            "target": target,
            "instructions": (
                "CORSy identified origin reflection. "
                "Trigger EvidenceAnalystAgent to check if sensitive data is returned "
                "with Access-Control-Allow-Credentials set to true."
            ),
        }
