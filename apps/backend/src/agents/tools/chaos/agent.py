from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_KEYWORDS = {"admin", "api", "dev", "staging", "internal", "backend"}


class ChaosAgent(BaseToolAgent):
    TOOL_NAME = "chaos"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/chaos_output.txt")
        # chaos has a -silent flag and -d for domain. 
        # We enforce timeout via subprocess wrapper in BaseToolAgent.
        return ["chaos", "-d", target, "-silent", "-o", str(output_file)]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            value = line.strip()
            if not value or "." not in value:
                continue
            findings.append(
                {
                    "type": "subdomain",
                    "value": value,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.95,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {
                        "source": "projectdiscovery_dataset",
                        "note": "High-confidence passive dataset hit.",
                    },
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
                finding["confidence"] = 0.97
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
            "priority_targets": [f["value"] for f in high_value[:15]],
            "operator_summary": (
                f"Chaos returned {len(signal)} subdomains for {target} from the "
                "ProjectDiscovery community dataset. Prioritize newly surfaced internal labels."
            ),
        }
