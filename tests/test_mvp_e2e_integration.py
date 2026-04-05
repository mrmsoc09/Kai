from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

import apps.backend.src.core.bug_bounty_hunting_service as hunting_module
import apps.backend.src.core.workflow_executor as workflow_executor_module
from apps.backend.src.core.hil_db import dispose_async_engine, get_async_engine, get_async_session_maker
from apps.backend.src.core.workflow_executor import WorkflowExecutionResult
from apps.backend.src.core.workflow_run_service import WorkflowRunService
from apps.backend.src.models import Base
from apps.backend.src.models.bug_bounty import AnalystCaseRecord, AnalystQueueItem, NotificationAlertRecord
from apps.backend.src.models.campaign import CampaignRun, SubmissionDraft
from apps.backend.src.models.enums import CampaignStatusEnum, WorkflowRunStatusEnum
from apps.backend.src.models.workflow import WorkflowRun


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def isolated_mvp_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    output_root = tmp_path / "output"
    artifacts_root = tmp_path / "artifacts"
    output_root.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    existing_db_url = (os.getenv("DATABASE_URL") or "").strip()
    db_path = tmp_path / "mvp_e2e.sqlite3"
    if not existing_db_url:
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("K1_WORKFLOW_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(artifacts_root))

    _run(dispose_async_engine())

    async def _init_schema() -> None:
        engine = get_async_engine()
        if not existing_db_url:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    try:
        _run(_init_schema())
    except RuntimeError as exc:
        if "Database driver module missing" in str(exc):
            pytest.fail(
                f"MVP E2E integration test requires an async DB driver but none is installed.\n"
                f"Run: pip install 'aiosqlite>=0.20,<1.0'  (or set DATABASE_URL to a live asyncpg PostgreSQL URL)\n"
                f"Original error: {exc}"
            )
        raise
    yield {"db_path": db_path, "output_root": output_root}
    _run(dispose_async_engine())


def test_mvp_api_e2e_chain(client, monkeypatch: pytest.MonkeyPatch, isolated_mvp_environment):
    def _healthy_dashboard(
        *,
        tool_names=None,
        enabled_only=False,
        run_smoke_tests=False,
        telemetry_window=10,
        install_timeout=4,
        use_cached_install_report=True,
    ):
        _ = enabled_only, run_smoke_tests, telemetry_window, install_timeout, use_cached_install_report
        names = list(tool_names or [])
        return {
            "tools": [{"tool_name": name, "overall_health": "healthy"} for name in names],
            "summary": {"total_tools": len(names), "healthy_tools": len(names)},
        }

    monkeypatch.setattr(hunting_module, "build_dashboard", _healthy_dashboard)
    monkeypatch.setattr(
        hunting_module.BugBountyHuntingService,
        "_resolve_required_secrets",
        staticmethod(lambda required_keys: (sorted(set(required_keys or [])), [])),
    )

    async def _fake_execute_template(
        self,
        *,
        workflow_template: str,
        target: str,
        run_id: str | None = None,
        safe_mode: bool = True,
        dry_run: bool = False,
        concurrency_limit: int = 4,
        enable_steps=None,
        disable_steps=None,
        scope_policy_path=None,
        scope_policy_override=None,
        resume: bool = False,
        program_id=None,
        scope_target_id=None,
        campaign_name: str | None = None,
        initiated_by: str | None = None,
    ) -> WorkflowExecutionResult:
        _ = (
            safe_mode,
            dry_run,
            concurrency_limit,
            enable_steps,
            disable_steps,
            scope_policy_path,
            scope_policy_override,
            resume,
        )
        assert self.db is not None
        assert program_id is not None
        assert scope_target_id is not None

        now = datetime.now(timezone.utc)
        run_key = run_id or f"mvp-{uuid4().hex[:8]}"
        workflow_root = Path(os.getenv("K1_WORKFLOW_OUTPUT_ROOT", "output")).resolve()
        raw_dir = workflow_root / "raw" / run_key
        workflows_dir = workflow_root / "workflows" / run_key
        reports_dir = workflow_root / "reports" / run_key
        raw_dir.mkdir(parents=True, exist_ok=True)
        workflows_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        evidence_path = raw_dir / "nuclei.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "tool": "nuclei",
                    "target": target,
                    "severity": "high",
                    "title": "SQL injection candidate",
                }
            ),
            encoding="utf-8",
        )
        manifest_path = workflows_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "run_id": run_key,
                    "workflow_template": workflow_template,
                    "target": target,
                    "status": "completed",
                }
            ),
            encoding="utf-8",
        )
        summary_path = workflows_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": run_key,
                    "status": "COMPLETED",
                    "workflow_template": workflow_template,
                }
            ),
            encoding="utf-8",
        )
        report_path = reports_dir / "report.md"
        report_path.write_text("# MVP workflow report\n", encoding="utf-8")

        campaign = CampaignRun(
            program_id=program_id,
            primary_scope_target_id=scope_target_id,
            campaign_name=campaign_name or f"mvp-e2e:{workflow_template}:{run_key}",
            initiated_by=initiated_by or "tests.mvp_e2e",
            declared_goal="Deterministic MVP integration run",
            declared_reason="Pytest API E2E coverage",
            policy_basis="TEST",
            approval_required=False,
            status=CampaignStatusEnum.COMPLETED,
            run_config_json={"source": "tests.test_mvp_e2e_integration"},
            started_at=now,
            ended_at=now,
        )
        self.db.add(campaign)
        await self.db.flush()

        workflow_service = WorkflowRunService(self.db)
        workflow_run = await workflow_service.create_workflow_run(
            campaign_run_id=campaign.id,
            scope_target_id=scope_target_id,
            template_name=workflow_template,
            target=target,
            safe_mode=True,
            dry_run=False,
            trigger_source="TEST",
            total_phases=1,
            artifact_manifest_path=str(manifest_path),
        )
        await workflow_service.transition_workflow_run(
            workflow_run,
            WorkflowRunStatusEnum.COMPLETED,
            artifact_manifest_path=str(manifest_path),
            summary_artifact_path=str(summary_path),
        )
        await workflow_service.create_workflow_finding(
            workflow_run_id=workflow_run.id,
            campaign_id=campaign.id,
            stage_run_id=None,
            tool_execution_id=None,
            asset_identifier=target,
            endpoint="/api/v1/users",
            parameter="id",
            vulnerability_type="sql_injection_candidate",
            confidence_score=0.97,
            severity_hint="high",
            evidence_artifact_path=str(evidence_path),
            details_json={"title": "SQL injection candidate", "source": "pytest"},
        )

        return WorkflowExecutionResult(
            run_id=run_key,
            workflow_template=workflow_template,
            status="COMPLETED",
            target=target,
            manifest_path=str(manifest_path),
            summary_path=str(summary_path),
            report_path=str(report_path),
            stage_results=[{"stage": "vuln_scan", "status": "COMPLETED"}],
            prioritized_findings=[{"host": target, "priority_score": 0.94}],
            metrics={"executed_tools": 1},
            campaign_id=str(campaign.id),
            workflow_run_id=str(workflow_run.id),
        )

    monkeypatch.setattr(workflow_executor_module.WorkflowExecutor, "execute_template", _fake_execute_template)

    login_response = client.post(
        "/auth/login",
        json={"token": os.environ["K1_DEV_TOKEN"]},
    )
    assert login_response.status_code == 200
    access_token = login_response.json().get("access_token")
    assert isinstance(access_token, str) and access_token
    client.headers.update({"Authorization": f"Bearer {access_token}"})

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    roles = set(me_response.json().get("roles", []))
    assert {"operator", "analyst", "admin"}.issubset(roles)

    program_import = client.post(
        "/api/v1/bug-bounty/programs/import",
        json={
            "source": "manual",
            "platform": "hackerone",
            "name": "MVP Integration Program",
            "program_key": f"mvp-integration-{uuid4().hex[:8]}",
            "status": "ACTIVE",
            "require_safe_mode": True,
            "in_scope_assets": [
                {
                    "target": "mvp.example.com",
                    "target_type": "domain",
                    "monitoring_enabled": True,
                    "safe_mode_required": True,
                    "priority_tier": 2,
                }
            ],
            "out_of_scope_assets": [
                {
                    "target": "admin.mvp.example.com",
                    "target_type": "domain",
                    "monitoring_enabled": False,
                    "safe_mode_required": True,
                    "priority_tier": 5,
                }
            ],
        },
    )
    assert program_import.status_code == 200
    program_id = program_import.json()["id"]

    targets_response = client.get(f"/api/v1/bug-bounty/programs/{program_id}/targets")
    assert targets_response.status_code == 200
    targets = targets_response.json()
    assert targets
    in_scope_targets = [target for target in targets if target.get("is_in_scope")]
    assert in_scope_targets
    scope_target_id = in_scope_targets[0]["id"]

    schedule_response = client.post(
        "/api/v1/bug-bounty/schedules",
        json={
            "program_id": program_id,
            "scope_target_id": scope_target_id,
            "workflow_template": "workflow_quick_vuln_sweep",
            "schedule_type": "interval",
            "interval_minutes": 60,
            "safe_mode": True,
            "dry_run": False,
            "priority_tier": 2,
            "created_by": "tests.mvp_e2e",
        },
    )
    assert schedule_response.status_code == 200
    schedule_id = schedule_response.json()["id"]

    trigger_response = client.post(
        f"/api/v1/bug-bounty/schedules/{schedule_id}/trigger",
        json={"actor": "tests.mvp_e2e", "force": False},
    )
    assert trigger_response.status_code == 200
    trigger_payload = trigger_response.json()
    assert trigger_payload["decision_status"] == "READY"
    assert trigger_payload["workflow_run_id"]
    assert trigger_payload["campaign_id"]
    assert trigger_payload["details"]["status"] == "COMPLETED"

    readiness_records = client.get(
        "/api/v1/bug-bounty/readiness-records",
        params={"program_id": program_id, "limit": 50},
    )
    assert readiness_records.status_code == 200
    assert any(item["decision_status"] == "READY" for item in readiness_records.json())

    candidates_response = client.get(
        "/api/v1/bug-bounty/candidates",
        params={"program_id": program_id, "limit": 50},
    )
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert candidates
    queue_item_id = candidates[0]["id"]
    assert candidates[0]["status"] in {"ready_for_report", "needs_manual_validation", "new"}

    sync_alerts_response = client.post(
        "/api/v1/bug-bounty/alerts/sync",
        json={
            "actor": "tests.mvp_e2e",
            "program_id": program_id,
            "cooldown_minutes": 1,
        },
    )
    assert sync_alerts_response.status_code == 200
    # The trigger already ran an automatic sync, so the alert may be "updated" rather than
    # "created" on this second call.  Either way at least one alert must be accounted for.
    sync_payload = sync_alerts_response.json()
    assert sync_payload["created_alerts"] + sync_payload["updated_alerts"] >= 1

    alerts_response = client.get(
        "/api/v1/bug-bounty/alerts",
        params={"program_id": program_id, "limit": 50},
    )
    assert alerts_response.status_code == 200
    alerts = alerts_response.json()
    assert alerts
    alert_id = alerts[0]["id"]

    create_case_response = client.post(
        f"/api/v1/bug-bounty/alerts/{alert_id}/case",
        json={"actor": "tests.mvp_e2e", "owner": "analyst.mvp"},
    )
    assert create_case_response.status_code == 200
    case_id = create_case_response.json()["id"]

    update_case_response = client.patch(
        f"/api/v1/bug-bounty/cases/{case_id}",
        json={
            "actor": "tests.mvp_e2e",
            "status": "triaging",
            "priority": "HIGH",
            "summary": "triage in progress",
        },
    )
    assert update_case_response.status_code == 200
    assert update_case_response.json()["status"] == "triaging"

    draft_response = client.post(
        f"/api/v1/bug-bounty/candidates/{queue_item_id}/report-draft",
        json={"actor": "tests.mvp_e2e", "analyst_notes": "validated in MVP integration test"},
    )
    assert draft_response.status_code == 200
    draft_payload = draft_response.json()
    assert draft_payload["status"] == "ready_for_report"
    assert Path(draft_payload["draft_path"]).exists()

    alert_summary = client.get(
        "/api/v1/bug-bounty/alerts/summary",
        params={"program_id": program_id},
    )
    assert alert_summary.status_code == 200
    assert alert_summary.json()["open_case_count"] >= 1

    workflow_run_id = UUID(trigger_payload["workflow_run_id"])
    program_uuid = UUID(program_id)
    case_uuid = UUID(case_id)
    queue_uuid = UUID(queue_item_id)

    async def _fetch_state() -> dict:
        async with get_async_session_maker()() as session:
            workflow_run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            case_row = await session.scalar(select(AnalystCaseRecord).where(AnalystCaseRecord.id == case_uuid))
            queue_row = await session.scalar(select(AnalystQueueItem).where(AnalystQueueItem.id == queue_uuid))
            alert_rows = list(
                (
                    await session.execute(
                        select(NotificationAlertRecord).where(NotificationAlertRecord.program_id == program_uuid)
                    )
                ).scalars()
            )
            all_drafts = list((await session.execute(select(SubmissionDraft))).scalars())
            draft_rows = [
                item
                for item in all_drafts
                if isinstance(item.details_json, dict)
                and str(item.details_json.get("queue_item_id") or "") == str(queue_item_id)
            ]
            campaign_row = await session.scalar(
                select(CampaignRun).where(CampaignRun.id == workflow_run.campaign_run_id)
            ) if workflow_run else None
            return {
                "workflow_run": workflow_run,
                "campaign": campaign_row,
                "case": case_row,
                "queue_item": queue_row,
                "alert_count": len(alert_rows),
                "draft_count": len(draft_rows),
            }

    state = _run(_fetch_state())
    assert state["workflow_run"] is not None
    assert state["workflow_run"].status == WorkflowRunStatusEnum.COMPLETED
    assert state["campaign"] is not None
    assert state["case"] is not None and state["case"].status == "triaging"
    assert state["queue_item"] is not None
    assert state["alert_count"] >= 1
    assert state["draft_count"] >= 1


