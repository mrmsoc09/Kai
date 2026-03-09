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

from .evidence_objects import create_evidence_object
from .secret_manager import get_secret_manager, SecretManagerError
from .kai_security_guardrails import set_tool_tier, ToolRiskTier
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
            parameters=[
                ToolParameter("ip", "string", "IP address to query"),
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        try:
            api_key = get_secret_manager().get_required("SHODAN_API_KEY")
        except SecretManagerError as exc:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(exc))

        ip = kwargs["ip"]
        run_id = kwargs.get("run_id")
        url = f"https://api.shodan.io/shodan/host/{ip}"
        start = time.time()
        try:
            resp = httpx.get(url, params={"key": api_key}, timeout=30)
            elapsed = (time.time() - start) * 1000
            if resp.status_code != 200:
                return ToolResult(self.id, ToolStatus.FAILED, {}, error=f"HTTP {resp.status_code}: {resp.text}", execution_time_ms=elapsed)
            data = resp.json()
            evidence = create_evidence_object(
                tool=self.id,
                target=ip,
                run_id=run_id,
                evidence_type="host_intel",
                structured_data={
                    "ip": ip,
                    "ports": data.get("ports", []),
                    "vulns": data.get("vulns", {}),
                },
                raw_payload=data,
                confidence_score=0.8,
                scope_status="validated",
                description="shodan host response",
            )
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED,
                {
                    "ip": ip,
                    "ports": data.get("ports", []),
                    "vulns": data.get("vulns", {}),
                    "raw": data,
                    "evidence": evidence,
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


class DnsxTool(CLITool):
    binary_name = "dnsx"

    def __init__(self):
        super().__init__(
            id="dnsx",
            name="DNSX Resolution",
            description="Resolve and validate DNS records for discovered hosts.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("target", "string", "Host or domain to resolve"),
                ToolParameter("record_type", "string", "DNS record type", required=False, default="a"),
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = kwargs["target"]
        record_type = str(kwargs.get("record_type", "a")).lower()
        run_id = kwargs.get("run_id")

        args = ["-silent", "-json", "-a", "-resp", "-l", "-"]
        start = time.time()
        success, stdout, stderr = self._run(
            CommandSpec(self.binary_name, args, timeout=180, workdir=None)
        )
        elapsed = (time.time() - start) * 1000

        # dnsx expects stdin for list mode; fallback to direct single target invocation.
        if not success:
            args = ["-silent", "-json", "-a", "-resp", "-d", target]
            success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=180))

        records: List[Dict[str, Any]] = []
        for line in stdout.splitlines():
            try:
                records.append(json.loads(line))
            except Exception:
                continue

        evidence = create_evidence_object(
            tool=self.id,
            target=target,
            run_id=run_id,
            evidence_type="dns",
            structured_data={"target": target, "record_type": record_type, "records": records},
            raw_payload={"stdout": stdout, "stderr": stderr, "records": records},
            confidence_score=0.85 if success else 0.2,
            scope_status="validated",
            description="dnsx resolution results",
        )
        output = {"target": target, "record_type": record_type, "records": records, "evidence": evidence}
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
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        host = kwargs["host"]
        ports = kwargs.get("ports", "top-100")
        run_id = kwargs.get("run_id")
        args = ["-host", host, "-silent"]
        if ports:
            args.extend(["-p", ports])

        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=240))
        elapsed = (time.time() - start) * 1000

        open_ports = [line.strip() for line in stdout.splitlines() if line.strip()]
        evidence = create_evidence_object(
            tool=self.id,
            target=host,
            run_id=run_id,
            evidence_type="portscan",
            structured_data={"host": host, "open_ports": open_ports},
            raw_payload={"stdout": stdout, "stderr": stderr, "ports": open_ports},
            confidence_score=0.8 if success else 0.2,
            scope_status="validated",
            description="naabu open ports",
        )
        output = {"host": host, "ports": open_ports, "raw": stdout, "evidence": evidence}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class GauTool(CLITool):
    binary_name = "gau"

    def __init__(self):
        super().__init__(
            id="gau",
            name="GAU URL Harvest",
            description="Collect historical URLs from public archives for a domain.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("domain", "string", "Domain to enumerate URLs for"),
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        domain = kwargs["domain"]
        run_id = kwargs.get("run_id")

        args = ["--subs", domain]
        start = time.time()
        success, stdout, stderr = self._run(CommandSpec(self.binary_name, args, timeout=240))
        elapsed = (time.time() - start) * 1000

        urls = [line.strip() for line in stdout.splitlines() if line.strip()]
        evidence = create_evidence_object(
            tool=self.id,
            target=domain,
            run_id=run_id,
            evidence_type="crawl",
            structured_data={"domain": domain, "url_count": len(urls), "urls": urls[:2000]},
            raw_payload={"stdout": stdout, "stderr": stderr, "url_count": len(urls)},
            confidence_score=0.75 if success else 0.25,
            scope_status="validated",
            description="gau historical URLs",
        )
        output = {"domain": domain, "urls": urls, "evidence": evidence}
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
            parameters=[
                ToolParameter("target", "string", "URL or host to probe"),
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = kwargs["target"]
        run_id = kwargs.get("run_id")
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

        evidence = create_evidence_object(
            tool=self.id,
            target=target,
            run_id=run_id,
            evidence_type="http",
            structured_data={"target": target, "records": records},
            raw_payload={"stdout": stdout, "stderr": stderr},
            confidence_score=0.85 if success else 0.2,
            scope_status="validated",
            description="httpx probe results",
        )
        output = {"target": target, "records": records, "raw": stdout, "evidence": evidence}
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
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
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
        run_id = kwargs.get("run_id")

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

        evidence = create_evidence_object(
            tool=self.id,
            target=url,
            run_id=run_id,
            evidence_type="http",
            structured_data={"url": url, "results": results},
            raw_payload={"stdout": stdout, "stderr": stderr, "result_count": len(results)},
            confidence_score=0.75 if success else 0.2,
            scope_status="validated",
            description="ffuf content discovery results",
        )
        output = {"url": url, "results": results, "raw": stdout, "evidence": evidence}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class CensysHostTool(BaseTool):
    def __init__(self):
        super().__init__(
            id="censys",
            name="Censys Host Intel",
            description="Retrieve Censys host intelligence for an IP.",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("ip", "string", "IP address to query"),
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        try:
            secret_manager = get_secret_manager()
            api_id = secret_manager.get_required("CENSYS_API_ID")
            api_secret = secret_manager.get_required("CENSYS_API_SECRET")
        except SecretManagerError as exc:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(exc))

        ip = kwargs["ip"]
        run_id = kwargs.get("run_id")
        url = f"https://search.censys.io/api/v2/hosts/{ip}"
        start = time.time()
        try:
            resp = httpx.get(url, auth=(api_id, api_secret), timeout=30)
            elapsed = (time.time() - start) * 1000
            if resp.status_code != 200:
                return ToolResult(
                    self.id,
                    ToolStatus.FAILED,
                    {},
                    error=f"HTTP {resp.status_code}: {resp.text}",
                    execution_time_ms=elapsed,
                )
            data = resp.json()
            result = data.get("result", {})
            services = result.get("services", [])
            evidence = create_evidence_object(
                tool=self.id,
                target=ip,
                run_id=run_id,
                evidence_type="host_intel",
                structured_data={
                    "ip": ip,
                    "service_count": len(services),
                    "services": services,
                },
                raw_payload=data,
                confidence_score=0.8,
                scope_status="validated",
                description="censys host response",
            )
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED,
                {
                    "ip": ip,
                    "services": services,
                    "raw": result,
                    "evidence": evidence,
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_phase1_osint_tools():
    """Register core Phase 1 recon tools into the global registry."""
    tools = [
        AmassTool(),
        ShodanHostTool(),
        TheHarvesterTool(),
        ExifToolMetadata(),
        TrufflehogSecrets(),
        SubfinderTool(),
        DnsxTool(),
        NaabuTool(),
        GauTool(),
        HttpxTool(),
        NucleiTool(),
        FfufTool(),
        CensysHostTool(),
    ]
    for tool in tools:
        register_tool(tool)
        # Map risk tier for guardrails
        if tool.autonomy_tier == ToolAutonomyTier.TIER_0_AUTO:
            set_tool_tier(tool.id, ToolRiskTier.TIER_0_SAFE)
        elif tool.autonomy_tier == ToolAutonomyTier.TIER_1_NOTIFY:
            set_tool_tier(tool.id, ToolRiskTier.TIER_1_NOTIFY)
        else:
            set_tool_tier(tool.id, ToolRiskTier.TIER_2_INTRUSIVE)
