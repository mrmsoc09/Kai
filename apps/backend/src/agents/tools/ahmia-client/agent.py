from __future__ import annotations

import json
import re
from typing import Any

from ..base_tool_agent import BaseToolAgent


class AhmiaClientAgent(BaseToolAgent):
    TOOL_NAME = "ahmia-client"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        import shutil
        if shutil.which("ahmia"):
            return ["ahmia", "search", target]
        return [
            "python3",
            "-c",
            f"import requests,sys; r=requests.get('https://ahmia.fi/search/', params={{'q':'{target}'}}, timeout=30); print(r.text[:50000])",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if not raw_output.strip():
            return findings

        onion_urls = re.findall(r"https?://[a-z0-9]{16,}\.onion[^\s<\"]*", raw_output, re.IGNORECASE)
        for url in set(onion_urls):
            findings.append(
                {
                    "type": "indexed_dark_web_result",
                    "value": url,
                    "target": target,
                    "severity": "medium",
                    "confidence": 0.75,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": raw_output[:500],
                    "context": {
                        "source": "ahmia_index",
                        "clearnet_accessed": True,
                    },
                    "recommended_next_tools": ["torbot", "EvidenceAnalystAgent"],
                    "recommended_next_actions": ["verify_onion_content"],
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
            if f"{finding['target'].lower()}|ahmia|{value}" in known:
                noise.append(finding)
                continue

            target_in_url = finding["target"].lower() in value
            if target_in_url or target in finding.get("raw_evidence", ""):
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        return {
            "next_agents": ["torbot", "EvidenceAnalystAgent"],
            "indexed_onion_urls": len(signal),
            "operator_summary": (
                f"Ahmia index returned {len(signal)} indexed .onion URLs for {target}. "
                "No Tor connection required for index search. Consider crawling URLs with torbot."
            ),
        }
