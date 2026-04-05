from __future__ import annotations

import json
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

_NOISE_TOKENS = {"parking", "coming soon", "default page", "it works", "placeholder"}


class GoWitnessAgent(BaseToolAgent):
    TOOL_NAME = "gowitness"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        hosts_file = opts.get("hosts_file", target)
        screenshot_path = opts.get("screenshot_path", f"{opts.get('artifact_dir', '/tmp')}/screenshots")
        return [
            "gowitness",
            "scan",
            "file",
            "-f",
            str(hosts_file),
            "--screenshot-path",
            str(screenshot_path),
            "--delay",
            str(opts.get("delay", 2)),
            "--timeout",
            str(opts.get("timeout", 10)),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            data: dict[str, Any] = {}
            if line.startswith("{") and line.endswith("}"):
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        data = parsed
                except json.JSONDecodeError:
                    data = {}

            url = str(data.get("url") or data.get("final_url") or "")
            title = str(data.get("title") or "")
            status = data.get("status_code")
            shot = str(data.get("screenshot") or data.get("screenshot_path") or "")

            if not url:
                if line.startswith("http://") or line.startswith("https://"):
                    url = line.split()[0]
                else:
                    continue

            findings.append(
                {
                    "type": "screenshot",
                    "value": url,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.75,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {
                        "screenshot_path": shot,
                        "http_status": status,
                        "title": title,
                    },
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
                finding["confidence"] = 0.9
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
        screenshot_paths = [
            str(item.get("context", {}).get("screenshot_path", "")).strip()
            for item in signal
            if str(item.get("context", {}).get("screenshot_path", "")).strip()
        ]
        return {
            "next_agents": ["feroxbuster", "nuclei_scan"],
            "priority_targets": [item.get("value") for item in high_value[:20]],
            "screenshot_dir": screenshot_paths[0].rsplit("/", 1)[0] if screenshot_paths else "",
            "operator_summary": (
                f"GoWitness captured {len(signal)} pages for {target}. "
                f"Flagged {len(high_value)} as high-value visual targets for immediate review."
            ),
        }
