from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class CaidoCliAgent(BaseToolAgent):
    """Headless Caido CLI wrapper for lightweight endpoint and parameter discovery."""

    TOOL_NAME = "caido_cli"

    _NOISE_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
        ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".pdf",
    }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        depth = max(1, int(opts.get("depth", 2)))
        max_requests = max(1, int(opts.get("max_requests", 120)))
        
        # Base command for caido-cli
        return [
            "caido-cli",
            "crawl",
            "--headless",
            "--url",
            target,
            "--format",
            "jsonl",
            "--depth",
            str(depth),
            "--max-requests",
            str(max_requests),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
                url = data.get("url") or data.get("endpoint")
                if not url:
                    continue
                
                findings.append({
                    "type": "url",
                    "value": url,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.84,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line[:1000],
                    "context": {
                        "method": data.get("method", "GET"),
                        "status_code": data.get("status_code"),
                        "parameters": data.get("parameters", []),
                    },
                    "recommended_next_tools": ["arjun", "gf", "dalfox"],
                    "recommended_next_actions": ["parameter_discovery", "vulnerability_scan"],
                })
            except json.JSONDecodeError:
                continue
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for finding in findings:
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            if any(value.endswith(ext) for ext in self._NOISE_EXTENSIONS):
                noise.append(finding)
                continue
            
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        urls = [f["value"] for f in signal]
        return {
            "next_agent": "arjun",
            "action": "parameter_discovery",
            "target": target,
            "input_urls": urls,
            "instructions": f"Caido discovered {len(urls)} endpoints. Trigger arjun for parameter discovery.",
        }
