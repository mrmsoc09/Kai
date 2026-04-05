from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_KEYWORDS = {
    "admin",
    "api",
    "dev",
    "staging",
    "internal",
    "backend",
    "portal",
    "dashboard",
    "jenkins",
    "grafana",
}


class FindomainAgent(BaseToolAgent):
    TOOL_NAME = "findomain"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/findomain_output.txt")
        # findomain doesn't have a direct timeout flag but we enforce via subprocess.
        # Ensure it runs quietly in background for larger scans.
        return [
            "findomain",
            "--target",
            target,
            "--quiet",
            "--output",
            str(output_file),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            value = line.strip()
            if not value or value.startswith("[") or "." not in value:
                continue
            findings.append(
                {
                    "type": "subdomain",
                    "value": value,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {"source": "certificate_transparency"},
                    "recommended_next_tools": ["dnsx", "httpx_probe"],
                    "recommended_next_actions": ["resolve_dns"],
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
            if f"{finding.get('target', '').lower()}|subdomain|{value}" in known:
                noise.append(finding)
                continue

            if value.startswith("*."):
                noise.append(finding)
                continue
            if any(token in value for token in _HIGH_VALUE_KEYWORDS):
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
        return {
            "next_agents": ["dnsx", "httpx_probe"],
            "priority_targets": [f["value"] for f in high_value[:10]],
            "operator_summary": (
                f"Findomain discovered {len(signal)} subdomains for {target}. "
                "Merge and deduplicate with subfinder and amass before dnsx probing."
            ),
        }
