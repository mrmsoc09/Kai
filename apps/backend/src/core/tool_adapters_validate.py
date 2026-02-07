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


# ---------------------------------------------------------------------------
# Registration entrypoint
# ---------------------------------------------------------------------------


def register_phase3_validation_tools():
    tools = [
        SQLMapValidate(),
        CommixValidate(),
        XSStrikeValidate(),
        ArjunParams(),
    ]
    for tool in tools:
        _register(tool)

