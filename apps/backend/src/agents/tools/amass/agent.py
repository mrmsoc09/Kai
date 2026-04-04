from __future__ import annotations

from typing import Any

from ..base_tool_agent import BaseToolAgent

_HIGH_SIGNAL_KEYWORDS = {
    "admin", "api", "staging", "internal", "jenkins", "grafana",
    "vault", "k8s", "dev", "portal", "dashboard", "backend",
    "gateway", "graphql", "rest", "swagger", "debug", "mgmt",
}
_NOISE_KEYWORDS = {"mail", "smtp", "ftp", "cdn", "mx", "pop", "imap"}


class AmassAgent(BaseToolAgent):
    TOOL_NAME = "amass"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        # Amass v5.0.0 syntax focus: enum -d and intel -d
        if opts.get("intel"):
            # Intel mode for ASN/Org mapping
            cmd = ["amass", "intel", "-d", target, "-whois"]
        else:
            # Standard passive enumeration
            cmd = ["amass", "enum", "-passive", "-d", target]
        
        if opts.get("brute"):
            cmd.append("-brute")
        if opts.get("config"):
            cmd += ["-config", opts["config"]]
        if opts.get("output_file"):
            cmd += ["-o", opts["output_file"]]
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip source annotation if present (amass verbose format: "subdomain (source)")
            subdomain = line.split(" ")[0].strip()
            if not (subdomain.endswith(f".{target}") or subdomain == target):
                continue
            source = "amass"
            if "(" in line and ")" in line:
                source = line[line.index("(") + 1:line.index(")")]
            findings.append({
                "subdomain": subdomain,
                "value": subdomain,
                "source": source,
                "target": target,
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            label = item["subdomain"].lower().split(".")[0]
            if any(kw in label for kw in _HIGH_SIGNAL_KEYWORDS):
                item["signal_reason"] = "high_signal_keyword"
                signal.append(item)
            elif any(kw in label for kw in _NOISE_KEYWORDS):
                item["noise_reason"] = "low_signal_keyword"
                noise.append(item)
            else:
                signal.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        subdomains = [s["subdomain"] for s in signal]
        asn_note = (
            "Run: amass intel -org '<Company Name>' to find related ASNs. "
            "Then enumerate each ASN for related infrastructure."
        )
        return {
            "next_agent": "dnsx",
            "action": "resolve_subdomains",
            "target": target,
            "input_subdomains": subdomains,
            "asn_enumeration_note": asn_note,
            "instructions": (
                "Combine amass results with subfinder output, deduplicate with sort -u, "
                "then feed combined list to dnsx for DNS resolution."
            ),
        }
