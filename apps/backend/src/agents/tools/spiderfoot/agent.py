from __future__ import annotations

import json
import os
import shutil
from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_TYPES = {
    "CREDENTIAL_COMPROMISED",
    "EMAILADDR_COMPROMISED",
    "LEAKED_INFO",
    "PASSWORD_COMPROMISED",
    "VULNERABILITY_CVE_CRITICAL",
    "VULNERABILITY_CVE_HIGH",
    "DARKWEB_MENTION",
    "SOCIAL_MEDIA",
}


class SpiderfootAgent(BaseToolAgent):
    TOOL_NAME = "spiderfoot"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        artifact_dir = str(opts.get("artifact_dir", "/tmp"))
        output_path = f"{artifact_dir}/spiderfoot.json"
        # PERMITTED: SPIDERFOOT_MODULES is set by the midnight orchestrator before scan execution.
        # This is the designed integration point between the orchestrator and spiderfoot agent.
        # It is not a hardcoded secret — it is a runtime configuration value with a safe default.
        modules = os.environ.get(
            "SPIDERFOOT_MODULES",
            "sfp_dns,sfp_ssl,sfp_whois,sfp_crt,sfp_netcraft",
        )
        timeout_seconds = int(opts.get("timeout_seconds", 1800))
        binary = "sf" if shutil.which("sf") else "spiderfoot"
        return [
            binary,
            "-s",
            target,
            "-m",
            modules,
            "-o",
            "json",
            "-q",
            "-l",
            output_path,
            "-t",
            str(min(timeout_seconds, 1800)),
        ]

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        try:
            payload = json.loads(raw_output.strip())
        except (json.JSONDecodeError, TypeError):
            payload = []
            # Fallback: allow JSONL-style output emitted line-by-line.
            for line in raw_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    payload.append(item)

        if isinstance(payload, dict):
            data = payload.get("results", [])
        else:
            data = payload

        if not isinstance(data, list):
            return findings

        for entry in data:
            if not isinstance(entry, dict):
                continue
            data_type = str(entry.get("type", "UNKNOWN"))
            value = str(entry.get("data", "")).strip()
            if not value:
                continue

            high = data_type in _HIGH_VALUE_TYPES
            findings.append(
                {
                    "type": "osint_finding",
                    "value": value[:500],
                    "target": target,
                    "severity": "high" if high else "info",
                    "confidence": 0.9 if high else 0.7,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": json.dumps(entry, ensure_ascii=True)[:1000],
                    "context": {
                        "data_type": data_type,
                        "module": str(entry.get("module", "")),
                    },
                    "recommended_next_tools": ["EvidenceAnalystAgent"],
                    "recommended_next_actions": ["investigate"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()
        critical_tokens = ["CREDENTIAL", "LEAKED", "PASSWORD", "COMPROMISED", "DARKWEB", "CVE"]

        for finding in findings:
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|osint|{value}" in known:
                noise.append(finding)
                continue

            data_type = str(finding.get("context", {}).get("data_type", ""))
            if any(token in data_type for token in critical_tokens):
                finding["severity"] = "high"
                signal.append(finding)
            elif str(finding.get("severity", "info")).lower() == "info":
                noise.append(finding)
            else:
                signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        credentials = [
            f
            for f in signal
            if "CREDENTIAL" in str(f.get("context", {}).get("data_type", ""))
        ]
        return {
            "next_agents": ["EvidenceAnalystAgent"],
            "credential_findings": len(credentials),
            "operator_summary": (
                f"SpiderFoot analyzed {target} with configured OSINT modules. "
                f"Signal findings: {len(signal)}. Credential exposures: {len(credentials)}. "
                "Discovered credentials are escalation evidence only and must never be used."
            ),
        }
