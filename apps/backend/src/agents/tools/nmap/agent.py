from __future__ import annotations

import re
from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_PORTS = {
    "9200": "Elasticsearch",
    "6379": "Redis",
    "5601": "Kibana",
    "27017": "MongoDB",
    "9090": "Prometheus",
}


class NmapAgent(BaseToolAgent):
    TOOL_NAME = "nmap"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        output_file = opts.get("output_file", f"{opts.get('artifact_dir', '/tmp')}/nmap_output.xml")
        cmd = [
            "nmap",
            "-sV",
            "-p",
            "80,443,8080,8443,3000,4000,5000,8000,8081,8888,9000,9090,9200,6379,5601,27017,5432,3306",
            "--open",
            "-oX",
            str(output_file),
            "--host-timeout",
            str(opts.get("host_timeout", "60s")),
            "--script-timeout",
            str(opts.get("script_timeout", "30s")),
        ]
        open_ports_file = opts.get("open_ports_file")
        if isinstance(open_ports_file, str) and open_ports_file.strip():
            cmd.extend(["-iL", open_ports_file.strip()])
        else:
            cmd.append(target)
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        pattern = re.compile(r"(\d+)/tcp\s+open\s+(\S+)\s*(.*)")
        for line in raw_output.splitlines():
            match = pattern.search(line)
            if not match:
                continue
            port = match.group(1)
            service = match.group(2)
            version = match.group(3).strip()
            severity = "info"
            confidence = 0.7
            if port in _HIGH_VALUE_PORTS:
                severity = "high"
                confidence = 0.9
            elif port not in {"80", "443"}:
                severity = "medium"
                confidence = 0.8
            findings.append(
                {
                    "type": "open_port",
                    "value": f"{target}:{port}",
                    "target": target,
                    "severity": severity,
                    "confidence": confidence,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line.strip(),
                    "context": {"port": port, "service": service, "version": version},
                    "recommended_next_tools": ["searchsploit", "nuclei_scan"],
                    "recommended_next_actions": ["check_cve_for_version", "run_service_specific_scan"],
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
            value = str(finding.get("value", ""))
            if f"{finding.get('target', '').lower()}|open_port|{value}" in known:
                noise.append(finding)
                continue

            port = str(finding.get("context", {}).get("port", ""))
            if port in {"80", "443"}:
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
        high_value = [
            item for item in signal if str(item.get("severity", "")).lower() in {"medium", "high", "critical"}
        ]
        versions = [
            str(item.get("context", {}).get("version", "")).strip()
            for item in high_value
            if str(item.get("context", {}).get("version", "")).strip()
        ]
        return {
            "next_agents": ["searchsploit", "nuclei_scan"],
            "version_strings": versions,
            "high_value_ports": [f["value"] for f in high_value],
            "operator_summary": (
                f"Nmap found {len(signal)} non-noise open services on {target}. "
                f"Forwarding {len(versions)} version strings for CVE correlation and template narrowing."
            ),
        }
