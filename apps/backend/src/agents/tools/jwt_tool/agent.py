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
                "token": target,
                "value": target,
                "type": "jwt_vulnerability",
                "severity": "high",
                "evidence": "Token manipulation successful (e.g., none alg, key confusion)",
                "source": "jwt_tool",
                "target": target,
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            if item.get("type") == "jwt_vulnerability":
                item["signal_reason"] = "token_manipulation_vulnerability"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agent": "privilege_escalation_agent",
            "action": "test_privilege_escalation",
            "target": target,
            "instructions": (
                "JWT_Tool identified a vulnerability in token handling. "
                "Attempt to modify 'role' or 'user_id' claims in the JWT "
                "to escalate privileges horizontally or vertically."
            ),
        }
