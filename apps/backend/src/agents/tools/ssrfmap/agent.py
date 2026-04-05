from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent


class SsrfmapAgent(BaseToolAgent):
    TOOL_NAME = "ssrfmap"

    # Common internal and metadata targets
    CLOUD_METADATA_TARGETS = [
        "169.254.169.254",  # AWS/GCP/Azure/Openstack
        "metadata.google.internal",  # GCP
        "100.100.100.200",  # Alibaba
        "169.254.169.254/latest/meta-data/iam/security-credentials/", # AWS Role
    ]

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # SSRFMap requires a URL and a parameter to fuzz
        # Example: ssrfmap -u "http://target.com/api?url=FUZZ" -m read
        cmd = ["ssrfmap", "-u", target, "-m", "read"]
        
        if opts.get("proxy"):
            cmd += ["--proxy", opts["proxy"]]
            
        if opts.get("headers"):
            cmd += ["--headers", opts["headers"]]
            
        # Default to cloud metadata exfiltration if no module specified
        if not opts.get("modules"):
            cmd += ["-l", "aws,gcp,azure"]
            
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        # Parse for successful SSRF indicators in output
        if "[+]" in raw_output or "Vulnerable" in raw_output or "200 OK" in raw_output:
            findings.append({
                "type": "vulnerability",
                "value": target,
                "target": target,
                "severity": "high",
                "confidence": 0.8,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": raw_output[:2000],
                "context": {
                    "vulnerability_type": "ssrf",
                    "evidence": "Cloud metadata or internal resource accessible",
                },
                "recommended_next_tools": ["EvidenceAnalystAgent"],
                "recommended_next_actions": ["validate_ssrf"],
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        for item in findings:
            value = item["value"].lower()
            if f"{item['target'].lower()}|vulnerability|{value}" in known:
                noise.append(item)
                continue

            if item["context"].get("vulnerability_type") == "ssrf":
                item["signal_reason"] = "potential_ssrf_leaking_metadata"
                signal.append(item)
            else:
                noise.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        return {
            "next_agent": "EvidenceAnalystAgent",
            "action": "confirm_ssrf_oob",
            "target": target,
            "instructions": (
                "SSRFMap identified a potential metadata leak. "
                "Trigger EvidenceAnalystAgent for out-of-band (OOB) confirmation using Interactsh."
            ),
        }
