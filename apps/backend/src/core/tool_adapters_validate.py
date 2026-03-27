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
import ipaddress
import re
import shutil
import httpx
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError, field_validator

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
from .secret_manager import get_secret_manager, SecretManagerError


@dataclass
class ValidateCommandSpec:
    binary: str
    args: List[str]
    workdir: Optional[Path] = None
    timeout: int = 300


SHELL_META_CHARS_RE = re.compile(r"[;&|`$<>]")
HOST_TARGET_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|(?:\d{1,3}\.){3}\d{1,3})"
    r"(?::\d{1,5})?(?:/\d{1,2})?$"
)
SECRETISH_FIELDS = {
    "password",
    "pass",
    "client_secret",
    "token",
    "api_key",
    "key",
}
BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
ALLOW_PRIVATE_TARGETS = os.getenv("K1_ALLOW_PRIVATE_TARGETS", "false").lower() == "true"


def _is_disallowed_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _reject_disallowed_host(host: str) -> None:
    normalized = host.strip().lower().strip(".")
    if normalized in BLOCKED_HOSTNAMES:
        raise ValueError("target host is disallowed")

    try:
        addr = ipaddress.ip_address(normalized)
    except ValueError:
        return

    if not ALLOW_PRIVATE_TARGETS and _is_disallowed_ip(addr):
        raise ValueError("private or local network targets are disallowed")


def _validate_host_or_target(value: str) -> str:
    if not value or not HOST_TARGET_RE.fullmatch(value):
        raise ValueError("must be a valid hostname, IPv4, host:port, or CIDR target")

    if "/" in value:
        # CIDR input must parse as IPv4 network.
        network = ipaddress.ip_network(value, strict=False)
        if not ALLOW_PRIVATE_TARGETS and _is_disallowed_ip(network.network_address):
            raise ValueError("private or local network targets are disallowed")
        return value

    host_port = value
    if ":" in value and value.count(":") == 1:
        host, port_str = value.rsplit(":", 1)
        if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
            raise ValueError("invalid port value")
        host_port = host

    _reject_disallowed_host(host_port)

    try:
        ipaddress.ip_address(host_port)
    except ValueError:
        labels = host_port.split(".")
        if any(not label or len(label) > 63 for label in labels):
            raise ValueError("invalid hostname label")
    return value


