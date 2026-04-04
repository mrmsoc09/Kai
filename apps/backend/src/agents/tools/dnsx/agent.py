from __future__ import annotations

import json
from typing import Any

from ..base_tool_agent import BaseToolAgent

# Cloud services that indicate potential subdomain takeover
_TAKEOVER_CNAME_PATTERNS = [
    "github.io", "s3.amazonaws.com", "azurewebsites.net",
    "herokudns.com", "herokuapp.com", "ghost.io", "fastly.net",
    "surge.sh", "readme.io", "zendesk.com", "helpscout.net",
    "freshdesk.com", "uservoice.com", "desk.com", "unbounce.com",
    "fly.io", "netlify.com", "vercel.app",
]

# Cloudflare IPs — CDN noise
_CF_PREFIXES = {"104.16.", "104.17.", "104.18.", "104.19.", "104.20.",
                "104.21.", "172.64.", "172.65.", "162.159."}


class DnsxAgent(BaseToolAgent):
    TOOL_NAME = "dnsx"

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        input_file = opts.get("input_file", "subdomains.txt")
        # Mandatory CNAME resolution for takeover detection and response codes
        cmd = ["dnsx", "-l", input_file, "-silent", "-a", "-resp", "-cname"]
        # Mandatory wildcard detection to prevent false positives
        if opts.get("wildcard_detection", True):
            cmd += ["-wd", target]
        if opts.get("all_records"):
            cmd += ["-aaaa", "-mx", "-ns"]
        if opts.get("json_output"):
            cmd.append("-json")
        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Try JSON first
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    subdomain = data.get("host", "")
                    findings.append({
                        "subdomain": subdomain,
                        "value": subdomain,
                        "a_records": data.get("a", []),
                        "cname_records": data.get("cname", []),
                        "aaaa_records": data.get("aaaa", []),
                        "mx_records": data.get("mx", []),
                        "status_code": data.get("status_code", ""),
                        "source": "dnsx",
                        "target": target,
                    })
                    continue
                except json.JSONDecodeError:
                    pass
            # Plaintext: "subdomain.target.com [1.2.3.4]"
            parts = line.split()
            if not parts:
                continue
            subdomain = parts[0]
            ips: list[str] = []
            for part in parts[1:]:
                part = part.strip("[]")
                if part:
                    ips.append(part)
            findings.append({
                "subdomain": subdomain,
                "value": subdomain,
                "a_records": ips,
                "cname_records": [],
                "source": "dnsx",
                "target": target,
            })
        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        for item in findings:
            cnames = item.get("cname_records", [])
            ips = item.get("a_records", [])
            # Takeover candidate is always signal
            takeover_cname = next(
                (c for c in cnames if any(p in c for p in _TAKEOVER_CNAME_PATTERNS)),
                None,
            )
            if takeover_cname:
                item["signal_reason"] = "subdomain_takeover_candidate"
                item["takeover_cname"] = takeover_cname
                signal.append(item)
                continue
            # CDN-only IPs → noise
            if ips and all(any(ip.startswith(p) for p in _CF_PREFIXES) for ip in ips):
                item["noise_reason"] = "cdn_only_ip"
                noise.append(item)
                continue
            # No IP and no CNAME → NXDOMAIN noise
            if not ips and not cnames:
                item["noise_reason"] = "nxdomain"
                noise.append(item)
                continue
            signal.append(item)
        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        resolved = [s["subdomain"] for s in signal]
        takeover_candidates = [
            s for s in signal if s.get("signal_reason") == "subdomain_takeover_candidate"
        ]
        return {
            "next_agent": "httpx_probe",
            "action": "probe_http_services",
            "target": target,
            "input_subdomains": resolved,
            "takeover_candidates": [t["subdomain"] for t in takeover_candidates],
            "instructions": (
                f"Probe {len(resolved)} resolved subdomains for HTTP services. "
                + (
                    f"PRIORITY: {len(takeover_candidates)} subdomain takeover candidates found: "
                    + ", ".join(t["subdomain"] for t in takeover_candidates[:3])
                    if takeover_candidates
                    else "No takeover candidates identified."
                )
            ),
        }