def test_osint_crew_dispatches_tool_agents():
    """
    OSINTIntelligenceAgent.execute() should
    attempt to load and run its tool agents.
    With tools not installed, it should return
    partial results with errors listed —
    not raise an exception.
    """
    from apps.backend.src.agents.crew.osint_intelligence_agent import (
        OSINTIntelligenceAgent,
    )

    agent = OSINTIntelligenceAgent()
    mission_context = {
        "scan_id": "test-scan-001",
        "mission_id": "test-mission-001",
        "target": "example.com",
        "artifact_dir": "/tmp/test_artifacts",
        "rate_limit": 5,
        "timeout": 30,
    }
    result = _run(agent.execute(mission_context, {}))
    # Should return dict, not raise
    assert isinstance(result, dict)
    assert "osint_complete" in result
    # May have errors if tools not installed
    # but should never raise
    assert "errors" in result
    assert "tools_executed" in result


def test_vulnerability_crew_dispatches_tools():
    from apps.backend.src.agents.crew.vulnerability_agent import (
        VulnerabilityAgent,
    )

    agent = VulnerabilityAgent()
    mission_context = {
        "scan_id": "test-scan-001",
        "mission_id": "test-mission-001",
        "target": "https://example.com",
        "artifact_dir": "/tmp/test_artifacts",
        "rate_limit": 5,
        "timeout": 30,
    }
    result = _run(agent.execute(mission_context, {}))
    assert isinstance(result, dict)
    assert "vulnerability_scan_complete" in result
    assert "errors" in result


