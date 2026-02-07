"""
Layer 3: Exploit validation & simulation adapters.

These wrappers execute common validation tools with conservative defaults
and gated autonomy tiers. They are intended to be triggered only after a
scanner raises a candidate finding. All adapters degrade gracefully if
the binary is missing or misconfigured.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import os
import json
import httpx

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
from .kai_security_guardrails import set_tool_tier, ToolRiskTier


@dataclass
class ValidateCommandSpec:
    binary: str
    args: List[str]
    workdir: Optional[Path] = None
    timeout: int = 300


class ValidatorCLITool(BaseTool):
    """Minimal CLI runner with timeouts and stderr capture."""

    binary_name: str = ""

    def _run(self, spec: ValidateCommandSpec) -> tuple[bool, str, str]:
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
        except FileNotFoundError:
            return False, "", f"binary '{spec.binary}' not found in PATH"
        except Exception as e:  # pragma: no cover - defensive
            return False, "", str(e)


def _register(tool: BaseTool):
    reg = get_registry()
    if reg.get(tool.id):
        return
    register_tool(tool)
    # map risk tier (validation is intrusive by design)
    set_tool_tier(tool.id, ToolRiskTier.TIER_2_INTRUSIVE)


# ---------------------------------------------------------------------------
# Validation adapters
# ---------------------------------------------------------------------------


class SQLMapValidate(ValidatorCLITool):
    binary_name = "sqlmap"

    def __init__(self):
        super().__init__(
            id="sqlmap_validate",
            name="SQLMap Validator",
            description="Validate SQL injection on a URL/param using safe defaults (--batch).",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("url", "string", "Target URL with injectable param"),
                ToolParameter("risk", "number", "Risk level (1-3)", required=False, default=1, min_value=1, max_value=3),
                ToolParameter("level", "number", "Test level (1-5)", required=False, default=1, min_value=1, max_value=5),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        url = kwargs["url"]
        risk = int(kwargs.get("risk", 1))
        level = int(kwargs.get("level", 1))
        args = ["-u", url, "--batch", "--risk", str(risk), "--level", str(level), "--random-agent"]
        start = time.time()
        success, stdout, stderr = self._run(ValidateCommandSpec(self.binary_name, args, timeout=420))
        elapsed = (time.time() - start) * 1000
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(
            self.id,
            status,
            {"url": url, "raw": stdout},
            error=None if success else stderr,
            execution_time_ms=elapsed,
            metadata={"repro_command": f"sqlmap {' '.join(args)}"},
        )


class CommixValidate(ValidatorCLITool):
    binary_name = "commix"

    def __init__(self):
        super().__init__(
            id="commix_validate",
            name="Commix Validator",
            description="Validate OS command injection in URL-based targets.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[ToolParameter("url", "string", "Target URL with injectable param")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        url = kwargs["url"]
        args = ["--batch", "--url", url, "--random-agent"]
        start = time.time()
        success, stdout, stderr = self._run(ValidateCommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(
            self.id,
            status,
            {"url": url, "raw": stdout},
            error=None if success else stderr,
            execution_time_ms=elapsed,
            metadata={"repro_command": f"commix {' '.join(args)}"},
        )


class XSStrikeValidate(ValidatorCLITool):
    binary_name = "xsstrike"

    def __init__(self):
        super().__init__(
            id="xsstrike_validate",
            name="XSStrike Validator",
            description="Validate and discover XSS vectors using XSStrike.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[ToolParameter("url", "string", "Target URL with params")],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        url = kwargs["url"]
        args = ["-u", url, "--crawl", "--fuzzer"]
        start = time.time()
        success, stdout, stderr = self._run(ValidateCommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(
            self.id,
            status,
            {"url": url, "raw": stdout},
            error=None if success else stderr,
            execution_time_ms=elapsed,
            metadata={"repro_command": f"xsstrike {' '.join(args)}"},
        )


class ArjunParams(ValidatorCLITool):
    binary_name = "arjun"

    def __init__(self):
        super().__init__(
            id="arjun_params",
            name="Arjun Param Finder",
            description="Discover hidden HTTP parameters using Arjun.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("url", "string", "Target URL"),
                ToolParameter("method", "string", "HTTP method", required=False, default="GET", enum=["GET", "POST"]),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        url = kwargs["url"]
        method = kwargs.get("method", "GET")
        args = ["-u", url, "-m", method, "--stable"]
        start = time.time()
        success, stdout, stderr = self._run(ValidateCommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(
            self.id,
            status,
            {"url": url, "raw": stdout},
            error=None if success else stderr,
            execution_time_ms=elapsed,
            metadata={"repro_command": f"arjun {' '.join(args)}"},
        )


class MetasploitRPCValidate(BaseTool):
    """Metasploit RPC-driven validation (best-effort JSON-RPC)."""

    def __init__(self):
        super().__init__(
            id="metasploit_rpc_validate",
            name="Metasploit RPC Validator",
            description="Run Metasploit modules via RPC (requires MSF_RPC_URL and creds).",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("module", "string", "Metasploit module path (e.g., auxiliary/scanner/http/dir_scanner)"),
                ToolParameter("rhost", "string", "Target host"),
                ToolParameter("options", "object", "Module options", required=False, default={}),
            ],
            version="0.0.1",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        rpc_url = os.getenv("MSF_RPC_URL")
        rpc_user = os.getenv("MSF_RPC_USER")
        rpc_pass = os.getenv("MSF_RPC_PASS")
        if not all([rpc_url, rpc_user, rpc_pass]):
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="MSF_RPC_URL/USER/PASS not set")

        module = kwargs["module"]
        rhost = kwargs["rhost"]
        options = kwargs.get("options", {})

        def _rpc(method: str, params: dict) -> httpx.Response:
            return httpx.post(rpc_url, json={"method": method, "params": params}, timeout=30)

        try:
            auth = _rpc("auth.login", {"username": rpc_user, "password": rpc_pass})
            if auth.status_code != 200 or auth.json().get("error"):
                return ToolResult(self.id, ToolStatus.FAILED, {}, error=f"MSF auth failed: {auth.text}")
            token = auth.json().get("result", {}).get("token")
            if not token:
                return ToolResult(self.id, ToolStatus.FAILED, {}, error="MSF token missing")

            mod_resp = _rpc("module.execute", {"token": token, "module_type": module.split("/")[0], "module_name": "/".join(module.split("/")[1:]), "options": {"RHOSTS": rhost, **options}})
            if mod_resp.status_code != 200:
                return ToolResult(self.id, ToolStatus.FAILED, {}, error=f"MSF exec HTTP {mod_resp.status_code}")
            data = mod_resp.json()
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED,
                {"module": module, "rhost": rhost, "raw": data},
                execution_time_ms=0,
                metadata={"repro_command": f"msfrpc {module} RHOSTS={rhost}"},
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class CalderaEmulation(BaseTool):
    """MITRE Caldera / Atomic Red Team emulation runner (minimal HTTP client)."""

    def __init__(self):
        super().__init__(
            id="caldera_emulation",
            name="Caldera Emulation",
            description="Run a Caldera/Atomic profile for validation (requires CALDERA_API_URL/TOKEN).",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("profile", "string", "Caldera profile/op ID"),
                ToolParameter("target", "string", "Target host/group"),
            ],
            version="0.0.1",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        api_url = os.getenv("CALDERA_API_URL")
        api_key = os.getenv("CALDERA_API_KEY")
        if not api_url or not api_key:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="CALDERA_API_URL/API_KEY not set")

        profile = kwargs["profile"]
        target = kwargs["target"]
        headers = {"KEY": api_key, "Content-Type": "application/json"}
        payload = {"name": f"kai-{profile}", "adversary_id": profile, "host_group": [target]}
        try:
            resp = httpx.post(f"{api_url.rstrip('/')}/api/v2/operations", headers=headers, json=payload, timeout=30)
            if resp.status_code not in (200, 201):
                return ToolResult(self.id, ToolStatus.FAILED, {"raw": resp.text}, error=f"Caldera HTTP {resp.status_code}")
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED,
                {"profile": profile, "target": target, "raw": resp.json()},
                metadata={"repro_command": f"POST {api_url}/api/v2/operations profile={profile} target={target}"},
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class PacuCloudValidate(BaseTool):
    """AWS adversary simulation via Pacu (CLI invocation)."""

    def __init__(self):
        super().__init__(
            id="pacu_validate",
            name="Pacu Cloud Validator",
            description="Run Pacu modules against AWS creds/session for cloud validation.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("module", "string", "Pacu module name"),
                ToolParameter("profile", "string", "AWS profile/creds ref"),
            ],
            version="0.0.1",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        module = kwargs["module"]
        profile = kwargs["profile"]

        # pacu --non-interactive --profile <profile> --module <module> --run
        args = ["pacu", "--non-interactive", "--profile", profile, "--module", module, "--run"]
        start = time.time()
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=600)
            elapsed = (time.time() - start) * 1000
            ok = result.returncode == 0
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED if ok else ToolStatus.FAILED,
                {"module": module, "profile": profile, "stdout": result.stdout},
                error=None if ok else result.stderr,
                execution_time_ms=elapsed,
                metadata={"repro_command": " ".join(args)},
            )
        except FileNotFoundError:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="pacu CLI not found in PATH")
        except subprocess.TimeoutExpired:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="pacu run timed out after 600s")
        except Exception as e:  # pragma: no cover
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class BloodHoundCollector(BaseTool):
    """Active Directory graph collection (placeholder)."""

    def __init__(self):
        super().__init__(
            id="bloodhound_collect",
            name="BloodHound Collector",
            description="Collect AD data using SharpHound/BloodHound (requires domain creds).",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("domain", "string", "AD domain"),
                ToolParameter("username", "string", "Domain user"),
            ],
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
            error="BloodHound collection not configured; supply collector path/creds",
        )


class EvilWinRMValidate(BaseTool):
    """Evil-WinRM validation helper (placeholder)."""

    def __init__(self):
        super().__init__(
            id="evilwinrm_validate",
            name="Evil-WinRM Validator",
            description="Validate WinRM access with provided creds/key.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("target", "string", "Target host"),
                ToolParameter("username", "string", "Username"),
                ToolParameter("password", "string", "Password", required=False),
                ToolParameter("key_path", "string", "Key path", required=False),
            ],
            version="0.0.1",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        return ToolResult(
            self.id,
            ToolStatus.FAILED,
            {"target": kwargs.get("target")},
            error="Evil-WinRM not configured; install binary and pass credentials",
        )


class ResponderListener(BaseTool):
    """Responder listener setup (placeholder)."""

    def __init__(self):
        super().__init__(
            id="responder_listener",
            name="Responder Listener",
            description="Start Responder for LLMNR/NBNS/MDNS capture (intrusive; gated).",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[ToolParameter("iface", "string", "Interface", required=False, default="eth0")],
            version="0.0.1",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        return ToolResult(
            self.id,
            ToolStatus.FAILED,
            {"iface": kwargs.get("iface", "eth0")},
            error="Responder not started in sandbox; requires privileged network context",
        )


# ---------------------------------------------------------------------------
# Registration entrypoint
# ---------------------------------------------------------------------------


def register_phase3_validation_tools():
    tools = [
        SQLMapValidate(),
        CommixValidate(),
        XSStrikeValidate(),
        ArjunParams(),
        MetasploitRPCValidate(),
        CalderaEmulation(),
        PacuCloudValidate(),
        BloodHoundCollector(),
        EvilWinRMValidate(),
        ResponderListener(),
    ]
    for tool in tools:
        _register(tool)
