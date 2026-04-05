from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class CrlfuzzAgent(BaseToolAgent):
    TOOL_NAME = "crlfuzz"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # CRLFuzz for header injection
        cmd = ["crlfuzz", "-u", target, "-silent"]
        
        if opts.get("data"):
            cmd += ["-d", opts["data"]]
            
        if opts.get("method"):
            cmd += ["-X", opts["method"]]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        # CRLFuzz returns vulnerable URLs in output
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            findings.append({
                "type": "vulnerability",
                "value": line,
                "target": target,
                "severity": "medium",
                "confidence": 0.8,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": line,
                "context": {
                    "vulnerability_type": "crlf_injection",
                    "evidence": "Header injection / Response splitting detected",
                },
                "recommended_next_tools": ["EvidenceAnalystAgent"],
                "recommended_next_actions": ["validate_crlf"],
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

            if item["context"].get("vulnerability_type") == "crlf_injection":
                item["signal_reason"] = "header_injection_confirmed"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "test_cache_poisoning",
            "target": target,
            "instructions": (
                "CRLFuzz detected header injection. "
                "Trigger EvidenceAnalystAgent to check for cache poisoning or session fixation possibilities."
            ),
        }
