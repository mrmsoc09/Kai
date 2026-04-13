"""
Enhanced DNSX Resolver Agent for K1 Platform

Provides three primary functions:
1. Validation: Resolving subdomains discovered by Amass/Subfinder
2. DNS Probing: Extracting A, AAAA, CNAME, PTR, and MX records
3. Bruteforcing: High-performance DNS bruteforcing using K1 wordlists

Features:
- Listener mode: Piped input from stdin (Subfinder/Amass chains)
- DNS Registry normalization: Maps dnsx output to DnsRegistry Pydantic model
- Output deduplication: Automatic IP/record deduplication
- V-RAD telemetry: Real-time metric push to dashboard
- Wildcard detection: Uses dnsx -wd flag to filter false positives
- Sovereign Network Layer: DoH/custom resolver support
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)

from ..base_tool_agent import BaseToolAgent
from .schemas import (
    DnsProbeResult,
    DnsRecord,
    DnsRecordType,
    DnsRegistry,
    ResolutionStatus,
)

# Cloud services indicating potential subdomain takeover
_TAKEOVER_CNAME_PATTERNS = [
    "github.io", "s3.amazonaws.com", "azurewebsites.net",
    "herokudns.com", "herokuapp.com", "ghost.io", "fastly.net",
    "surge.sh", "readme.io", "zendesk.com", "helpscout.net",
    "freshdesk.com", "uservoice.com", "desk.com", "unbounce.com",
    "fly.io", "netlify.com", "vercel.app",
]

# Cloudflare IP ranges (CDN noise)
_CF_PREFIXES = {
    "104.16.", "104.17.", "104.18.", "104.19.", "104.20.",
    "104.21.", "172.64.", "172.65.", "162.159."
}

# Other common CDN providers
_CDN_PREFIXES = _CF_PREFIXES | {
    "13.32.", "13.33.", "13.34.", "13.35.",  # CloudFront
    "143.204.", "144.220.",  # Akamai
    "37.77.", "37.78.",  # Fastly
}


class DnsxAgent(BaseToolAgent):
    """
    Enhanced DNS Resolver Agent with listener mode, deduplication, and V-RAD integration.

    Execution modes:
    1. Standard: dnsx -l subdomains.txt (file-based)
    2. Listener: Read subdomains from stdin (piped from Amass/Subfinder)
    3. Brute: dnsx -d target -w wordlist.txt (bruteforce mode)
    """

    TOOL_NAME = "dnsx"
    DEFAULT_TIMEOUT_SECONDS = 300
    MAX_THREADS = 100
    RETRY_COUNT = 3

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._telemetry_hook: Callable | None = None
        self._listener_mode = False
        self._input_buffer: list[str] = []
        self._dedup_cache: dict[str, DnsRegistry] = {}
        self._metrics = {
            "total_probed": 0,
            "total_resolved": 0,
            "total_wildcards": 0,
            "total_takeovers": 0,
            "resolution_success_rate": 0.0,
            "avg_record_density": 0.0,
        }

    def register_telemetry_hook(self, hook: Callable[[str, str | float], None]) -> None:
        """Register callback for real-time V-RAD telemetry push.

        Args:
            hook: Callable(metric_name: str, value: str | float) -> None
        """
        self._telemetry_hook = hook

    def _push_telemetry(self, metric_name: str, value: str | float) -> None:
        """Push metric to V-RAD dashboard via telemetry hook."""
        if self._telemetry_hook:
            try:
                self._telemetry_hook(metric_name, value)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Telemetry push failed: {e}")

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        """Build dnsx command with high-concurrency settings.

        Supports three modes:
        1. Resolver: -l <file> (resolve from list)
        2. Listener: stdin piping
        3. Brute: -d <domain> -w <wordlist>
        """
        opts = options or {}
        self._listener_mode = bool(opts.get("listener_mode", False))
        brute_mode = bool(opts.get("brute", False))

        binary = str(opts.get("binary_path", "dnsx"))
        threads = int(opts.get("threads", self.MAX_THREADS))
        retries = int(opts.get("retries", self.RETRY_COUNT))

        # Base command with high-performance flags
        cmd = [binary, "-silent", "-json", "-v"]
        cmd += ["-t", str(threads)]
        cmd += ["-r", str(retries)]

        # Wildcard detection (CRITICAL for accuracy)
        if opts.get("wildcard_detection", True):
            cmd += ["-wd", target]

        # Record types
        cmd.append("-a")  # A records
        if opts.get("ipv6", True):
            cmd.append("-aaaa")  # IPv6
        if opts.get("cname", True):
            cmd.append("-cname")  # CNAME records
        if opts.get("mx", False):
            cmd.append("-mx")  # MX records
        if opts.get("ns", False):
            cmd.append("-ns")  # Nameserver records
        if opts.get("txt", False):
            cmd.append("-txt")  # TXT records

        # Response code extraction
        cmd.append("-resp")

        # Resolver configuration (Sovereign Network Layer support)
        resolver = str(opts.get("resolver", "")).strip()
        if resolver:
            if resolver.lower() in {"doh", "dns-over-https"}:
                cmd += ["-doh"]
            elif resolver and resolver != "system":
                cmd += ["-r", resolver]

        # Input source
        if brute_mode:
            wordlist = str(opts.get("wordlist", "")).strip()
            if wordlist:
                cmd += ["-w", wordlist]
            cmd += ["-d", target]
        elif not self._listener_mode:
            input_file = str(opts.get("input_file", "subdomains.txt"))
            cmd += ["-l", input_file]

        return cmd

    def build_input_stream(self, target: str, options: dict[str, Any] | None = None) -> str | None:
        """Build stdin data for listener mode (piped input from Amass/Subfinder).

        Returns:
            Newline-delimited subdomains, or None if not in listener mode.
        """
        opts = options or {}
        if not self._listener_mode:
            return None

        input_source = opts.get("input_data", [])
        if isinstance(input_source, str):
            return input_source

        if isinstance(input_source, list):
            return "\n".join(str(item).strip() for item in input_source if item)

        return None

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        """Parse dnsx JSON output into findings list.

        Each JSON line is a single DNS resolution result:
        {
          "host": "subdomain.target.com",
          "a": ["1.2.3.4"],
          "aaaa": ["::1"],
          "cname": ["target.cloudfront.net"],
          "mx": [],
          "status_code": "200",
          "timestamp": "2024-04-12T12:34:56Z"
        }
        """
        findings: list[dict[str, Any]] = []
        seen_fqdns: set[str] = set()

        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            fqdn = str(data.get("host", "")).strip().lower()
            if not fqdn or fqdn in seen_fqdns:
                continue

            seen_fqdns.add(fqdn)

            # Validate FQDN is subdomain of target
            if not (fqdn == target.lower() or fqdn.endswith(f".{target.lower()}")):
                continue

            # Build DnsRegistry from dnsx output
            registry = self._build_dns_registry(fqdn, target, data)

            # Convert to finding for BaseToolAgent compatibility
            finding = {
                "type": "subdomain",
                "subdomain": fqdn,
                "value": fqdn,
                "target": target,
                "severity": "medium" if registry.has_takeover_risk else "info",
                "confidence": 0.95 if registry.is_alive else 0.6,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": data,
                "context": {
                    "registry_id": str(registry.registry_id),
                    "a_records": registry.a_records,
                    "aaaa_records": registry.aaaa_records,
                    "cname_records": registry.cname_records,
                    "mx_records": registry.mx_records,
                    "ns_records": registry.ns_records,
                    "txt_records": registry.txt_records,
                    "ptr_records": registry.ptr_records,
                    "resolution_status": registry.resolution_status.value,
                    "is_wildcard": registry.is_wildcard,
                    "has_takeover_risk": registry.has_takeover_risk,
                    "takeover_cname": registry.takeover_cname,
                    "ip_count": registry.ip_count,
                    "record_count": registry.record_count,
                    "http_status_code": registry.http_status_code,
                },
                "recommended_next_tools": ["httpx"],
                "recommended_next_actions": ["probe_http"],
                "dns_registry": registry.model_dump(),
            }

            findings.append(finding)
            self._metrics["total_probed"] += 1

        # Calculate metrics
        resolved_count = sum(1 for f in findings if not f["context"]["is_wildcard"])
        self._metrics["total_resolved"] = resolved_count
        self._metrics["total_wildcards"] = len(findings) - resolved_count
        if self._metrics["total_probed"] > 0:
            self._metrics["resolution_success_rate"] = (
                resolved_count / self._metrics["total_probed"] * 100
            )
        if resolved_count > 0:
            total_records = sum(f["context"]["record_count"] for f in findings if f["context"]["record_count"] > 0)
            self._metrics["avg_record_density"] = total_records / resolved_count

        # Push metrics to V-RAD
        self._push_telemetry("RESOLUTION_SUCCESS_RATE", f"{self._metrics['resolution_success_rate']:.1f}%")
        self._push_telemetry("RECORD_DENSITY", f"{self._metrics['avg_record_density']:.1f}")

        return findings

    def _build_dns_registry(self, fqdn: str, target: str, dnsx_data: dict[str, Any]) -> DnsRegistry:
        """Build DnsRegistry from raw dnsx JSON output."""

        # Determine resolution status
        status_code = str(dnsx_data.get("status_code", "")).strip()
        a_records = [r.strip() for r in dnsx_data.get("a", []) if isinstance(r, str) and r.strip()]
        aaaa_records = [r.strip() for r in dnsx_data.get("aaaa", []) if isinstance(r, str) and r.strip()]
        cname_records = [r.strip().lower() for r in dnsx_data.get("cname", []) if isinstance(r, str) and r.strip()]

        # Resolution status logic
        if dnsx_data.get("wildcard"):
            resolution_status = ResolutionStatus.WILDCARD
            is_wildcard = True
        elif a_records or aaaa_records or cname_records:
            resolution_status = ResolutionStatus.RESOLVED
            is_wildcard = False
        elif status_code == "NXDOMAIN":
            resolution_status = ResolutionStatus.NXDOMAIN
            is_wildcard = False
        elif status_code == "SERVFAIL":
            resolution_status = ResolutionStatus.SERVFAIL
            is_wildcard = False
        elif dnsx_data.get("error", "").lower() in {"timeout", "network timeout"}:
            resolution_status = ResolutionStatus.TIMEOUT
            is_wildcard = False
        else:
            resolution_status = ResolutionStatus.UNKNOWN
            is_wildcard = False

        # Detect takeover risk
        has_takeover_risk = False
        takeover_cname = None
        for cname in cname_records:
            if any(pattern in cname for pattern in _TAKEOVER_CNAME_PATTERNS):
                has_takeover_risk = True
                takeover_cname = cname
                break

        # Build registry
        registry = DnsRegistry(
            fqdn=fqdn,
            target_domain=target,
            resolution_status=resolution_status,
            a_records=a_records,
            aaaa_records=aaaa_records,
            cname_records=cname_records,
            mx_records=[r.strip().lower() for r in dnsx_data.get("mx", []) if isinstance(r, str) and r.strip()],
            ns_records=[r.strip().lower() for r in dnsx_data.get("ns", []) if isinstance(r, str) and r.strip()],
            txt_records=[r.strip() for r in dnsx_data.get("txt", []) if isinstance(r, str) and r.strip()],
            ptr_records=[r.strip().lower() for r in dnsx_data.get("ptr", []) if isinstance(r, str) and r.strip()],
            is_wildcard=is_wildcard,
            http_status_code=int(status_code) if status_code.isdigit() else None,
            has_takeover_risk=has_takeover_risk,
            takeover_cname=takeover_cname,
            resolver_used=str(dnsx_data.get("resolver", "system")).lower(),
            raw_dnsx_output=json.dumps(dnsx_data, ensure_ascii=True),
        )

        # Recalculate counts
        registry.post_init_calculate_counts()

        return registry

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Separate signal from noise.

        Signal criteria:
        - RESOLVED status with real IPs/CNAMEs
        - Subdomain takeover candidates (HIGH priority)
        - Non-CDN IPs

        Noise criteria:
        - NXDOMAIN (dead subdomains)
        - Wildcard responses
        - CDN-only IPs (Cloudflare, Akamai, etc)
        - Previously seen (dedup cache)
        """
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for item in findings:
            fqdn = item["subdomain"].lower()
            target = item["target"].lower()
            dedupe_key = f"{target}|subdomain|{fqdn}"

            # Check dedup cache
            if dedupe_key in known or fqdn in self._dedup_cache:
                noise.append(item)
                continue

            ctx = item["context"]
            resolution_status = ctx.get("resolution_status")

            # Wildcard → noise
            if ctx.get("is_wildcard"):
                item["noise_reason"] = "wildcard_detected"
                noise.append(item)
                continue

            # NXDOMAIN → noise
            if resolution_status == "nxdomain":
                item["noise_reason"] = "nxdomain"
                noise.append(item)
                continue

            # Takeover candidate → HIGH signal
            if ctx.get("has_takeover_risk"):
                item["signal_reason"] = "subdomain_takeover_candidate"
                item["severity"] = "high"
                signal.append(item)
                self._metrics["total_takeovers"] += 1
                self._push_telemetry("TAKEOVER_RISK_FOUND", fqdn)
                continue

            # CDN-only IPs → noise
            ips = ctx.get("a_records", []) + ctx.get("aaaa_records", [])
            if ips and all(any(ip.startswith(p) for p in _CDN_PREFIXES) for ip in ips):
                item["noise_reason"] = "cdn_only_ip"
                noise.append(item)
                continue

            # RESOLVED with records → signal
            if resolution_status == "resolved" and (ips or ctx.get("cname_records")):
                item["signal_reason"] = "resolved_valid_records"
                signal.append(item)
                self._push_telemetry("NODE_ACTIVE", fqdn)
                continue

            # Default: signal if not explicitly noise
            signal.append(item)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        """Generate instructions for next agent (HTTP probing)."""
        resolved = [s["subdomain"] for s in signal]
        takeover_candidates = [
            s for s in signal if s.get("signal_reason") == "subdomain_takeover_candidate"
        ]
        return {
            "next_agent": "httpx",
            "action": "probe_http_services",
            "target": target,
            "input_subdomains": resolved,
            "takeover_candidates": [t["subdomain"] for t in takeover_candidates],
            "instructions": (
                f"HTTP probe {len(resolved)} resolved subdomains. "
                + (
                    f"PRIORITY: {len(takeover_candidates)} takeover candidates: "
                    + ", ".join(t["subdomain"] for t in takeover_candidates[:3])
                    if takeover_candidates
                    else "No takeover risks detected."
                )
            ),
        }