def test_dark_web_crew_handles_no_tor():
    from apps.backend.src.agents.crew.dark_web_intel_agent import (
        DarkWebIntelAgent,
    )

    agent = DarkWebIntelAgent()
    # Tor almost certainly not running in test env
    mission_context = {
        "scan_id": "test-scan-001",
        "mission_id": "test-mission-001",
        "target": "example.com",
        "artifact_dir": "/tmp/test_artifacts",
        "timeout": 10,
    }
    result = _run(agent.execute(mission_context, {}))
    # Must not raise even without Tor
    assert isinstance(result, dict)
    assert "dark_web_complete" in result


def test_api_crew_skips_graphql_when_not_found():
    from apps.backend.src.agents.crew.api_security_agent import (
        APISecurityAgent,
    )

    agent = APISecurityAgent()
    mission_context = {
        "scan_id": "test-scan-001",
        "mission_id": "test-mission-001",
        "target": "https://example.com",
        "artifact_dir": "/tmp/test_artifacts",
        "timeout": 30,
    }
    # No graphql_endpoints in prior_findings
    result = _run(agent.execute(mission_context, {}))
    assert isinstance(result, dict)
    # graphql-cop and clairvoyance should be skipped
    executed = result.get("tools_executed", [])
    assert "graphql-cop" not in executed
    assert "clairvoyance" not in executed


def test_faraday_coordinator_aggregates():
    from apps.backend.src.agents.crew.faraday_coordinator_agent import (
        FaradayCoordinatorAgent,
    )

    agent = FaradayCoordinatorAgent()
    mission_context = {
        "scan_id": "test-scan-001",
        "mission_id": "test-mission-001",
        "target": "example.com",
        "artifact_dir": "/tmp/test_artifacts",
        "timeout": 30,
    }
    # Empty prior findings — should handle gracefully
    result = _run(agent.execute(mission_context, {}))
    assert isinstance(result, dict)
    assert "aggregation_complete" in result


def test_load_tool_agent_returns_none_for_missing():
    from apps.backend.src.agents.crew.osint_intelligence_agent import (
        OSINTIntelligenceAgent,
    )

    agent = OSINTIntelligenceAgent()
    result = agent._load_tool_agent("nonexistent-tool-xyz")
    assert result is None


def test_load_tool_agent_loads_existing_tool():
    from apps.backend.src.agents.crew.osint_intelligence_agent import (
        OSINTIntelligenceAgent,
    )

    agent = OSINTIntelligenceAgent()
    # Try to load a tool that should exist
    result = agent._load_tool_agent("spiderfoot")
    # Should load successfully
    assert result is not None
