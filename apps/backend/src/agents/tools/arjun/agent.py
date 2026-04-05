from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class ArjunAgent(BaseToolAgent):
    TOOL_NAME = "arjun"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        endpoint = str(opts.get("endpoint", target))
        output_path = f"{artifact_dir}/arjun.json"
        return ["arjun", "-u", endpoint, "--stable", "-oJ", output_path]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            data = None

        records: list[tuple[str, list[str], str]] = []
        if isinstance(data, dict):
            if "endpoint" in data and isinstance(data.get("parameters"), list):
                endpoint = str(data.get("endpoint", target))
                method = str(data.get("method", "GET"))
                params = [str(p) for p in data.get("parameters", []) if str(p).strip()]
                records.append((endpoint, params, method))
            else:
                for endpoint, params in data.items():
                    if isinstance(params, list):
                        records.append((str(endpoint), [str(p) for p in params if str(p).strip()], "GET"))
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                endpoint = str(item.get("endpoint", target))
                params = item.get("parameters") or item.get("params") or []
                method = str(item.get("method", "GET"))
                if isinstance(params, list):
                    records.append((endpoint, [str(p) for p in params if str(p).strip()], method))

        for endpoint, params, method in records:
            for param in params:
                findings.append(
                    {
                        "type": "parameter",
                        "value": param,
                        "target": target,
                        "severity": "info",
                        "confidence": 0.85,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": raw_output[:1000],
                        "context": {
                            "endpoint": endpoint,
                            "method": method,
                        },
                        "recommended_next_tools": ["dalfox", "sqlmap", "ssrfmap"],
                        "recommended_next_actions": ["inject_parameter"],
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
            endpoint = finding["context"].get("endpoint", "").lower()
            if f"{finding['target'].lower()}|parameter|{value}@{endpoint}" in known:
                noise.append(finding)
                continue
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        endpoint_param_map: dict[str, list[str]] = {}
        for finding in signal:
            endpoint = str(finding.get("context", {}).get("endpoint", target))
            param = str(finding.get("value", "")).strip()
            if not param:
                continue
            endpoint_param_map.setdefault(endpoint, [])
            if param not in endpoint_param_map[endpoint]:
                endpoint_param_map[endpoint].append(param)

        parameter_list = sorted({p for params in endpoint_param_map.values() for p in params})

        return {
            "next_agents": ["dalfox", "sqlmap", "ssrfmap"],
            "parameter_list": parameter_list,
            "endpoint_param_map": endpoint_param_map,
            "operator_summary": (
                f"Arjun identified {len(parameter_list)} unique parameters across "
                f"{len(endpoint_param_map)} endpoints for {target}."
            ),
        }
