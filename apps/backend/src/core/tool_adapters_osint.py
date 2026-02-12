"""
CLI/API adapters for high-value recon tools (Phase 1)
Implements lightweight wrappers around core utilities so they can be
invoked through the unified tool registry and orchestrated by agents.

Tools implemented:
  - amass (subdomain enum)
  - shodan (host intel via API)
  - theHarvester (email/host/osint)
  - exiftool (metadata extraction)
  - trufflehog (secrets scan)
  - subfinder (subdomain enum)
  - naabu (port scan)
  - httpx (http probe)
  - nuclei (templated vuln scan)
  - ffuf (content fuzz)

All adapters are defensive: if binaries or API keys are missing they
return graceful ToolResult failures with actionable errors instead of
raising.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .tools import (
    BaseTool,
    ToolParameter,
    ToolCategory,
    ToolAutonomyTier,
    ToolResult,
    ToolStatus,
    register_tool,
)


# ---------------------------------------------------------------------------
# Helper base
# ---------------------------------------------------------------------------


@dataclass
class CommandSpec:
    binary: str
    args: List[str]
    workdir: Optional[Path] = None
    timeout: int = 300


class CLITool(BaseTool):
    """Base class for CLI-backed tools with subprocess execution."""

    binary_name: str = ""

    def _which(self) -> Optional[str]:
        return shutil.which(self.binary_name)

    def _run(self, spec: CommandSpec) -> tuple[bool, str, str]:
        if not self._which():
            return False, "", f"binary '{self.binary_name}' not found in PATH"

        try:
            result = subprocess.run(
                [spec.binary, *spec.args],
                cwd=spec.workdir,
                capture_output=True,
                text=True,
                timeout=spec.timeout,
            )
            ok = result.returncode == 0
            return ok, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", f"command timed out after {spec.timeout}s"
        except Exception as e:  # pragma: no cover - defensive
            return False, "", str(e)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


class AmassTool(CLITool):
    binary_name = "amass"

    def __init__(self):
        super().__init__(
            id="amass_enum",
            name="Amass Subdomain Enumeration",
            description="Enumerate subdomains using amass (passive by default).",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("domain", "string", "Domain to enumerate"),
                ToolParameter("passive", "boolean", "Use passive mode", required=False, default=True),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        domain = kwargs.get("domain")
        passive = bool(kwargs.get("passive", True))

        args = ["enum", "-d", domain]
        if passive:
            args.append("-passive")

        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000

        output = {
            "domain": domain,
            "passive": passive,
            "raw": stdout,
            "stderr": stderr,
            "subdomains": [line.strip() for line in stdout.splitlines() if line.strip()],
        }

        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class ShodanHostTool(BaseTool):
    def __init__(self):
        super().__init__(
            id="shodan_host",
            name="Shodan Host Intel",
            description="Retrieve Shodan host data for an IP using SHODAN_API_KEY.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[ToolParameter("ip", "string", "IP address to query")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        api_key = os.getenv("SHODAN_API_KEY")
        if not api_key:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="SHODAN_API_KEY env var not set")

        ip = kwargs["ip"]
        url = f"https://api.shodan.io/shodan/host/{ip}"
        start = time.time()
        try:
            resp = httpx.get(url, params={"key": api_key}, timeout=30)
            elapsed = (time.time() - start) * 1000
            if resp.status_code != 200:
                return ToolResult(self.id, ToolStatus.FAILED, {}, error=f"HTTP {resp.status_code}: {resp.text}", execution_time_ms=elapsed)
            data = resp.json()
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED,
                {
                    "ip": ip,
                    "ports": data.get("ports", []),
                    "vulns": data.get("vulns", {}),
                    "raw": data,
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class TheHarvesterTool(CLITool):
    binary_name = "theHarvester"

    def __init__(self):
        super().__init__(
            id="theharvester",
            name="theHarvester Enumerator",
            description="Gather emails/hosts via theHarvester (passive OSINT)",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("domain", "string", "Domain to enumerate"),
                ToolParameter("sources", "string", "Comma-separated sources (e.g., all,bing,crtsh)", required=False, default="all"),
                ToolParameter("limit", "number", "Result limit", required=False, default=200),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        domain = kwargs["domain"]
        sources = kwargs.get("sources", "all")
        limit = int(kwargs.get("limit", 200))

        args = ["-d", domain, "-b", sources, "-l", str(limit)]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=240))
        elapsed = (time.time() - start) * 1000

        output = {"domain": domain, "sources": sources, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class ExifToolMetadata(CLITool):
    binary_name = "exiftool"

    def __init__(self):
        super().__init__(
            id="exif_metadata",
            name="ExifTool Metadata Extraction",
            description="Extract metadata from a file using exiftool",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_0_AUTO,
            parameters=[ToolParameter("path", "string", "Path to file")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        path = Path(kwargs["path"]).expanduser().resolve()
        if not path.exists():
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=f"file not found: {path}")

        args = ["-json", str(path)]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=60))
        elapsed = (time.time() - start) * 1000

        parsed = []
        if stdout:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = []

        output = {"file": str(path), "metadata": parsed, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class TrufflehogSecrets(CLITool):
    binary_name = "trufflehog"

    def __init__(self):
        super().__init__(
            id="trufflehog",
            name="TruffleHog Secrets Scan",
            description="Scan a repository or directory for secrets",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("target", "string", "Path or git URL to scan"),
                ToolParameter("since_commit", "string", "Optional starting commit", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = kwargs["target"]
        since = kwargs.get("since_commit")

        args = ["filesystem", target, "--json"]
        if since:
            args.extend(["--since-commit", since])

        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000

        findings: List[Dict[str, Any]] = []
        for line in stdout.splitlines():
            try:
                findings.append(json.loads(line))
            except Exception:
                continue

        output = {"target": target, "findings": findings, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class SubfinderTool(CLITool):
    binary_name = "subfinder"

    def __init__(self):
        super().__init__(
            id="subfinder",
            name="Subfinder Enumeration",
            description="Passive subdomain enumeration using subfinder",
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
        args = ["-silent", "-d", domain]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000

        subs = [line.strip() for line in stdout.splitlines() if line.strip()]
        output = {"domain": domain, "subdomains": subs, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class NaabuTool(CLITool):
    binary_name = "naabu"

    def __init__(self):
        super().__init__(
            id="naabu",
            name="Naabu Port Scan",
            description="Fast TCP port scan via naabu",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("host", "string", "Target host"),
                ToolParameter("ports", "string", "Port list/range (optional)", required=False, default="top-100"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        host = kwargs["host"]
        ports = kwargs.get("ports", "top-100")
        args = ["-host", host, "-silent"]
        if ports:
            args.extend(["-p", ports])

        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=240))
        elapsed = (time.time() - start) * 1000

        open_ports = [line.strip() for line in stdout.splitlines() if line.strip()]
        output = {"host": host, "ports": open_ports, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class HttpxTool(CLITool):
    binary_name = "httpx"

    def __init__(self):
        super().__init__(
            id="httpx_probe",
            name="httpx Probe",
            description="HTTP probe with tech + status",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[ToolParameter("target", "string", "URL or host to probe")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = kwargs["target"]
        args = ["-u", target, "-status-code", "-title", "-tech-detect", "-json"]

        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))
        elapsed = (time.time() - start) * 1000

        records: List[Dict[str, Any]] = []
        for line in stdout.splitlines():
            try:
                records.append(json.loads(line))
            except Exception:
                continue

        output = {"target": target, "records": records, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class NucleiTool(CLITool):
    binary_name = "nuclei"

    def __init__(self):
        super().__init__(
            id="nuclei_scan",
            name="Nuclei Scan",
            description="Template-based HTTP vulnerability scan",
            category=ToolCategory.SCANNER,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("target", "string", "Target URL"),
                ToolParameter("severity", "string", "Severity filter", required=False, default="medium,high,critical"),
                ToolParameter("template", "string", "Specific template or directory", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = kwargs["target"]
        severity = kwargs.get("severity", "medium,high,critical")
        template = kwargs.get("template")

        args = ["-u", target, "-severity", severity, "-json"]
        if template:
            args.extend(["-t", template])

        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=600))
        elapsed = (time.time() - start) * 1000

        findings: List[Dict[str, Any]] = []
        for line in stdout.splitlines():
            try:
                findings.append(json.loads(line))
            except Exception:
                continue

        output = {"target": target, "findings": findings, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class FfufTool(CLITool):
    binary_name = "ffuf"

    def __init__(self):
        super().__init__(
            id="ffuf",
            name="FFUF Content Fuzz",
            description="Directory/content fuzzing with ffuf",
            category=ToolCategory.SCANNER,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("url", "string", "Target URL with FUZZ placeholder"),
                ToolParameter("wordlist", "string", "Wordlist path", required=False, default="/usr/share/wordlists/dirb/common.txt"),
                ToolParameter("extensions", "string", "Extensions (csv)", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        url = kwargs["url"]
        wordlist = kwargs.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        extensions = kwargs.get("extensions")

        args = ["-u", url, "-w", wordlist, "-mc", "200,204,301,302,307,401,403", "-json"]
        if extensions:
            args.extend(["-e", extensions])

        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=600))
        elapsed = (time.time() - start) * 1000

        results: List[Dict[str, Any]] = []
        if stdout:
            try:
                parsed = json.loads(stdout)
                results = parsed.get("results", []) if isinstance(parsed, dict) else []
            except Exception:
                results = []

        output = {"url": url, "results": results, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_phase1_osint_tools():
    """Register core Phase 1 recon tools into the global registry."""
    register_tool(AmassTool())
    register_tool(ShodanHostTool())
    register_tool(TheHarvesterTool())
    register_tool(ExifToolMetadata())
    register_tool(TrufflehogSecrets())
    register_tool(SubfinderTool())
    register_tool(NaabuTool())
    register_tool(HttpxTool())
    register_tool(NucleiTool())
    register_tool(FfufTool())
