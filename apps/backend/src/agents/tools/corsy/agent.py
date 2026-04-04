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
                "url": target,
                "value": target,
                "type": "cors_misconfig",
                "severity": "medium",
                "evidence": "Arbitrary origin reflection detected",
                "source": "corsy",
                "target": target,
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            if item.get("type") == "cors_misconfig":
                item["signal_reason"] = "origin_reflection_with_credentials"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agent": "vulnerability_validator",
            "action": "check_cors_exploitability",
            "target": target,
            "instructions": (
                "CORSy identified origin reflection. "
                "Check if the endpoint returns sensitive data (PII, tokens) "
                "and if 'Access-Control-Allow-Credentials: true' is set. "
                "Without credentials or sensitive data, this remains informational."
            ),
        }
