from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class JwtToolAgent(BaseToolAgent):
    TOOL_NAME = "jwt_tool"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # JWT_Tool for token manipulation
        # target is the JWT token string
        cmd = ["jwt_tool", target]
        
        if opts.get("attack_mode"):
            # -M at: run all attack tests
            cmd += ["-M", "at"]
            
        if opts.get("key"):
            cmd += ["-k", opts["key"]]
            
        if opts.get("none_alg"):
            # -X a: test for none algorithm
            cmd += ["-X", "a"]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        # Parse for successful attack indicators
        if "[+]" in raw_output or "VULNERABILITY" in raw_output:
            findings.append({
                "type": "vulnerability",
                "value": target,
                "target": target,
                "severity": "high",
                "confidence": 0.85,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": raw_output[:2000],
                "context": {
                    "vulnerability_type": "jwt_vulnerability",
                    "evidence": "Token manipulation successful (e.g., none alg, key confusion)",
                    "token": target,
                },
                "recommended_next_tools": ["EvidenceAnalystAgent"],
                "recommended_next_actions": ["validate_jwt"],
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

            if item["context"].get("vulnerability_type") == "jwt_vulnerability":
                item["signal_reason"] = "token_manipulation_vulnerability"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "test_privilege_escalation",
            "target": target,
            "instructions": (
                "JWT_Tool identified a vulnerability in token handling. "
                "Trigger EvidenceAnalystAgent to test for horizontal or vertical privilege escalation."
            ),
        }
