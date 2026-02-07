"""
Layer 1: Recon & Asset Discovery adapters.

These are thin wrappers around common recon binaries/APIs so they can be
orchestrated via ToolRunner/Celery with consistent safety defaults.
All tools are best-effort: if a binary/API key is missing they return a
FAILED ToolResult with a clear error instead of throwing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .tools import (
    BaseTool,
    ToolParameter,
    ToolCategory,
    ToolAutonomyTier,
    ToolResult,
    ToolStatus,
    register_tool,
    get_registry,
)
from .tool_adapters_osint import CLITool, CommandSpec  # reuse lightweight runner
from .kai_security_guardrails import set_tool_tier, ToolRiskTier


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _register(tool: BaseTool):
    """Idempotent registration helper."""
    registry = get_registry()
    if registry.get(tool.id):
        return
    register_tool(tool)


# ---------------------------------------------------------------------------
# Recon tools
# ---------------------------------------------------------------------------


class AssetfinderTool(CLITool):
    binary_name = "assetfinder"

    def __init__(self):
        super().__init__(
            id="assetfinder_enum",
            name="Assetfinder",
            description="Fast subdomain enumeration via assetfinder.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("domain", "string", "Domain to enumerate")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        domain = kwargs["domain"]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, [domain], timeout=180))
        elapsed = (time.time() - start) * 1000

        output = {"domain": domain, "subdomains": [l.strip() for l in stdout.splitlines() if l.strip()]}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class FindomainTool(CLITool):
    binary_name = "findomain"

    def __init__(self):
        super().__init__(
            id="findomain_enum",
            name="Findomain",
            description="Subdomain enumeration via findomain (passive by default).",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("domain", "string", "Domain to enumerate")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        domain = kwargs["domain"]
        args = ["--quiet", "-t", domain]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000
        output = {"domain": domain, "subdomains": [l.strip() for l in stdout.splitlines() if l.strip()]}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class DNSDumpsterTool(BaseTool):
    """Placeholder for DNSDumpster integration. Returns clear error until wired."""

    def __init__(self):
        super().__init__(
            id="dnsdumpster_lookup",
            name="DNSDumpster Lookup",
            description="DNS reconnaissance via DNSDumpster (requires API integration).",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("domain", "string", "Domain to query")],
            version="0.0.1",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        return ToolResult(
            self.id,
            ToolStatus.FAILED,
            {"domain": kwargs.get("domain")},
            error="DNSDumpster API integration not configured; set DNSDUMPSTER_API_URL/TOKEN",
        )


class MasscanTool(CLITool):
    binary_name = "masscan"

    def __init__(self):
        super().__init__(
            id="masscan_scan",
            name="Masscan (rate-limited)",
            description="Fast port scan with conservative defaults (--top-ports 100).",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("target", "string", "Target CIDR or host"),
                ToolParameter("ports", "string", "Port list or range", required=False, default="top-100"),
                ToolParameter("rate", "number", "Packet rate", required=False, default=1000),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = kwargs["target"]
        ports = kwargs.get("ports", "top-100")
        rate = int(kwargs.get("rate", 1000))
        port_arg = ["--top-ports", "100"] if ports == "top-100" else ["-p", str(ports)]
        args = ["-oJ", "-", *port_arg, "--rate", str(rate), target]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000
        output = {"target": target, "ports": ports, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class RustScanTool(CLITool):
    binary_name = "rustscan"

    def __init__(self):
        super().__init__(
            id="rustscan_quick",
            name="RustScan",
            description="Fast TCP port discovery using RustScan.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("target", "string", "Target host"),
                ToolParameter("ports", "string", "Port list", required=False, default="1-1000"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = kwargs["target"]
        ports = kwargs.get("ports", "1-1000")
        args = ["-a", target, "-p", str(ports), "--ulimit", "4096"]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000
        output = {"target": target, "ports": ports, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class ZMapTool(CLITool):
    binary_name = "zmap"

    def __init__(self):
        super().__init__(
            id="zmap_scan",
            name="ZMap (conservative)",
            description="Single-port internet scan; rate-limited and gated.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("target", "string", "Target CIDR/host"),
                ToolParameter("port", "number", "Port to scan"),
                ToolParameter("rate", "number", "Packet rate", required=False, default=5000),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = kwargs["target"]
        port = int(kwargs["port"])
        rate = int(kwargs.get("rate", 5000))
        args = ["-p", str(port), target, "-r", str(rate)]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000
        output = {"target": target, "port": port, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class S3ScannerTool(CLITool):
    binary_name = "s3scanner"

    def __init__(self):
        super().__init__(
            id="s3scanner",
            name="S3Scanner",
            description="Find open S3 buckets by name prefix.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("wordlist", "string", "Path to bucket wordlist"),
                ToolParameter("threads", "number", "Threads", required=False, default=10),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        wordlist = Path(kwargs["wordlist"]).expanduser()
        threads = int(kwargs.get("threads", 10))
        if not wordlist.exists():
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=f"wordlist not found: {wordlist}")
        args = ["--threads", str(threads), str(wordlist)]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        output = {"wordlist": str(wordlist), "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class CloudEnumTool(CLITool):
    binary_name = "cloud_enum"

    def __init__(self):
        super().__init__(
            id="cloudenum",
            name="CloudEnum",
            description="Enumerate cloud storage and services for a target org prefix.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("keyword", "string", "Org/keyword prefix")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        keyword = kwargs["keyword"]
        args = ["-k", keyword, "-t", "10"]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        output = {"keyword": keyword, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class GrayhatWarfareTool(CLITool):
    binary_name = "grayhatwarfare"

    def __init__(self):
        super().__init__(
            id="grayhatwarfare",
            name="GrayhatWarfare Buckets",
            description="Query GrayhatWarfare for exposed buckets (API key required).",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("query", "string", "Search query")],
            version="0.1.0",
        )

    def _which(self) -> Optional[str]:
        return shutil.which(self.binary_name) or shutil.which("ghw")

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        api_key = os.getenv("GRAYHAT_API_KEY")
        if not api_key:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="GRAYHAT_API_KEY env var not set")
        query = kwargs["query"]
        args = ["search", query, "--key", api_key, "--json"]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self._which() or self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000
        output = {"query": query, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class SherlockTool(CLITool):
    binary_name = "sherlock"

    def __init__(self):
        super().__init__(
            id="sherlock_user",
            name="Sherlock Username Finder",
            description="Find usernames across platforms using sherlock.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("username", "string", "Username to search")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        username = kwargs["username"]
        args = [username, "--print-found"]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        output = {"username": username, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class HoleheTool(CLITool):
    binary_name = "holehe"

    def __init__(self):
        super().__init__(
            id="holehe_email",
            name="Holehe Email Enumeration",
            description="Check if an email is registered on popular sites.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("email", "string", "Email address")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        email = kwargs["email"]
        args = ["-u", email, "--only-used"]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=240))
        elapsed = (time.time() - start) * 1000
        output = {"email": email, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class WhatWebTool(CLITool):
    binary_name = "whatweb"

    def __init__(self):
        super().__init__(
            id="whatweb_fingerprint",
            name="WhatWeb Fingerprint",
            description="Fingerprint technologies of a target URL.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("url", "string", "Target URL")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        url = kwargs["url"]
        args = ["-a", "3", url]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000
        output = {"url": url, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


# ---------------------------------------------------------------------------
# Registration entrypoint
# ---------------------------------------------------------------------------


def register_phase2_recon_tools():
    """Register expanded recon / asset discovery tools."""
    tools = [
        AssetfinderTool(),
        FindomainTool(),
        DNSDumpsterTool(),
        MasscanTool(),
        RustScanTool(),
        ZMapTool(),
        S3ScannerTool(),
        CloudEnumTool(),
        GrayhatWarfareTool(),
        SherlockTool(),
        HoleheTool(),
        WhatWebTool(),
    ]
    for tool in tools:
        _register(tool)
        # Map risk tier for guardrails
        if tool.autonomy_tier == ToolAutonomyTier.TIER_0_AUTO:
            set_tool_tier(tool.id, ToolRiskTier.TIER_0_SAFE)
        elif tool.autonomy_tier == ToolAutonomyTier.TIER_1_NOTIFY:
            set_tool_tier(tool.id, ToolRiskTier.TIER_1_NOTIFY)
        else:
            set_tool_tier(tool.id, ToolRiskTier.TIER_2_INTRUSIVE)

