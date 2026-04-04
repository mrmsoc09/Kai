from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


_STATIC_EXTENSIONS = {".css", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".svg"}


class KatanaAgent(BaseToolAgent):
    TOOL_NAME = "katana"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        output_path = f"{artifact_dir}/katana.json"
        return [
            "katana",
            "-u",
            target,
            "-jc",
            "-kf",
            "all",
            "-d",
            str(opts.get("depth", 5)),
            "-json",
            "-o",
            output_path,
            "-timeout",
            str(opts.get("timeout", 10)),
            "-rate-limit",
            str(opts.get("rate_limit", 10)),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            endpoint = str(entry.get("endpoint") or entry.get("url") or "").strip()
            if not endpoint:
                continue
            is_graphql = "graphql" in endpoint.lower()

            findings.append(
                {
                    "type": "url",
                    "value": endpoint,
                    "target": target,
                    "severity": "medium" if is_graphql else "info",
                    "confidence": 0.8,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line[:1000],
                    "context": {
                        "source": entry.get("source", ""),
                        "is_graphql": is_graphql,
                        "tag": entry.get("tag", ""),
                    },
                    "recommended_next_tools": ["arjun", "dalfox", "gf"],
                    "recommended_next_actions": ["parameter_discovery", "vulnerability_scan"],
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
            if f"{finding['target'].lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            if bool(finding.get("context", {}).get("is_graphql")):
                finding["severity"] = "medium"
                signal.append(finding)
                continue
            if any(value.endswith(ext) for ext in _STATIC_EXTENSIONS):
                noise.append(finding)
                continue
            if value.endswith(".js"):
                finding["severity"] = "low"
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        graphql_endpoints = [f["value"] for f in signal if bool(f.get("context", {}).get("is_graphql"))]
        js_files = [f["value"] for f in signal if str(f.get("value", "")).lower().endswith(".js")]

        return {
            "next_agents": ["arjun", "gf", "dalfox", "EvidenceAnalystAgent"],
            "graphql_endpoints": graphql_endpoints,
            "js_files": js_files,
            "graphql_detected": len(graphql_endpoints) > 0,
            # graphql-cop added Wave 3
            "operator_summary": (
                f"Katana crawled {target} and produced {len(signal)} endpoints. "
                f"GraphQL endpoints: {len(graphql_endpoints)}. JS assets for review: {len(js_files)}."
            ),
        }
