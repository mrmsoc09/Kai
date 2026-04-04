from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent


class NaabuAgent(BaseToolAgent):
    TOOL_NAME = "naabu"

    # Common BBP and High-Risk Ports
    BBP_WEB_PORTS = "80,443,8080,8443,9000,9090,9200,9443,10000"
    ALL_WEB_PORTS = "80,443,8080,8443,9000,9090,9200,9443,10000,3000,5000,8000,8888,9001"

    PORT_SERVICE_MAP = {
        "9200": "elasticsearch",
        "9300": "elasticsearch",
        "10000": "webmin",
        "9000": "php-fpm",
        "6379": "redis",
        "27017": "mongodb",
        "3306": "mysql",
        "5432": "postgresql",
        "2375": "docker-api",
        "2376": "docker-api-tls",
        "5601": "kibana",
    }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # Naabu for fast port scanning
        cmd = ["naabu", "-host", target, "-silent"]
        
        # Port selection
        if opts.get("full_scan"):
            cmd += ["-p", "-"]
        elif opts.get("top_ports"):
            cmd += ["-top-ports", str(opts["top_ports"])]
        else:
            # Default: Prioritize BBP web ports
            ports = opts.get("ports", self.BBP_WEB_PORTS)
            cmd += ["-p", ports]
            
        # Mandatory CDN exclusion for speed/accuracy
        if opts.get("exclude_cdn", True):
            cmd.append("-exclude-cdn")
            
        if opts.get("rate_limit"):
            cmd += ["-rate", str(opts["rate_limit"])]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Output format: host:port
            parts = line.split(":")
            if len(parts) == 2:
                host, port = parts
                findings.append({
                    "host": host,
                    "port": port,
                    "value": f"{host}:{port}",
                    "service": self.PORT_SERVICE_MAP.get(port, "unknown"),
                    "source": "naabu",
                    "target": target,
                })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            # Common 80/443 are signal but high volume, separate if needed
            if item.get("service") != "unknown":
                item["signal_reason"] = "high_risk_service"
                signal.append(item)
            else:
                signal.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        targets = [s["value"] for s in signal]
        high_risk = [s["value"] for s in signal if s.get("signal_reason") == "high_risk_service"]
        
        return {
            "next_agent": "nmap",
            "action": "service_enumeration",
            "target": target,
            "input_targets": targets,
            "high_risk_targets": high_risk,
            "instructions": (
                f"Found {len(targets)} open ports. "
                f"High-risk services: {', '.join(high_risk[:5])}. "
                "Run Nmap service fingerprinting on these targets for confirmation."
            ),
        }
