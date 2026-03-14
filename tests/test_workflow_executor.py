from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from apps.backend.src.core.workflow_executor import WorkflowExecutor
from apps.backend.src.core.scope_guardrails import ScopePolicy
from apps.backend.src.core.tools import BaseTool, ToolAutonomyTier, ToolCategory, ToolParameter, ToolResult, ToolStatus
from apps.backend.src.models.campaign import CampaignRun, ExecutionBranch, ScopeTarget, ToolExecution
from apps.backend.src.models.enums import BranchStatusEnum, CampaignStatusEnum, WorkflowRunStatusEnum
from apps.backend.src.models.workflow import CorrelationRecord, StageRun, WorkflowFinding, WorkflowRun


class _FakeTool(BaseTool):
    def __init__(self, tool_id: str, output: dict, *, param_names: list[str] | None = None):
        param_names = param_names or ["target", "run_id", "signals"]
        params: list[ToolParameter] = []
        if "target" in param_names:
            params.append(ToolParameter("target", "string", "target"))
        if "domain" in param_names:
            params.append(ToolParameter("domain", "string", "domain"))
        if "host" in param_names:
            params.append(ToolParameter("host", "string", "host"))
        if "url" in param_names:
            params.append(ToolParameter("url", "string", "url"))
        if "run_id" in param_names:
            params.append(ToolParameter("run_id", "string", "run id", required=False, default=None))
        if "signals" in param_names:
            params.append(ToolParameter("signals", "array", "signals", required=False, default=[]))
        super().__init__(
            id=tool_id,
            name=tool_id,
            description="fake tool",
            category=ToolCategory.OSINT,
            autonomy_tier=ToolAutonomyTier.TIER_0_AUTO,
            parameters=params,
        )
        self._output = output

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(
            tool_id=self.id,
            status=ToolStatus.COMPLETED,
            output=self._output,
            metadata={"exit_code": 0},
        )


class _FakeRegistry:
    def __init__(self):
        self.tools = {
            "subfinder": _FakeTool(
                "subfinder",
                {"subdomains": ["api.example.com"]},
                param_names=["domain", "run_id"],
            ),
            "assetfinder": _FakeTool("assetfinder", {"subdomains": ["app.example.com"]}),
            "amass": _FakeTool(
                "amass",
                {"subdomains": ["dev.example.com"]},
                param_names=["domain", "run_id"],
            ),
            "gau": _FakeTool("gau", {"urls": ["https://api.example.com/v1/users?id=1"]}),
            "waybackurls": _FakeTool("waybackurls", {"urls": ["https://api.example.com/legacy?q=2"]}),
            "dnsx": _FakeTool("dnsx", {"records": [{"host": "api.example.com", "a": "1.2.3.4"}]}),
            "httpx_probe": _FakeTool(
                "httpx_probe",
                {
                    "records": [
                        {
                            "host": "api.example.com",
                            "url": "https://api.example.com",
                            "port": 443,
                            "tech": ["nginx", "python"],
                            "title": "API",
                        }
                    ]
                },
            ),
            "naabu": _FakeTool("naabu", {"records": [{"host": "api.example.com", "port": 443, "service": "https"}]}),
            "tlsx": _FakeTool("tlsx", {"records": [{"host": "api.example.com", "service": "tls"}]}),
            "k1_correlation": _FakeTool("k1_correlation", {"parsed": {"items": []}}),
            "k1_priority_ranking": _FakeTool("k1_priority_ranking", {"parsed": {"items": []}}),
        }

    def get(self, tool_id: str):
        return self.tools.get(tool_id)


class _FakeDB:
    def __init__(self):
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        now = datetime.now(timezone.utc)
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            setattr(obj, "id", uuid4())
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            setattr(obj, "created_at", now)
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            setattr(obj, "updated_at", now)
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("Unexpected SQL execution in workflow executor unit test")


@pytest.mark.asyncio
async def test_workflow_executor_runs_recon_surface_map(monkeypatch, tmp_path: Path):
    from apps.backend.src.core import workflow_executor as mod

    fake_registry = _FakeRegistry()
    monkeypatch.setattr(mod, "initialize_default_tools", lambda: None)
    monkeypatch.setattr(mod, "get_registry", lambda: fake_registry)
    monkeypatch.setattr(
        mod,
        "load_scope_policy",
        lambda _path=None: ScopePolicy(allowlist=["example.com"], strict_allowlist=True),
    )

    executor = WorkflowExecutor(output_root=str(tmp_path / "output"))
    result = await executor.execute_template(
        workflow_template="workflow_recon_surface_map",
        target="example.com",
        safe_mode=True,
    )
    assert result.status in {"COMPLETED", "COMPLETED_WITH_FAILURES"}
    assert result.stage_results
    assert result.prioritized_findings
    assert (tmp_path / "output" / "workflows" / result.run_id / "manifest.json").exists()
    assert (tmp_path / "output" / "reports" / result.run_id / "report.md").exists()
    assert (tmp_path / "output" / "normalized" / result.run_id / "url_records.jsonl").exists()


