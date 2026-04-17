"""
Catalog-backed bug bounty tool adapters.

This module adds a broad set of defensive wrappers while reusing the existing
global tool registry (`core.tools`) and worker execution path.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .evidence_objects import create_evidence_object
from .kai_security_guardrails import ToolRiskTier, set_tool_tier
from .recon_correlation import correlate_observations
from .tool_registry_catalog import ToolCatalogEntry, get_catalog_entry, list_catalog_entries
from .tools import (
    BaseTool,
    ToolAutonomyTier,
    ToolCategory,
    ToolParameter,
    ToolResult,
    ToolStatus,
    get_registry,
    register_tool,
)
from .trilium.sandbox_validator import SandboxValidator


REGISTRY_TOOL_ID_ALIASES: dict[str, str] = {
    "amass": "amass_enum",
    "httpx": "httpx_probe",
    "nuclei": "nuclei_scan",
    "masscan": "masscan_scan",
    "rustscan": "rustscan_quick",
    "zmap": "zmap_scan",
    "shodan": "shodan_host",
    "theharvester": "theharvester",
    "gitleaks": "gitleaks_scan",
}


DEFAULT_ARGS: dict[str, list[str]] = {
    "nuclei": ["-jsonl", "-nt", "-u"],
    "assetfinder": [],
    "findomain": ["--quiet", "-t"],
    "puredns": ["resolve"],
    "waybackurls": [],
    "httprobe": [],
    "tlsx": ["-silent", "-json"],
    "katana": ["-silent", "-jsonl", "-u"],
    "hakrawler": ["-plain", "-url"],
    "gospider": ["-q", "-s"],
    "waymore": ["-i"],
    "dirsearch": ["-u"],
    "gobuster": ["dir", "-u"],
    "wfuzz": ["-c"],
    "nikto": ["-h"],
    "wpscan": ["--url"],
    "dalfox": ["url"],
    "jaeles": ["scan", "-u"],
    "nmap": ["-sV", "-oX", "-"],
    "sqlmap": ["-u"],
    "xsstrike": ["-u"],
    "commix": ["--url"],
    "tplmap": [],
    "searchsploit": [],
    "git-secrets": ["--scan", "-r"],
    "gitrob_alt": ["filesystem"],
}


TOOL_PARSE_MODE: dict[str, str] = {
    "nuclei": "jsonl",
    "assetfinder": "lines",
    "findomain": "lines",
    "puredns": "lines",
    "waybackurls": "lines",
    "httprobe": "lines",
    "tlsx": "jsonl",
    "katana": "jsonl",
    "hakrawler": "lines",
    "gospider": "lines",
    "waymore": "lines",
    "dirsearch": "json_or_lines",
    "gobuster": "lines",
    "wfuzz": "lines",
    "nikto": "json_or_lines",
    "wpscan": "json_or_lines",
    "dalfox": "json_or_lines",
    "jaeles": "json_or_lines",
    "nmap": "nmap_xml",
    "sqlmap": "json_or_lines",
    "xsstrike": "lines",
    "commix": "lines",
    "tplmap": "lines",
    "searchsploit": "lines",
    "git-secrets": "lines",
    "gitrob_alt": "jsonl",
}

_MSF_ALLOWED_MODULE_RE = re.compile(r"^(exploit|auxiliary)/[a-zA-Z0-9_./-]+$")
_MSF_ALLOWED_TARGET_RE = re.compile(r"^[a-zA-Z0-9._:-]+$")


@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    command: list[str]
    duration_ms: float


def _category_from_catalog(value: str) -> ToolCategory:
    if value in {"vulnerability_scanning", "fuzzing_content_discovery"}:
        return ToolCategory.SCANNER
    if value in {"validation_support"}:
        return ToolCategory.VALIDATION
    return ToolCategory.OSINT


def _tier_for_safety(value: str) -> ToolAutonomyTier:
    if value in {"manual_only", "intrusive"}:
        return ToolAutonomyTier.TIER_2_APPROVE
    if value in {"active"}:
        return ToolAutonomyTier.TIER_1_NOTIFY
    return ToolAutonomyTier.TIER_0_AUTO


def _risk_tier_for_autonomy(tier: ToolAutonomyTier) -> ToolRiskTier:
    if tier == ToolAutonomyTier.TIER_0_AUTO:
        return ToolRiskTier.TIER_0_SAFE
    if tier == ToolAutonomyTier.TIER_1_NOTIFY:
        return ToolRiskTier.TIER_1_NOTIFY
    return ToolRiskTier.TIER_2_INTRUSIVE


class CatalogBackedCLITool(BaseTool):
    # Rate-limit tracking per instance (sync tools only — see _enforce_rate_limit)
    _last_run_time: float = 0.0

    def __init__(self, catalog_entry: ToolCatalogEntry):
        self.catalog_entry = catalog_entry
        self.catalog_name = catalog_entry.name
        # Scope lists set externally before execute() — enforcement only fires when non-empty
        self._allowed_scope: list[str] = []
        self._denied_scope: list[str] = []
        self._last_run_time: float = 0.0
        tool_id = REGISTRY_TOOL_ID_ALIASES.get(catalog_entry.name, catalog_entry.name)
        params = [
            ToolParameter("target", "string", "Primary target input"),
            ToolParameter(
                "run_id",
                "string",
                "Execution run identifier",
                required=False,
                default=None,
            ),
            ToolParameter(
                "extra_args",
                "array",
                "Additional CLI arguments",
                required=False,
                default=[],
            ),
            ToolParameter(
                "timeout_seconds",
                "number",
                "Override timeout in seconds",
                required=False,
                default=catalog_entry.timeout_seconds,
            ),
            ToolParameter(
                "retries",
                "number",
                "Retry attempts override",
                required=False,
                default=catalog_entry.retry_policy.max_attempts,
            ),
        ]
        if self.catalog_name == "metasploit-framework":
            params.append(
                ToolParameter(
                    "module",
                    "string",
                    "Metasploit module path (exploit/* or auxiliary/*). CHECK-only mode enforced.",
                    required=False,
                    default=None,
                )
            )
        super().__init__(
            id=tool_id,
            name=f"{catalog_entry.name} adapter",
            description=f"Catalog-backed wrapper for {catalog_entry.name}",
            category=_category_from_catalog(catalog_entry.category),
            autonomy_tier=_tier_for_safety(catalog_entry.safety_classification),
            parameters=params,
            version="1.0.0",
        )

    def _binary(self) -> str:
        return self.catalog_entry.binary_path or self.catalog_name

    _EXTRA_SEARCH_DIRS = [
        "/home/k1-admin/go/bin",
        "/root/go/bin",
        "/usr/local/go/bin",
    ]

    def _which(self) -> str | None:
        binary = self._binary()
        found = shutil.which(binary)
        if found:
            return found
        for directory in self._EXTRA_SEARCH_DIRS:
            candidate = os.path.join(directory, binary)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def _docker_available(self) -> bool:
        return shutil.which("docker") is not None

    @staticmethod
    def _find_wordlist() -> str:
        candidates = [
            "/usr/share/wordlists/dirb/common.txt",
            "/usr/share/dirb/wordlists/common.txt",
            "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt",
        ]
        for path in candidates:
            if Path(path).is_file():
                return path
        return candidates[0]  # binary-missing check happens in execute()

    def _build_command(self, target: str, extra_args: list[str]) -> tuple[list[str], str | None]:
        name = self.catalog_name
        args = list(DEFAULT_ARGS.get(name, []))
        stdin_text: str | None = None
        wordlist = self._find_wordlist()

        if name in {"waybackurls", "httprobe"}:
            stdin_text = f"{target}\n"
        elif name == "gobuster":
            args.extend([target, "-w", wordlist, "-q"])
        elif name == "wfuzz":
            args.extend(["-z", f"file,{wordlist}", "--hc", "404", target])
        elif name == "wpscan":
            args.extend([target, "--format", "json", "--disable-tls-checks"])
        elif name == "dalfox":
            args.extend([target, "--format", "json"])
        elif name == "jaeles":
            args.extend([target, "-json"])
        elif name == "sqlmap":
            args.extend([target, "--batch", "--flush-session"])
        elif name == "xsstrike":
            args.extend([target, "--crawl"])
        elif name == "commix":
            args.extend([target, "--batch"])
        elif name == "gitrob_alt":
            args.extend([target, "--json"])
        elif name in {"searchsploit", "tplmap"}:
            args.append(target)
        elif name == "nmap":
            args.append(target)
        elif name == "katana":
            args.append(target)
        elif name == "hakrawler":
            args.append(target)
        elif name == "gospider":
            args.append(target)
        elif name in {"findomain"}:
            args.append(target)
        elif name in {"puredns", "waymore", "assetfinder", "dirsearch", "nikto"}:
            args.append(target)
        else:
            if "-u" in args or "--url" in args:
                args.append(target)
            elif args:
                args.append(target)
            else:
                args = [target]

        args.extend(extra_args)
        return args, stdin_text

    @staticmethod
    def _normalize_target_host(target: str) -> str:
        text = (target or "").strip()
        if not text:
            return ""
        if "://" in text:
            parsed = urlparse(text)
            return (parsed.hostname or "").strip()
        return text.split("/", 1)[0].strip()

    def _metasploit_check_only_args(self, target: str, module: str | None) -> list[str]:
        safe_target = self._normalize_target_host(target)
        if not safe_target or not _MSF_ALLOWED_TARGET_RE.fullmatch(safe_target):
            raise ValueError("metasploit-framework target must be a host/domain/IP without shell metacharacters")

        resolved_module = str(module or os.getenv("K1_METASPLOIT_CHECK_MODULE", "")).strip()
        if not resolved_module:
            raise ValueError(
                "metasploit-framework requires 'module' (exploit/* or auxiliary/*) for CHECK-only execution"
            )
        if not _MSF_ALLOWED_MODULE_RE.fullmatch(resolved_module):
            raise ValueError(
                "metasploit-framework module must match exploit/* or auxiliary/* and contain only safe characters"
            )

        command_script = f"use {resolved_module}; setg RHOSTS {safe_target}; check; exit -y"
        return ["-q", "-x", command_script]

    _MAX_STDOUT_CHARS = 100 * 1024 * 1024 // 4  # ~25 MB char limit (≈100 MB UTF-8 worst case)

    def _run_once(self, command: list[str], timeout_seconds: int, stdin_text: str | None) -> CommandResult:
        start = time.time()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                input=stdin_text,
            )
            duration_ms = (time.time() - start) * 1000
            stdout = result.stdout.strip()
            if len(stdout) > self._MAX_STDOUT_CHARS:
                stdout = stdout[: self._MAX_STDOUT_CHARS]
            return CommandResult(
                success=result.returncode == 0,
                stdout=stdout,
                stderr=result.stderr.strip(),
                exit_code=result.returncode,
                command=command,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"command timed out after {timeout_seconds}s",
                exit_code=124,
                command=command,
                duration_ms=duration_ms,
            )
        except Exception as exc:  # pragma: no cover - defensive
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=1,
                command=command,
                duration_ms=duration_ms,
            )

    def _run_via_docker(
        self,
        command_args: list[str],
        timeout_seconds: int,
        stdin_text: str | None,
    ) -> CommandResult:
        image = self.catalog_entry.container_image
        if not image:
            return CommandResult(
                success=False,
                stdout="",
                stderr="docker image not configured",
                exit_code=127,
                command=[],
                duration_ms=0.0,
            )
        docker_cmd = ["docker", "run", "--rm", image, *command_args]
        return self._run_once(docker_cmd, timeout_seconds=timeout_seconds, stdin_text=stdin_text)

    def _run_with_retry(
        self,
        command: list[str],
        *,
        retries: int,
        timeout_seconds: int,
        stdin_text: str | None,
    ) -> tuple[CommandResult, int]:
        attempts = max(1, retries)
        last: CommandResult | None = None
        for attempt in range(attempts):
            last = self._run_once(command, timeout_seconds, stdin_text)
            if last.success:
                return last, attempt + 1
            if attempt < attempts - 1:
                time.sleep(self.catalog_entry.retry_policy.backoff_seconds)
        assert last is not None
        return last, attempts

    def _parse_output(self, output: str) -> dict[str, Any]:
        parse_mode = TOOL_PARSE_MODE.get(self.catalog_name, "lines")
        if not output:
            return {"items": []}

        if parse_mode == "jsonl":
            items: list[dict[str, Any]] = []
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        items.append(parsed)
                except Exception:
                    continue
            return {"items": items}

        if parse_mode == "json_or_lines":
            try:
                parsed = json.loads(output)
                return {"items": parsed.get("results", parsed) if isinstance(parsed, dict) else parsed}
            except Exception:
                return {"items": [line for line in output.splitlines() if line.strip()]}

        if parse_mode == "nmap_xml":
            _MAX_XML_BYTES = 50 * 1024 * 1024  # 50 MB cap — guards against XML bomb DoS
            if len(output.encode("utf-8", errors="replace")) > _MAX_XML_BYTES:
                return {"raw_xml": output[:1024], "truncated": True, "error": "output exceeded size cap"}
            hosts: list[dict[str, Any]] = []
            try:
                root = ET.fromstring(output)
                for host in root.findall("host"):
                    address = host.find("address")
                    ports: list[dict[str, Any]] = []
                    ports_elem = host.find("ports")
                    if ports_elem is not None:
                        for port in ports_elem.findall("port"):
                            service = port.find("service")
                            state = port.find("state")
                            ports.append(
                                {
                                    "port": port.attrib.get("portid"),
                                    "protocol": port.attrib.get("protocol"),
                                    "state": state.attrib.get("state") if state is not None else None,
                                    "service": service.attrib.get("name") if service is not None else None,
                                }
                            )
                    hosts.append(
                        {
                            "address": address.attrib.get("addr") if address is not None else None,
                            "ports": ports,
                        }
                    )
                return {"hosts": hosts}
            except Exception:
                return {"raw_xml": output}

        return {"items": [line for line in output.splitlines() if line.strip()]}

    def _enforce_rate_limit(self, tool_name: str) -> None:
        """Sync rate-limit enforcement for the subprocess execution path."""
        from .execution_safety import TOOL_SAFETY_DEFAULTS

        cfg = TOOL_SAFETY_DEFAULTS.get(tool_name, TOOL_SAFETY_DEFAULTS["default"])
        min_interval = 1.0 / cfg.rate_limit_rps if cfg.rate_limit_rps > 0 else 0.0
        now = time.monotonic()
        elapsed = now - self._last_run_time
        if elapsed < min_interval:
            wait = min_interval - elapsed
            time.sleep(wait)  # subprocess path is already blocking; sleep is acceptable here
        self._last_run_time = time.monotonic()

    def execute(self, headers: Optional[Dict[str, str]] = None, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = str(kwargs.get("target") or "").strip()
        module = str(kwargs.get("module") or "").strip() or None
        run_id = kwargs.get("run_id")
        extra_args = kwargs.get("extra_args") if isinstance(kwargs.get("extra_args"), list) else []
        retries = int(kwargs.get("retries") or self.catalog_entry.retry_policy.max_attempts)
        timeout_seconds = int(kwargs.get("timeout_seconds") or self.catalog_entry.timeout_seconds)

        # --- Scope enforcement ---
        from .scope_ingestion_service import NormalizedScope, ScopeEnforcementGate

        _scope = NormalizedScope(
            allowed=list(self._allowed_scope),
            denied=list(self._denied_scope),
        )
        if _scope.allowed:
            _check_target = target or (kwargs.get("tool_inputs") or {}).get("target", "")
            if _check_target and not ScopeEnforcementGate().check_target(str(_check_target), _scope):
                return ToolResult(
                    self.id,
                    ToolStatus.FAILED,
                    {},
                    error=f"Target '{_check_target}' is out of scope — execution blocked",
                )

        # --- Tool governance: Band 3 unconditional block ---
        from .tool_risk_registry import get_tool_band

        _band = get_tool_band(self.catalog_name)
        if _band >= 3:
            return ToolResult(
                self.id,
                ToolStatus.FAILED,
                {},
                error=f"Tool '{self.catalog_name}' is Band 3 (exploitation) — blocked unconditionally",
            )
        # Band 2 gate check must be performed upstream by ToolGovernanceService
        # before execute() is called.  Band 0/1 auto-proceed.

        # --- Sync rate limiting before subprocess ---
        self._enforce_rate_limit(self.catalog_name)

        # Reject extra_args entirely at the API level for Tier 2 tools
        if self.autonomy_tier == ToolAutonomyTier.TIER_2_APPROVE and extra_args:
            return ToolResult(
                self.id,
                ToolStatus.FAILED,
                {},
                error=f"Tool '{self.catalog_name}' is Tier 2 and does not permit extra_args",
            )

        # Enforce allowlist validation on each element of extra_args
        allowed = self.catalog_entry.allowed_extra_args or []
        for arg in extra_args:
            arg_str = str(arg)
            if arg_str not in allowed:
                return ToolResult(
                    self.id,
                    ToolStatus.FAILED,
                    {},
                    error=f"Argument '{arg_str}' is not in the allowlist for tool '{self.catalog_name}'",
                )

        binary = self._which()
        try:
            if self.catalog_name == "metasploit-framework":
                args = self._metasploit_check_only_args(target=target, module=module)
                stdin_text = None
            else:
                args, stdin_text = self._build_command(target, [str(arg) for arg in extra_args])
        except ValueError as exc:
            return ToolResult(
                self.id,
                ToolStatus.FAILED,
                {},
                error=str(exc),
            )
        if binary is None and self.catalog_entry.execution_mode in {"docker", "optional"}:
            if self._docker_available() and self.catalog_entry.container_image:
                result = self._run_via_docker(args, timeout_seconds=timeout_seconds, stdin_text=stdin_text)
                attempts = 1
                command = result.command
            else:
                return ToolResult(
                    self.id,
                    ToolStatus.FAILED,
                    {},
                    error=(
                        f"binary '{self._binary()}' not found and docker fallback unavailable "
                        f"for tool '{self.catalog_name}'"
                    ),
                )
        elif binary is None:
            return ToolResult(
                self.id,
                ToolStatus.FAILED,
                {},
                error=f"binary '{self._binary()}' not found in PATH",
            )
        else:
            command = [binary, *args]
            result, attempts = self._run_with_retry(
                command,
                retries=retries,
                timeout_seconds=timeout_seconds,
                stdin_text=stdin_text,
            )

        parsed = self._parse_output(result.stdout)
        evidence = create_evidence_object(
            tool=self.id,
            target=target or self.catalog_name,
            run_id=run_id,
            evidence_type=self.catalog_entry.category,
            structured_data={
                "tool": self.catalog_name,
                "parsed": parsed,
                "exit_code": result.exit_code,
            },
            raw_payload={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "command": command,
                "attempts": attempts,
            },
            confidence_score=0.8 if result.success else 0.2,
            scope_status="validated",
            description=f"{self.catalog_name} execution",
        )
        output = {
            "target": target,
            "module": module,
            "parsed": parsed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "command": command,
            "attempts": attempts,
            "catalog_entry": self.catalog_entry.as_dict(),
            "evidence": evidence,
            "guardrails": (
                {"mode": "check_only", "enforced": True}
                if self.catalog_name == "metasploit-framework"
                else {"mode": "standard", "enforced": False}
            ),
        }
        status = ToolStatus.COMPLETED if result.success else ToolStatus.FAILED
        return ToolResult(
            self.id,
            status,
            output,
            error=None if result.success else result.stderr,
            execution_time_ms=result.duration_ms,
            metadata={
                "attempts": attempts,
                "execution_mode": self.catalog_entry.execution_mode,
                "tool_name": self.catalog_name,
            },
        )


class IntegrationHookTool(BaseTool):
    def __init__(self, catalog_entry: ToolCatalogEntry):
        self.catalog_entry = catalog_entry
        tool_id = REGISTRY_TOOL_ID_ALIASES.get(catalog_entry.name, catalog_entry.name)
        super().__init__(
            id=tool_id,
            name=f"{catalog_entry.name} integration hook",
            description=f"Manual integration hook for {catalog_entry.name}",
            category=ToolCategory.ORCHESTRATION,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("target", "string", "Target URL/host/path"),
                ToolParameter("run_id", "string", "Execution run identifier", required=False, default=None),
            ],
            version="1.0.0",
        )

    def execute(self, headers: Optional[Dict[str, str]] = None, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = kwargs.get("target")
        run_id = kwargs.get("run_id")
        collection_summary: dict[str, Any] | None = None
        if self.catalog_entry.name in {"postman_collection_export", "insomnia_collection_export"}:
            try:
                path = Path(str(target)).expanduser().resolve()
                # Restrict collection reads to the designated upload/artifact directory only.
                import os as _os
                allowed_root = Path(
                    _os.getenv("K1_ARTIFACTS_ROOT", "").strip() or "artifacts"
                ).resolve()
                try:
                    path.relative_to(allowed_root)
                except ValueError:
                    collection_summary = None
                else:
                    if path.exists() and path.is_file():
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        collection_summary = {
                            "source_path": str(path),
                            "top_level_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
                            "size_bytes": path.stat().st_size,
                        }
            except Exception:
                collection_summary = None
        payload = {
            "status": "integration_hook",
            "tool": self.catalog_entry.name,
            "target": target,
            "run_id": run_id,
            "message": (
                "Manual operator integration required. "
                "No autonomous external submission/exploitation was performed."
            ),
            "catalog_entry": self.catalog_entry.as_dict(),
            "collection_summary": collection_summary,
        }
        return ToolResult(self.id, ToolStatus.COMPLETED, payload)


class InternalCorrelationTool(BaseTool):
    def __init__(self):
        super().__init__(
            id="k1_correlation",
            name="K1 Correlation",
            description="Deterministic host/port/url correlation from normalized inputs.",
            category=ToolCategory.ANALYSIS,
            autonomy_tier=ToolAutonomyTier.TIER_0_AUTO,
            parameters=[
                ToolParameter("target", "string", "Primary target"),
                ToolParameter("inputs", "array", "Optional normalized input list", required=False, default=[]),
                ToolParameter("signals", "array", "Alias input list", required=False, default=[]),
            ],
            version="1.0.0",
        )

    def execute(self, headers: Optional[Dict[str, str]] = None, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = str(kwargs.get("target") or "")
        inputs = kwargs.get("inputs") if isinstance(kwargs.get("inputs"), list) else []
        if not inputs and isinstance(kwargs.get("signals"), list):
            inputs = kwargs.get("signals")
        normalized_inputs = [item for item in inputs if isinstance(item, dict)]
        if target:
            normalized_inputs.append({"host": target})
        correlation_result = correlate_observations(normalized_inputs)
        correlation = {
            "target": target,
            "correlation": correlation_result.as_dict(),
            "duplicates_suppressed": bool(correlation_result.duplicate_keys),
            "confidence": 0.55 if correlation_result.hosts else 0.35,
            "notes": "Deterministic correlation based on normalized execution outputs.",
        }
        return ToolResult(self.id, ToolStatus.COMPLETED, correlation)


class PriorityRankingTool(BaseTool):
    def __init__(self):
        super().__init__(
            id="k1_priority_ranking",
            name="K1 Priority Ranking",
            description="Deterministic ranking of candidate targets from observed signals.",
            category=ToolCategory.ANALYSIS,
            autonomy_tier=ToolAutonomyTier.TIER_0_AUTO,
            parameters=[
                ToolParameter("target", "string", "Primary target"),
                ToolParameter("signals", "array", "Optional signal list", required=False, default=[]),
            ],
            version="1.0.0",
        )

    def execute(self, headers: Optional[Dict[str, str]] = None, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = str(kwargs.get("target") or "")
        signals = kwargs.get("signals") if isinstance(kwargs.get("signals"), list) else []
        normalized_signals = [item for item in signals if isinstance(item, dict)]
        correlation = correlate_observations(normalized_signals)
        top_signal_score = correlation.priority_queue[0]["priority_score"] if correlation.priority_queue else 0
        score = min(100, 20 + len(normalized_signals) * 4 + int(top_signal_score * 0.5))
        return ToolResult(
            self.id,
            ToolStatus.COMPLETED,
            {
                "target": target,
                "priority_score": score,
                "priority_bucket": "high" if score >= 70 else "medium" if score >= 40 else "low",
                "signal_count": len(normalized_signals),
                "priority_queue": correlation.priority_queue[:25],
                "method": "deterministic_rule_v1",
            },
        )


class K1SandboxCriticTool(BaseTool):
    def __init__(self):
        super().__init__(
            id="k1_sandbox_critic",
            name="K1 Sandbox Critic",
            description="Deterministic Stage 7 critic loop executed in-mission.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_0_AUTO,
            parameters=[
                ToolParameter("target", "string", "Target URL/host"),
                ToolParameter(
                    "payload",
                    "string",
                    "PoC payload to validate",
                    required=False,
                    default="print('BLOCKED')",
                ),
                ToolParameter(
                    "payload_type",
                    "string",
                    "python or shell payload type",
                    required=False,
                    default="python",
                    enum=["python", "shell"],
                ),
                ToolParameter(
                    "max_attempts",
                    "number",
                    "Maximum critic attempts",
                    required=False,
                    default=2,
                ),
                ToolParameter(
                    "program_id",
                    "string",
                    "Program UUID used for Stage 7 scope authorization",
                    required=False,
                    default=None,
                ),
                ToolParameter(
                    "workflow_id",
                    "string",
                    "Workflow UUID used for Stage 7 scoped authorization",
                    required=False,
                    default=None,
                ),
            ],
            version="1.0.0",
        )

    @staticmethod
    def _run_payload_sync(target: str, payload: str, payload_type: str, timeout_seconds: int = 35):
        holder: dict[str, Any] = {}

        def _runner() -> None:
            try:
                validator = SandboxValidator(isolated_target_url=target)
                holder["result"] = asyncio.run(
                    validator.execute_payload(payload, payload_type=payload_type)
                )
                holder["validator"] = validator
            except Exception as exc:  # pragma: no cover - defensive
                holder["error"] = str(exc)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(timeout_seconds)
        if thread.is_alive():
            return None, "sandbox execution timed out", None
        if holder.get("error"):
            return None, str(holder["error"]), None
        return holder.get("result"), None, holder.get("validator")

    @staticmethod
    def _scope_check_sync(
        *,
        target: str,
        program_id: str,
        workflow_id: str | None,
        timeout_seconds: int = 10,
    ) -> tuple[bool, str | None]:
        holder: dict[str, Any] = {}

        def _runner() -> None:
            try:
                from .authorization_gate import scope_validator_async

                holder["allowed"] = asyncio.run(
                    scope_validator_async(
                        target,
                        program_id,
                        method="exploit_poc_validation",
                        workflow_id=workflow_id,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive
                holder["error"] = str(exc)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(timeout_seconds)
        if thread.is_alive():
            return False, "scope validation timed out"
        if holder.get("error"):
            return False, f"scope validation error: {holder['error']}"
        if not bool(holder.get("allowed")):
            return False, "scope validation denied exploit_poc_validation"
        return True, None

    def execute(self, headers: Optional[Dict[str, str]] = None, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)

        target = str(kwargs.get("target") or "").strip()
        payload = str(kwargs.get("payload") or "print('BLOCKED')")
        payload_type = str(kwargs.get("payload_type") or "python").strip().lower()
        max_attempts = max(1, int(kwargs.get("max_attempts") or 2))
        program_id = str(kwargs.get("program_id") or "").strip()
        workflow_id_raw = str(kwargs.get("workflow_id") or "").strip()
        workflow_id = workflow_id_raw or None

        # Normalize target to URL form expected by sandbox validator.
        sandbox_target = target if target.startswith(("http://", "https://")) else f"https://{target}"
        scope_gate_checked = False
        if program_id:
            scope_gate_checked = True
            allowed, scope_error = self._scope_check_sync(
                target=sandbox_target,
                program_id=program_id,
                workflow_id=workflow_id,
            )
            if not allowed:
                return ToolResult(
                    self.id,
                    ToolStatus.FAILED,
                    {
                        "target": target,
                        "sandbox_target": sandbox_target,
                        "payload_type": payload_type,
                        "attempts": [],
                        "critic_instruction": None,
                    },
                    error=scope_error,
                    metadata={
                        "stage7_contract": True,
                        "attempt_count": 0,
                        "scope_gate_checked": True,
                        "scope_gate_allowed": False,
                    },
                )
        attempts: list[dict[str, Any]] = []
        critic_instruction: str | None = None
        active_payload = payload
        final_status = ToolStatus.FAILED
        final_error: str | None = None

        for attempt in range(1, max_attempts + 1):
            result, invoke_error, validator = self._run_payload_sync(
                sandbox_target,
                active_payload,
                payload_type,
            )
            if invoke_error is not None:
                final_error = invoke_error
                attempts.append(
                    {
                        "attempt": attempt,
                        "success": False,
                        "stderr": invoke_error,
                    }
                )
                break
            if result is None:
                final_error = "sandbox returned no result"
                break
            attempts.append(
                {
                    "attempt": attempt,
                    "success": bool(result.success),
                    "stdout": str(result.stdout or "")[:500],
                    "stderr": str(result.stderr or "")[:500],
                    "error_message": str(result.error_message or "")[:500],
                }
            )
            if result.success:
                final_status = ToolStatus.COMPLETED
                final_error = None
                break
            if validator is not None:
                critic_instruction = validator.generate_critic_instruction(result)
            # Deterministic mutation for the second pass.
            active_payload = "print('VERIFIED: POC')"
            final_error = str(result.error_message or result.stderr or "sandbox validation failed")[:500]

        return ToolResult(
            self.id,
            final_status,
            {
                "target": target,
                "sandbox_target": sandbox_target,
                "payload_type": payload_type,
                "attempts": attempts,
                "critic_instruction": critic_instruction,
            },
            error=final_error,
            metadata={
                "stage7_contract": True,
                "attempt_count": len(attempts),
                "scope_gate_checked": scope_gate_checked,
                "scope_gate_allowed": True if scope_gate_checked else None,
            },
        )


def _should_use_hook(entry: ToolCatalogEntry) -> bool:
    if entry.safety_classification == "manual_only":
        return True
    return entry.execution_mode == "optional" and not entry.binary_path


def _register_with_tier(tool: BaseTool) -> None:
    register_tool(tool)
    set_tool_tier(tool.id, _risk_tier_for_autonomy(tool.autonomy_tier))


def catalog_name_to_registry_tool_id(name: str) -> str:
    return REGISTRY_TOOL_ID_ALIASES.get(name, name)


def register_bugbounty_tools() -> None:
    """
    Register catalog-backed wrappers for bug bounty tools missing from the current registry.

    Existing adapters are not replaced to preserve already validated behavior.
    """
    registry = get_registry()
    if registry.get("k1_correlation") is None:
        _register_with_tier(InternalCorrelationTool())
    if registry.get("k1_sandbox_critic") is None:
        _register_with_tier(K1SandboxCriticTool())
    if registry.get("k1_priority_ranking") is None:
        _register_with_tier(PriorityRankingTool())
    for entry in list_catalog_entries(enabled_only=False):
        tool_id = catalog_name_to_registry_tool_id(entry.name)
        if registry.get(tool_id) is not None:
            continue
        if _should_use_hook(entry):
            _register_with_tier(IntegrationHookTool(entry))
            continue
        if not entry.binary_path:
            continue
        _register_with_tier(CatalogBackedCLITool(entry))


def tool_entry_or_none(tool_name: str) -> ToolCatalogEntry | None:
    return get_catalog_entry(tool_name)
