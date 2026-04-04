from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class DalfoxAgent(BaseToolAgent):
    TOOL_NAME = "dalfox"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # Dalfox for XSS scanning
        # Use gf xss output as input if file is provided, otherwise target directly
        input_file = opts.get("input_file")
        if input_file:
            cmd = ["dalfox", "file", input_file, "--silent"]
        else:
            cmd = ["dalfox", "url", target, "--silent"]
            
        # Implementation of --skip-bav for speed in pipelines
        if opts.get("skip_bav", True):
            cmd.append("--skip-bav")
            
        if opts.get("blind"):
            cmd += ["-b", opts["blind"]]
            
        if opts.get("header"):
            cmd += ["-H", opts["header"]]
            
        # JSON output for parsing
        cmd += ["--output-format", "json"]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
                # Dalfox JSON structure
                findings.append({
                    "type": "vulnerability",
                    "value": data.get("poc", data.get("url", "")),
                    "target": target,
                    "severity": "high" if data.get("type") == "V" else "medium",
                    "confidence": 0.9 if data.get("type") == "V" else 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {
                        "url": data.get("url", ""),
                        "parameter": data.get("param", ""),
                        "finding_type": data.get("type", ""),
                        "evidence": data.get("evidence", ""),
                        "poc": data.get("poc", ""),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["validate_xss"],
                })
            except json.JSONDecodeError:
                pass
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

            if item["context"].get("finding_type") == "V":  # Vulnerability
                item["signal_reason"] = "confirmed_xss"
                signal.append(item)
            elif item["context"].get("finding_type") == "P":  # Potential
                item["signal_reason"] = "potential_xss"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        confirmed = [s for s in signal if s.get("signal_reason") == "confirmed_xss"]
        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "screenshot_poc",
            "target": target,
            "confirmed_pocs": [s["context"]["poc"] for s in confirmed],
            "instructions": (
                f"Dalfox identified {len(confirmed)} confirmed XSS vulnerabilities. "
                "Trigger EvidenceAnalystAgent for screenshot capture and automated validation."
            ),
        }
