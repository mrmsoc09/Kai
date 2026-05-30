from __future__ import annotations

from dataclasses import dataclass


TOOL_RISK_BANDS: dict[str, int] = {
    # Band 0 — Passive (auto-approved)
    "whois": 0,
    "dns_lookup": 0,
    "shodan_query": 0,
    "crt_sh": 0,
    "wayback": 0,
    "passive_recon": 0,
    # Platform integration (API-mode) — passive by definition, auto-approved
    "misp": 0,
    "cortex": 0,
    "thehive": 0,
    "wazuh": 0,
    "shuffle": 0,
    "defectdojo": 0,
    "opencti": 0,
    "swagger-inspector": 0,
    # Band 1 — Active probing (auto-approved)
    "httpx": 1,
    "subfinder": 1,
    "nmap_basic": 1,
    "nuclei_safe": 1,
    "curl_probe": 1,
    # Band 2 — Intrusive scanning (approval required)
    "ffuf": 2,
    "nuclei_full": 2,
    "sqlmap": 2,
    "nikto": 2,
    "dirsearch": 2,
    "gobuster": 2,
    # Band 3 — Exploitation (blocked)
    "metasploit": 3,
    "exploit_exec": 3,
    "payload_delivery": 3,
}


def get_tool_band(tool_name: str) -> int:
    """Return the risk band for a tool. Defaults to 2 (requires approval) for unknown tools."""
    return TOOL_RISK_BANDS.get(tool_name, 2)


@dataclass
class ToolGovernanceResult:
    allowed: bool
    band: int
    requires_approval: bool
    gate_id: str | None
    reason: str
