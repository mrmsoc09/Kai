from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class SqlmapAgent(BaseToolAgent):
    TOOL_NAME = "sqlmap"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # STRICT SAFE MODE for BBP: --level=2, --risk=1, --batch, NO --dump
        cmd = ["sqlmap", "-u", target, "--batch", "--level", "2", "--risk", "1"]
        
        # Mandatory exclusion of destructive options
        if opts.get("dump") or "--dump" in str(opts):
            # In a real environment, this would be blocked by a governance layer.
            # Here, we simply ensure it's not added.
            pass
            
        # Focus on boolean-based blind detection only for maximum stability
        if opts.get("boolean_only", True):
            cmd += ["--technique", "B"]
            
        if opts.get("random_agent", True):
            cmd.append("--random-agent")
            
        if opts.get("threads"):
            cmd += ["--threads", str(opts["threads"])]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        # Sqlmap output parsing is complex; usually depends on -o or log file.
        # Here we parse for basic 'vulnerable' keywords in stdout.
        findings: list[dict[str, Any]] = []
        if "is vulnerable" in raw_output or "Payload:" in raw_output:
            findings.append({
                "type": "vulnerability",
                "value": target,
                "target": target,
                "severity": "critical",
                "confidence": 0.9,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": raw_output[:2000],
                "context": {
                    "vulnerability_type": "sql_injection",
                    "evidence": "Boolean-based blind / Time-based blind detected",
                },
                "recommended_next_tools": ["EvidenceAnalystAgent"],
                "recommended_next_actions": ["validate_sqli"],
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

            if item["context"].get("vulnerability_type") == "sql_injection":
                item["signal_reason"] = "confirmed_sqli"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "confirm_sqli_blind",
            "target": target,
            "instructions": (
                "SQLMap detected a potential blind SQL injection. "
                "Trigger EvidenceAnalystAgent for further automated confirmation "
                "or manual human review if confidence is high."
            ),
        }