class _ToolKwargsValidation(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: HttpUrl | None = None
    target: str | None = None
    rhost: str | None = None

    @field_validator("target", "rhost")
    @classmethod
    def _validate_target_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_host_or_target(value)

    @field_validator("url")
    @classmethod
    def _validate_url_field(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is None:
            return value
        parsed = urlparse(str(value))
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("url must use http or https")
        if not parsed.hostname:
            raise ValueError("url must include a hostname")
        _reject_disallowed_host(parsed.hostname)
        return value


def _reject_shell_meta_for_identifier(value: str, field_name: str) -> None:
    if SHELL_META_CHARS_RE.search(value):
        raise ValueError(f"{field_name} contains forbidden shell metacharacters")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{field_name} contains forbidden newlines")


def _secure_validate_kwargs(kwargs: dict) -> None:
    _ToolKwargsValidation.model_validate(kwargs)
    for key, value in kwargs.items():
        if not isinstance(value, str):
            continue
        lowered = key.lower()
        if "\x00" in value:
            raise ValueError(f"{key} contains forbidden null byte")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} contains forbidden newlines")
        if lowered == "url":
            continue
        if lowered in {"target", "rhost", "host", "hostname"}:
            _reject_shell_meta_for_identifier(value, key)
            _validate_host_or_target(value)
            continue
        if lowered not in SECRETISH_FIELDS:
            _reject_shell_meta_for_identifier(value, key)


class ValidatorCLITool(BaseTool):
    """Minimal CLI runner with timeouts and stderr capture."""

    binary_name: str = ""

    def validate_parameters(self, **kwargs) -> tuple[bool, str | None]:
        ok, err = super().validate_parameters(**kwargs)
        if not ok:
            return ok, err
        try:
            _secure_validate_kwargs(kwargs)
        except (ValidationError, ValueError) as exc:
            return False, f"invalid_parameters: {exc}"
        return True, None

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


class SecureBaseTool(BaseTool):
    """BaseTool with strict kwargs validation before execution."""

    def validate_parameters(self, **kwargs) -> tuple[bool, str | None]:
        ok, err = super().validate_parameters(**kwargs)
        if not ok:
            return ok, err
        try:
            _secure_validate_kwargs(kwargs)
        except (ValidationError, ValueError) as exc:
            return False, f"invalid_parameters: {exc}"
        return True, None


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


class MetasploitRPCValidate(SecureBaseTool):
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
        try:
            rpc_pass = get_secret_manager().get_required("MSF_RPC_PASS")
        except SecretManagerError:
            rpc_pass = None
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


class CalderaEmulation(SecureBaseTool):
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
        try:
            api_key = get_secret_manager().get_required("CALDERA_API_KEY")
        except SecretManagerError:
            api_key = None
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


class PacuCloudValidate(SecureBaseTool):
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


class ScoutSuiteValidate(ValidatorCLITool):
    binary_name = "scout"

    def __init__(self):
        super().__init__(
            id="scoutsuite_validate",
            name="ScoutSuite Cloud Audit",
            description="Run ScoutSuite against a cloud account (AWS/GCP/Azure) using profile/creds.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("provider", "string", "aws|gcp|azure", enum=["aws", "gcp", "azure"]),
                ToolParameter("profile", "string", "Profile or credentials ref"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        provider = kwargs["provider"]
        profile = kwargs["profile"]
        args = ["scout", provider, "--profile", profile, "--no-browser"]
        start = time.time()
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=900)
            elapsed = (time.time() - start) * 1000
            ok2 = proc.returncode == 0
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED if ok2 else ToolStatus.FAILED,
                {"provider": provider, "profile": profile, "stdout": proc.stdout},
                error=None if ok2 else proc.stderr,
                execution_time_ms=elapsed,
                metadata={"repro_command": " ".join(args)},
            )
        except FileNotFoundError:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="scout (ScoutSuite) binary not found in PATH")
        except subprocess.TimeoutExpired:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="ScoutSuite timed out after 900s")
        except Exception as e:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class AzurePwnValidate(ValidatorCLITool):
    binary_name = "azurepwn"

    def __init__(self):
        super().__init__(
            id="azurepwn_validate",
            name="AzurePwn Validator",
            description="Run AzurePwn against an Azure tenant with provided creds.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("tenant", "string", "Tenant ID"),
                ToolParameter("client_id", "string", "Client ID"),
                ToolParameter("client_secret", "string", "Client secret"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        tenant = kwargs["tenant"]
        client_id = kwargs["client_id"]
        client_secret = kwargs["client_secret"]
        args = [self.binary_name, "--tenant", tenant, "--client-id", client_id, "--client-secret", client_secret]
        start = time.time()
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=900)
            elapsed = (time.time() - start) * 1000
            ok2 = proc.returncode == 0
            # Redact client_secret from repro_command — never log credentials.
            safe_repro = f"{self.binary_name} --tenant {tenant} --client-id {client_id} --client-secret <REDACTED>"
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED if ok2 else ToolStatus.FAILED,
                {"tenant": tenant, "stdout": proc.stdout},
                error=None if ok2 else proc.stderr,
                execution_time_ms=elapsed,
                metadata={"repro_command": safe_repro},
            )
        except FileNotFoundError:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="azurepwn not found in PATH")
        except subprocess.TimeoutExpired:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="AzurePwn timed out after 900s")
        except Exception as e:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class PeiratesValidate(ValidatorCLITool):
    binary_name = "peirates"

    def __init__(self):
        super().__init__(
            id="peirates_validate",
            name="Peirates K8s Validator",
            description="Run Peirates for Kubernetes privilege escalation checks.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("kubeconfig", "string", "Path to kubeconfig"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        kubeconfig = Path(kwargs["kubeconfig"]).expanduser()
        if not kubeconfig.exists():
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=f"kubeconfig not found: {kubeconfig}")
        args = [self.binary_name, "--kubeconfig", str(kubeconfig), "--non-interactive"]
        start = time.time()
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=600)
            elapsed = (time.time() - start) * 1000
            ok2 = proc.returncode == 0
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED if ok2 else ToolStatus.FAILED,
                {"kubeconfig": str(kubeconfig), "stdout": proc.stdout},
                error=None if ok2 else proc.stderr,
                execution_time_ms=elapsed,
                metadata={"repro_command": " ".join(args)},
            )
        except FileNotFoundError:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="peirates binary not found")
        except subprocess.TimeoutExpired:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="Peirates run timed out after 600s")
        except Exception as e:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class CMEValidate(ValidatorCLITool):
    binary_name = "crackmapexec"

    def __init__(self):
        super().__init__(
            id="cme_validate",
            name="CrackMapExec Validator",
            description="Validate SMB/WinRM/LDAP access using CME.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("target", "string", "Target host or CIDR"),
                ToolParameter("username", "string", "Username"),
                ToolParameter("password", "string", "Password", required=False),
                ToolParameter("protocol", "string", "smb|winrm|ldap", enum=["smb", "winrm", "ldap"], required=False, default="smb"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = kwargs["target"]
        user = kwargs["username"]
        pw = kwargs.get("password")
        protocol = kwargs.get("protocol", "smb")
        args = [self.binary_name, protocol, target, "-u", user]
        if pw:
            args += ["-p", pw]
        start = time.time()
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=300)
            elapsed = (time.time() - start) * 1000
            ok2 = proc.returncode == 0
            # Redact password from repro_command — never log credentials.
            safe_repro = f"{self.binary_name} {protocol} {target} -u {user}" + (" -p <REDACTED>" if pw else "")
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED if ok2 else ToolStatus.FAILED,
                {"target": target, "protocol": protocol, "stdout": proc.stdout},
                error=None if ok2 else proc.stderr,
                execution_time_ms=elapsed,
                metadata={"repro_command": safe_repro},
            )
        except FileNotFoundError:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="crackmapexec not found")
        except subprocess.TimeoutExpired:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="CME timed out after 300s")
        except Exception as e:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))


