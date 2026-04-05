from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class GraphqlCopAgent(BaseToolAgent):
    TOOL_NAME = "graphql-cop"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        endpoint = str(opts.get("graphql_endpoint", target))
        timeout = str(opts.get("timeout_seconds", 60))
        return [
            "graphql-cop",
            "-t",
            endpoint,
            "-o",
            "json",
            "--timeout",
            timeout,
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

        results = data.get("results", [])
        if not isinstance(results, list):
            return findings

        for result in results:
            if not isinstance(result, dict):
                continue

            test_name = str(result.get("test", ""))
            passed = bool(result.get("passed", False))

            if passed:
                findings.append(
                    {
                        "type": "graphql_vulnerability",
                        "value": test_name,
                        "target": target,
                        "severity": "high" if test_name == "introspection" else "medium",
                        "confidence": 0.9,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": json.dumps(result)[:500],
                        "context": {
                            "test": test_name,
                            "vulnerable": True,
                        },
                        "recommended_next_tools": ["clairvoyance", "EvidenceAnalystAgent"],
                        "recommended_next_actions": ["graphql_remediation"],
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
            key = f"{finding['target'].lower()}|graphql|{finding['value'].lower()}"
            if key in known:
                noise.append(finding)
                continue

            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        introspection = [f for f in signal if f.get("context", {}).get("test") == "introspection"]
        return {
            "next_agents": ["clairvoyance", "EvidenceAnalystAgent"],
            "vulnerable_tests": len(signal),
            "introspection_enabled": len(introspection) > 0,
            "operator_summary": (
                f"GraphQL-Cop identified {len(signal)} security test failures on {target}. "
                f"Introspection vulnerability: {bool(introspection)}. "
                "If introspection disabled, run Clairvoyance for schema recovery."
            ),
        }
