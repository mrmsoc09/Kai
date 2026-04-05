from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_PORTS = {9200, 6379, 5601, 9090}


class MasscanAgent(BaseToolAgent):
    TOOL_NAME = "masscan"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/masscan_output.json")
        rate = int(opts.get("rate", 1000))
        # masscan uses --max-rate. Timeout is handled by BaseToolAgent's communicate().
        return [
            "masscan",
            target,
            "-p",
            "80,443,8080,8443,3000,4000,5000,8000,8888,9090",
            "--rate",
            str(rate),
            "--output-format",
            "json",
            "--output-filename",
            str(output_file),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        raw_output = raw_output.strip()
        if not raw_output:
            return findings

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            payload = []

        if not isinstance(payload, list):
            return findings

        for host_result in payload:
            if not isinstance(host_result, dict):
                continue
            ip = str(host_result.get("ip", target)).strip() or target
            ports = host_result.get("ports", [])
            if not isinstance(ports, list):
                continue
            for item in ports:
                if not isinstance(item, dict):
                    continue
                port_value = item.get("port")
                if not isinstance(port_value, int):
                    continue
                severity = "high" if port_value in _HIGH_VALUE_PORTS else "medium"
                findings.append(
                    {
                        "type": "open_port",
                        "value": f"{ip}:{port_value}",
                        "target": target,
                        "severity": severity,
                        "confidence": 0.9 if port_value in _HIGH_VALUE_PORTS else 0.8,
                        "source_tool": self.TOOL_NAME,
                        "raw_evidence": json.dumps(item, ensure_ascii=True),
                        "context": {"ip": ip, "port": port_value, "protocol": item.get("proto", "tcp")},
                        "recommended_next_tools": ["nmap"],
                        "recommended_next_actions": ["run_targeted_service_detection"],
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
            port = int(finding.get("context", {}).get("port", 0) or 0)
            if f"{finding.get('target', '').lower()}|port|{finding.get('value', '')}" in known:
                noise.append(finding)
                continue

            if port in {80, 443}:
                finding["confidence"] = 0.5
                noise.append(finding)
            else:
                signal.append(finding)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        ports = sorted(
            {int(item.get("context", {}).get("port", 0) or 0) for item in signal if item.get("context", {}).get("port")}
        )
        return {
            "next_agents": ["nmap"],
            "ports": [p for p in ports if p > 0],
            "operator_summary": (
                f"Masscan quickly identified {len(signal)} non-noise open ports for {target}. "
                "Handing off discovered ports to nmap for service and version detection."
            ),
        }
