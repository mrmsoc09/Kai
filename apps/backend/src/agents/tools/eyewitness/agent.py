from __future__ import annotations

import re
from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_TOKENS = {
    "login",
    "sign in",
    "admin",
    "dashboard",
    "forbidden",
    "error",
    "exception",
    "debug",
    "traceback",
    "swagger",
}

_NOISE_TOKENS = {"parking", "coming soon", "default page", "placeholder"}


class EyewitnessAgent(BaseToolAgent):
    TOOL_NAME = "eyewitness"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        hosts_file = opts.get("hosts_file", target)
        output_dir = opts.get("output_dir", f"{opts.get('artifact_dir', '/tmp')}/eyewitness")
        return [
            "eyewitness",
            "--web",
            "-f",
            str(hosts_file),
            "--directory",
            str(output_dir),
            "--timeout",
            str(opts.get("timeout", 10)),
            "--delay",
            str(opts.get("delay", 2)),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        url_pattern = re.compile(r"https?://[^\s]+", re.IGNORECASE)
        title_pattern = re.compile(r"title[:=]\s*([^\|\]]+)", re.IGNORECASE)
        status_pattern = re.compile(r"\b(\d{3})\b")

        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            url_match = url_pattern.search(line)
            if not url_match:
                continue
            url = url_match.group(0)

            title_match = title_pattern.search(line)
            status_match = status_pattern.search(line)
            title = title_match.group(1).strip() if title_match else ""
            status = int(status_match.group(1)) if status_match else None

            findings.append(
                {
                    "type": "screenshot",
                    "value": url,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.72,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {"title": title, "http_status": status},
                    "recommended_next_tools": ["feroxbuster", "nuclei_scan"],
                    "recommended_next_actions": ["review_interesting_pages", "enumerate_paths"],
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
            value = str(finding.get("value", "")).lower()
            if f"{finding.get('target', '').lower()}|screenshot|{value}" in known:
                noise.append(finding)
                continue

            title = str(finding.get("context", {}).get("title", "")).lower()
            evidence = str(finding.get("raw_evidence", "")).lower()
            merged = f"{title} {evidence}"
            if any(token in merged for token in _NOISE_TOKENS):
                noise.append(finding)
                continue
            if any(token in merged for token in _HIGH_VALUE_TOKENS):
                finding["severity"] = "medium"
                finding["confidence"] = 0.88
            signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        high_value = [
            item for item in signal if str(item.get("severity", "")).lower() in {"medium", "high", "critical"}
        ]
        return {
            "next_agents": ["feroxbuster", "nuclei_scan"],
            "complement_tool": "gowitness",
            "priority_targets": [item.get("value") for item in high_value[:20]],
            "note": (
                "Run both gowitness and eyewitness in parallel; rendering differences surface distinct findings."
            ),
            "operator_summary": (
                f"Eyewitness parsed {len(signal)} visual endpoints for {target}. "
                f"High-value pages flagged: {len(high_value)}."
            ),
        }
