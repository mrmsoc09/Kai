"""
Layer 2: Vulnerability scanning / SAST / SCA adapters.

These adapters wrap common security scanners with conservative defaults.
They are intended to be orchestrated via Celery and guarded by risk tiers.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .evidence_objects import create_evidence_object
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
class ScanCommandSpec:
    binary: str
    args: List[str]
    workdir: Optional[Path] = None
    timeout: int = 300


class ScannerCLITool(BaseTool):
    """Minimal CLI runner for scanners."""

    binary_name: str = ""

    def _run(self, spec: ScanCommandSpec) -> tuple[bool, str, str]:
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
    # Map tier
    if tool.autonomy_tier == ToolAutonomyTier.TIER_0_AUTO:
        set_tool_tier(tool.id, ToolRiskTier.TIER_0_SAFE)
    elif tool.autonomy_tier == ToolAutonomyTier.TIER_1_NOTIFY:
        set_tool_tier(tool.id, ToolRiskTier.TIER_1_NOTIFY)
    else:
        set_tool_tier(tool.id, ToolRiskTier.TIER_2_INTRUSIVE)


# ---------------------------------------------------------------------------
# Scanner adapters
# ---------------------------------------------------------------------------


class SemgrepTool(ScannerCLITool):
    binary_name = "semgrep"

    def __init__(self):
        super().__init__(
            id="semgrep_scan",
            name="Semgrep",
            description="Run Semgrep on a code directory with default rules.",
            category=ToolCategory.SCANNER,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("path", "string", "Path to project root"),
                ToolParameter("config", "string", "Semgrep config (e.g., p/owasp-top-ten)", required=False, default="p/owasp-top-ten"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        path = Path(kwargs["path"]).expanduser()
        config = kwargs.get("config", "p/owasp-top-ten")
        args = ["--config", config, "--json", str(path)]
        start = time.time()
        success, stdout, stderr = self._run(ScanCommandSpec(self.binary_name, args, timeout=420))
        elapsed = (time.time() - start) * 1000
        output = {"path": str(path), "config": config, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class GitleaksTool(ScannerCLITool):
    binary_name = "gitleaks"

    def __init__(self):
        super().__init__(
            id="gitleaks_scan",
            name="Gitleaks",
            description="Scan a repo for secrets with gitleaks.",
            category=ToolCategory.SCANNER,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("path", "string", "Path to repo"),
                ToolParameter("report", "string", "Report path", required=False, default="gitleaks-report.json"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        path = Path(kwargs["path"]).expanduser()
        report = kwargs.get("report", "gitleaks-report.json")
        args = ["detect", "--no-banner", "--report-format", "json", "--report-path", report, "-s", str(path)]
        start = time.time()
        success, stdout, stderr = self._run(ScanCommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        output = {"path": str(path), "report": report, "stdout": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class TrivyTool(ScannerCLITool):
    binary_name = "trivy"

    def __init__(self):
        super().__init__(
            id="trivy_scan",
            name="Trivy",
            description="Vulnerability scan for filesystem/image/repo using Trivy.",
            category=ToolCategory.SCANNER,
            autonomy_tier=ToolAutonomyTier.TIER_1_NOTIFY,
            parameters=[
                ToolParameter("target", "string", "Path, image, or repo to scan"),
                ToolParameter("mode", "string", "fs|image|repo", required=False, default="fs", enum=["fs", "image", "repo"]),
                ToolParameter("severity", "string", "Severity filter", required=False, default="HIGH,CRITICAL"),
                ToolParameter("run_id", "string", "Execution run ID", required=False, default=None),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = kwargs["target"]
        mode = kwargs.get("mode", "fs")
        severity = kwargs.get("severity", "HIGH,CRITICAL")
        run_id = kwargs.get("run_id")
        base_args = ["--severity", severity, "--quiet"]
        if mode == "image":
            args = ["image", *base_args, target]
        elif mode == "repo":
            args = ["repo", *base_args, target]
        else:
            args = ["fs", *base_args, target]
        start = time.time()
        success, stdout, stderr = self._run(ScanCommandSpec(self.binary_name, args, timeout=420))
        elapsed = (time.time() - start) * 1000
        evidence = create_evidence_object(
            tool=self.id,
            target=target,
            run_id=run_id,
            evidence_type="sca",
            structured_data={"target": target, "mode": mode, "severity": severity},
            raw_payload={"stdout": stdout, "stderr": stderr},
            confidence_score=0.8 if success else 0.2,
            scope_status="validated",
            description="trivy scan results",
        )
        output = {"target": target, "mode": mode, "raw": stdout, "evidence": evidence}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


class SyftSBOMTool(ScannerCLITool):
    binary_name = "syft"

    def __init__(self):
        super().__init__(
            id="syft_sbom",
            name="Syft SBOM",
            description="Generate SBOM for a filesystem or image using syft (JSON output).",
            category=ToolCategory.SCANNER,
            autonomy_tier=ToolAutonomyTier.TIER_0_AUTO,
            parameters=[
                ToolParameter("target", "string", "Path or image"),
                ToolParameter("output", "string", "Output format", required=False, default="json"),
            ],
            version="0.1.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        ok, err = self.validate_parameters(**kwargs)
        if not ok:
            return ToolResult(self.id, ToolStatus.FAILED, {}, error=err)
        target = kwargs["target"]
        output_fmt = kwargs.get("output", "json")
        args = [target, "-o", output_fmt]
        start = time.time()
        success, stdout, stderr = self._run(ScanCommandSpec(self.binary_name, args, timeout=300))
        elapsed = (time.time() - start) * 1000
        output = {"target": target, "format": output_fmt, "raw": stdout}
        status = ToolStatus.COMPLETED if success else ToolStatus.FAILED
        return ToolResult(self.id, status, output, error=None if success else stderr, execution_time_ms=elapsed)


# ---------------------------------------------------------------------------
# Registration entrypoint
# ---------------------------------------------------------------------------


def register_phase2_scanner_tools():
    tools = [
        SemgrepTool(),
        GitleaksTool(),
        TrivyTool(),
        SyftSBOMTool(),
    ]
    for tool in tools:
        _register(tool)
