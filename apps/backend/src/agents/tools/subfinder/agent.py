from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent

# Known CDN IP prefixes (first two octets) to classify as noise
_CDN_PREFIXES = {"104.16", "104.17", "104.18", "104.19", "104.20", "104.21",
                 "172.64", "172.65", "162.159", "188.114"}

# High-signal subdomain keyword patterns
_HIGH_SIGNAL_KEYWORDS = {
    "admin", "api", "staging", "internal", "jenkins", "grafana",
    "vault", "k8s", "dev", "portal", "dashboard", "backend",
    "gateway", "graphql", "rest", "swagger", "debug", "test",
    "mgmt", "management", "console", "kibana", "elastic",
}

# Low-signal / noise keywords
_NOISE_KEYWORDS = {"mail", "smtp", "ftp", "pop", "imap", "cdn", "mx"}


class SubfinderAgent(BaseToolAgent):
    TOOL_NAME = "subfinder"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # Mandatory silent mode for clean output
        cmd = ["subfinder", "-d", target, "-silent"]
        # API-heavy source selection - default to True for maximum impact
        if opts.get("all_sources", True):
            cmd.append("-all")
        # Recursive depth for sub-subdomains
        if opts.get("recursive"):
            cmd.append("-recursive")
        # Resource optimization
        threads = opts.get("threads", 50)
        cmd += ["-t", str(threads)]
        timeout = opts.get("timeout", 30)
        cmd += ["-timeout", str(timeout)]
        if opts.get("output_file"):
            cmd += ["-o", opts["output_file"]]
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Ensure it looks like a subdomain of the target
            if not (line.endswith(f".{target}") or line == target):
                continue
            findings.append({
                "subdomain": line,
                "value": line,
                "source": "subfinder",
                "target": target,
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            sub = item["subdomain"].lower()
            label = sub.split(".")[0]  # leftmost label
            if any(kw in label for kw in _HIGH_SIGNAL_KEYWORDS):
                item["signal_reason"] = "high_signal_keyword"
                signal.append(item)
            elif any(kw in label for kw in _NOISE_KEYWORDS):
                item["noise_reason"] = "low_signal_keyword"
                noise.append(item)
            else:
                # Default to signal — subfinder output is generally useful
                signal.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        subdomains = [s["subdomain"] for s in signal]
        high_value = [
            s["subdomain"] for s in signal
            if s.get("signal_reason") == "high_signal_keyword"
        ]
        return {
            "next_agent": "dnsx",
            "action": "resolve_subdomains",
            "target": target,
            "input_subdomains": subdomains,
            "priority_subdomains": high_value,
            "instructions": (
                "Run dnsx on all subdomains to confirm DNS resolution. "
                "Check CNAME records for subdomain takeover candidates. "
                f"Priority targets: {', '.join(high_value[:5]) if high_value else 'none identified'}."
            ),
        }
