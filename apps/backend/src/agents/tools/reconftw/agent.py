from __future__ import annotations

import re
from typing import Any

from ..base_tool_agent import BaseToolAgent


class ReconftfwAgent(BaseToolAgent):
    TOOL_NAME = "reconftw"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        return [
            "reconftw.sh",
            "-d",
            target,
            "-r",
            "--timeout",
            str(opts.get("timeout", 300)),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        subdomain_pattern = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+" + re.escape(target) + r"\b")

        for line in raw_output.strip().splitlines():
            text = line.strip()
            if not text:
                continue

            matches = subdomain_pattern.findall(text)
            if matches:
                for subdomain in matches:
                    findings.append(
                        {
                            "type": "subdomain",
                            "value": subdomain,
                            "target": target,
                            "severity": "info",
                            "confidence": 0.7,
                            "source_tool": self.TOOL_NAME,
                            "raw_evidence": text[:1000],
                            "context": {
                                "record_type": "subdomain",
                                "supplemental": True,
                            },
                            "recommended_next_tools": ["dnsx", "httpx_probe"],
                            "recommended_next_actions": ["resolve_dns"],
                        }
                    )
                continue

            if any(token in text.lower() for token in ["total", "found", "summary", "alive"]):
                findings.append(
                    {
                        "type": "summary",
                        "value": text[:200],
                        "target": target,
                        "severity": "info",
                        "confidence": 0.6,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": text[:500],
                        "context": {
                            "record_type": "summary_line",
                            "supplemental": True,
                        },
                        "recommended_next_tools": ["dnsx", "httpx_probe"],
                        "recommended_next_actions": ["review_delta"],
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
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|{finding['type']}|{value}" in known:
                noise.append(finding)
                continue
            
            if not value:
                noise.append(finding)
                continue
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        new_subdomains = [
            f["value"]
            for f in signal
            if str(f.get("context", {}).get("record_type", "")) == "subdomain"
        ]

        return {
            "next_agents": ["dnsx", "httpx_probe"],
            "new_subdomains": new_subdomains,
            "operator_summary": (
                f"ReconFTW supplemental recon yielded {len(new_subdomains)} candidate subdomains for {target}. "
                "Use as additive intelligence, not replacement for dedicated agents."
            ),
        }