class ImpacketValidate(ValidatorCLITool):
    binary_name = "psexec.py"

    def __init__(self):
        super().__init__(
            id="impacket_psexec_validate",
            name="Impacket PsExec Validator",
            description="Validate Windows exec via impacket psexec.",
            category=ToolCategory.VALIDATION,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=[
                ToolParameter("target", "string", "Target host"),
                ToolParameter("username", "string", "Username"),
                ToolParameter("password", "string", "Password"),
                ToolParameter("domain", "string", "Domain", required=False, default=""),
            ],
            version="0.1.0",
        )

    def _which(self):
        # support both psexec.py and impacket-psexec install names
        for name in ["psexec.py", "impacket-psexec"]:
            p = shutil.which(name)
            if p:
                return p
        return None

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        binary = self._which()
        if not binary:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="psexec.py/impacket-psexec not found")
        target = kwargs["target"]
        user = kwargs["username"]
        pw = kwargs["password"]
        domain = kwargs.get("domain", "")
        creds = f"{domain}/{user}:{pw}" if domain else f"{user}:{pw}"
        args = [binary, creds, f"@{target}", "whoami"]
        start = time.time()
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=180)
            elapsed = (time.time() - start) * 1000
            ok2 = proc.returncode == 0
            # Redact password from repro_command — never log credentials.
            safe_creds = f"{domain}/{user}:<REDACTED>" if domain else f"{user}:<REDACTED>"
            safe_repro = f"{binary} {safe_creds} @{target} whoami"
            return ToolResult(
                self.id,
                ToolStatus.COMPLETED if ok2 else ToolStatus.FAILED,
                {"target": target, "stdout": proc.stdout},
                error=None if ok2 else proc.stderr,
                execution_time_ms=elapsed,
                metadata={"repro_command": safe_repro},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error="impacket psexec timed out after 180s")
        except Exception as e:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=str(e))



class BloodHoundCollector(SecureBaseTool):
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


class EvilWinRMValidate(SecureBaseTool):
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


class ResponderListener(SecureBaseTool):
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
        ScoutSuiteValidate(),
        AzurePwnValidate(),
        PeiratesValidate(),
        CMEValidate(),
        ImpacketValidate(),
        BloodHoundCollector(),
        EvilWinRMValidate(),
        ResponderListener(),
    ]
    for tool in tools:
        _register(tool)