@pytest.mark.asyncio
async def test_workflow_executor_resume(monkeypatch, tmp_path: Path):
    from apps.backend.src.core import workflow_executor as mod

    fake_registry = _FakeRegistry()
    monkeypatch.setattr(mod, "initialize_default_tools", lambda: None)
    monkeypatch.setattr(mod, "get_registry", lambda: fake_registry)
    monkeypatch.setattr(
        mod,
        "load_scope_policy",
        lambda _path=None: ScopePolicy(allowlist=["example.com"], strict_allowlist=True),
    )

    executor = WorkflowExecutor(output_root=str(tmp_path / "output"))
    first = await executor.execute_template(
        workflow_template="workflow_recon_surface_map",
        target="example.com",
        run_id="wf-resume",
        safe_mode=True,
    )
    second = await executor.execute_template(
        workflow_template="workflow_recon_surface_map",
        target="example.com",
        run_id="wf-resume",
        safe_mode=True,
        resume=True,
    )
    assert first.run_id == second.run_id == "wf-resume"
    assert second.stage_results


@pytest.mark.asyncio
async def test_workflow_executor_persists_canonical_records(monkeypatch, tmp_path: Path):
    from apps.backend.src.core import workflow_executor as mod

    class _FailTool(_FakeTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.FAILED,
                output={"parsed": {"items": []}},
                error="simulated failure",
                metadata={"exit_code": 2},
            )

    fake_registry = _FakeRegistry()
    fake_registry.tools.update(
        {
            "httpx": _FakeTool(
                "httpx",
                {
                    "records": [
                        {
                            "host": "api.example.com",
                            "url": "https://api.example.com",
                            "port": 443,
                            "tech": ["nginx"],
                        }
                    ]
                },
            ),
            "nuclei_scan": _FakeTool(
                "nuclei_scan",
                {
                    "findings": [
                        {
                            "name": "SQL Injection Candidate",
                            "severity": "high",
                            "matched-at": "https://api.example.com/v1/users?id=1",
                        }
                    ]
                },
            ),
            "nikto": _FailTool("nikto", {"parsed": {"items": []}}),
            "dalfox": _FakeTool("dalfox", {"parsed": {"items": []}}),
        }
    )

    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        campaign_name="workflow_quick_vuln_sweep:wf-db",
        initiated_by="workflow.executor",
        declared_goal="Execute workflow workflow_quick_vuln_sweep on target example.com",
        status=CampaignStatusEnum.RUNNING,
    )
    scope = ScopeTarget(
        id=uuid4(),
        program_id=campaign.program_id,
        target="example.com",
        target_type="domain",
        is_in_scope=True,
    )
    branch = ExecutionBranch(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_key="wf-wf-db",
        status=BranchStatusEnum.RUNNING,
    )

    async def _fake_context(**_kwargs):
        return campaign, scope, branch

    monkeypatch.setattr(mod, "initialize_default_tools", lambda: None)
    monkeypatch.setattr(mod, "get_registry", lambda: fake_registry)
    monkeypatch.setattr(
        mod,
        "load_scope_policy",
        lambda _path=None: ScopePolicy(allowlist=["example.com"], strict_allowlist=True),
    )

    db = _FakeDB()
    executor = WorkflowExecutor(output_root=str(tmp_path / "output"), db=db, trigger_source="CLI")
    monkeypatch.setattr(executor, "_ensure_local_campaign_context", _fake_context)

    result = await executor.execute_template(
        workflow_template="workflow_quick_vuln_sweep",
        target="example.com",
        run_id="wf-db",
        safe_mode=False,
    )

    assert result.status == "COMPLETED_WITH_FAILURES"
    workflow_runs = [item for item in db.added if isinstance(item, WorkflowRun)]
    stage_runs = [item for item in db.added if isinstance(item, StageRun)]
    tool_executions = [item for item in db.added if isinstance(item, ToolExecution)]
    findings = [item for item in db.added if isinstance(item, WorkflowFinding)]
    correlations = [item for item in db.added if isinstance(item, CorrelationRecord)]

    assert workflow_runs
    assert stage_runs
    assert tool_executions
    assert findings
    assert correlations
    assert any(exec_row.artifact_path for exec_row in tool_executions)
    assert all(find_row.evidence_artifact_path for find_row in findings)
    assert workflow_runs[-1].status == WorkflowRunStatusEnum.FAILED
