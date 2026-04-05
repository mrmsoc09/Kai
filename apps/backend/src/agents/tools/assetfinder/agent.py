from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent


_HIGH_VALUE_KEYWORDS = {
    "admin",
    "api",
    "dev",
    "staging",
    "internal",
    "backend",
    "dashboard",
    "portal",
    "vpn",
    "gitlab",
    "jenkins",
    "grafana",
    "kibana",
    "vault",
    "consul",
    "k8s",
    "kubernetes",
    "prod",
    "qa",
    "test",
    "beta",
    "alpha",
    "preview",
}

_LOW_VALUE_KEYWORDS = {
    "mail",
    "smtp",
    "ftp",
    "imap",
    "pop",
    "autodiscover",
    "cpanel",
    "webmail",
}


class AssetfinderAgent(BaseToolAgent):
    TOOL_NAME = "assetfinder"
    def _get_tool_name(self) -> str:
        return self.TOOL_NAME


    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # assetfinder doesn't have a native timeout flag, but we enforce it via the base class.
        # We can simulate tool-level timeout by wrapping with 'timeout' command if needed,
        # but here we'll just ensure the options are passed if any downstream wrapper needs them.
        cmd = ["assetfinder"]
        if opts.get("subs_only", True):
            cmd.append("--subs-only")
        cmd.append(target)
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            value = line.strip()
            if not value or value.startswith("#") or "." not in value:
                continue
            findings.append(
                {
                    "type": "subdomain",
                    "value": value,
                    "target": target,
                    "severity": "info",
                    "confidence": 0.75,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": line,
                    "context": {"source": "certificate_transparency"},
                    "recommended_next_tools": ["dnsx", "httpx_probe"],
                    "recommended_next_actions": ["resolve_dns", "probe_http"],
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
            value = str(finding.get("value", "")).lower()
            # If we've seen this exact asset before, it's considered noise for the current stream
            # to avoid re-processing, although BaseToolAgent also handles this.
            if f"{finding.get('target', '').lower()}|subdomain|{value}" in known:
                noise.append(finding)
                continue

            if value.startswith("*."):
                noise.append(finding)
                continue
            if any(token in value for token in _LOW_VALUE_KEYWORDS):
                finding["confidence"] = 0.3
                noise.append(finding)
                continue
            if any(token in value for token in _HIGH_VALUE_KEYWORDS):
                finding["severity"] = "medium"
                finding["confidence"] = 0.9
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
        return {
            "next_agents": ["dnsx", "httpx_probe"],
            "priority_targets": [f["value"] for f in high_value[:20]],
            "configuration_hints": {
                "dnsx": {
                    "note": (
                        f"Resolve {len(signal)} subdomains from assetfinder and "
                        "inspect CNAME records for potential takeover candidates."
                    )
                }
            },
            "operator_summary": (
                f"Assetfinder discovered {len(signal)} subdomains for {target}. "
                f"High-value targets identified: {len(high_value)}. "
                "Deduplicate with subfinder and amass before DNS resolution."
            ),
        }
