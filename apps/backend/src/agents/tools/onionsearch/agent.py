from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class OnionsearchAgent(BaseToolAgent):
    TOOL_NAME = "onionsearch"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        return [
            "onionsearch",
            target,
            "--output",
            f"{artifact_dir}/onionsearch.json",
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        results = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(results, list):
            return findings

        target_lower = target.lower()
        for entry in results:
            if not isinstance(entry, dict):
                continue

            url = str(entry.get("url", "")).strip()
            snippet = str(entry.get("snippet", "")).strip()
            if not url:
                continue

            has_credential = any(
                pattern in snippet.lower()
                for pattern in ["password", "leaked", "credentials", "breach", "dump"]
            )

            findings.append(
                {
                    "type": "dark_web_search_result",
                    "value": url,
                    "target": target,
                    "severity": "high" if has_credential else "medium",
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": snippet[:500],
                    "context": {
                        "has_credential_keywords": has_credential,
                        "source": "onionsearch_index",
                    },
                    "recommended_next_tools": ["torbot", "EvidenceAnalystAgent"],
                    "recommended_next_actions": ["investigate_onion_source"],
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
            if f"{finding['target'].lower()}|dark_web_search|{value}" in known:
                noise.append(finding)
                continue

            if finding.get("context", {}).get("has_credential_keywords"):
                signal.append(finding)
            else:
                signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        high_value = [f for f in signal if f.get("severity") == "high"]
        return {
            "next_agents": ["torbot", "EvidenceAnalystAgent"],
            "high_value_results": len(high_value),
            "total_results": len(signal),
            "operator_summary": (
                f"Onionsearch found {len(signal)} dark web search results for {target}. "
                f"High-value findings: {len(high_value)} (credential-related). "
                "Consider deep crawl with torbot for detailed investigation."
            ),
        }
