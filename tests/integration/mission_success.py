from __future__ import annotations

import asyncio
import builtins
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import apps.backend.src.core.bug_bounty_hunting_service as hunting_module
import apps.backend.src.core.approval_gate_service as approval_gate_module
import apps.backend.src.core.authorization_gate as authorization_gate_module
import apps.backend.src.core.recon_inference_service as inference_module
import apps.backend.src.core.trilium.exploit_coordinator as exploit_module
import apps.backend.src.core.workflow_executor as workflow_executor_module
import apps.backend.src.worker.campaign_tasks as campaign_tasks
from apps.backend.src.core.bug_bounty_hunting_service import BugBountyHuntingService
from apps.backend.src.core.bugbounty_workflow_engine import WORKFLOW_TEMPLATES
from apps.backend.src.core.praison_langgraph_builder import PraisonLangGraphBuilder
from apps.backend.src.core.praison_mission_runtime import _make_minimal_agent_specs
from apps.backend.src.core.praison_mission_runtime import MissionRuntime
from apps.backend.src.core.praison_topology import PraisonTopology, resolve_execution_order
from apps.backend.src.core.recon_inference_service import ReconInferenceService
from apps.backend.src.core.tool_adapters_bugbounty import catalog_name_to_registry_tool_id
from apps.backend.src.core.tool_registry_catalog import get_catalog_entry, reset_tool_catalog
from apps.backend.src.core.trilium.exploit_coordinator import ExploitCoordinator
from apps.backend.src.core.trilium.query import OrchestrationQueryLayer
from apps.backend.src.core.trilium.sandbox_validator import ExecutionResult
from apps.backend.src.core.trilium.session_manager import SessionManager
from apps.backend.src.models import Base
from apps.backend.src.models.bug_bounty import (
    AdaptiveScheduleActionRecord,
    AnalystCaseRecord,
    AnalystQueueItem,
    DuplicateRiskRecord,
    EvidenceCompletenessRecord,
    HuntReadinessRecord,
    HuntScheduleJob,
    NotificationAlertRecord,
    OpportunityInferenceRecord,
    SignalIntelligenceRecord,
    SwarmReasoningRecord,
    VulnerabilityPredictionRecord,
    WorkflowDeltaRecord,
    WorkflowRecommendationRecord,
)
from apps.backend.src.models.campaign import (
    ApprovalGate,
    AuditEvent,
    CampaignRun,
    ExecutionBranch,
    PhaseJob,
    Program,
    ScopeTarget,
    ToolExecution,
)
from apps.backend.src.models.enums import ToolExecutionStatusEnum, WorkflowRunStatusEnum
from apps.backend.src.models.hil import Finding
from apps.backend.src.models.intention import IntentionRecord
from apps.backend.src.models.workflow import CorrelationRecord, StageRun, WorkflowFinding, WorkflowRun
from apps.backend.src.schemas.bug_bounty_hunt import HuntScheduleCreateRequest, ProgramOpportunityImportRequest


def _run(coro):
    return asyncio.run(coro)


class _AsyncSessionAdapter:
    def __init__(self, sync_session) -> None:  # noqa: ANN001
        self._session = sync_session

    def add(self, instance) -> None:  # noqa: ANN001
        self._session.add(instance)

    async def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return self._session.execute(*args, **kwargs)

    async def scalar(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return self._session.scalar(*args, **kwargs)

    async def flush(self) -> None:
        self._session.flush()

    async def commit(self) -> None:
        self._session.commit()

    async def rollback(self) -> None:
        self._session.rollback()

    async def refresh(self, instance) -> None:  # noqa: ANN001
        self._session.refresh(instance)

    def close(self) -> None:
        self._session.close()


class _AsyncSessionContext:
    def __init__(self, sync_session_factory) -> None:  # noqa: ANN001
        self._sync_session_factory = sync_session_factory
        self._sync_session = None
        self._adapter = None

    async def __aenter__(self) -> _AsyncSessionAdapter:
        self._sync_session = self._sync_session_factory()
        self._adapter = _AsyncSessionAdapter(self._sync_session)
        return self._adapter

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        if self._sync_session is not None:
            if exc is not None:
                self._sync_session.rollback()
            self._sync_session.close()
        return False


class _FakeTriliumClient:
    def __init__(self, free_tier_key: str) -> None:
        self.free_tier_key = free_tier_key
        self.updated_notes: list[tuple[str, str]] = []
        self.created_attributes: list[tuple[str, str, str, str]] = []

    async def search_notes(self, query: str):  # noqa: ANN201
        if "session_target='api-governor'" in query:
            return [{"noteId": "session-note", "title": "Session:api-governor", "type": "text"}]
        if "note.title='Session:api-governor'" in query:
            return [{"noteId": "session-note", "title": "Session:api-governor", "type": "text"}]
        return []

    async def get_note(self, note_id: str):  # noqa: ANN201
        if note_id == "session-note":
            payload = {
                "base_url": "https://mvp.example.com",
                "cookies": {"sid": "stable"},
                "headers": {"X-API-Key": self.free_tier_key},
                "auth_config": {},
            }
            return {
                "title": "Session:api-governor",
                "content": f"<pre><code>{json.dumps(payload)}</code></pre>",
            }
        if note_id == "note-exploit":
            return {"title": "https://mvp.example.com/poc", "content": "<p>PoC target context</p>"}
        return {"title": "unknown", "content": "{}"}

    async def get_attributes(self, note_id: str):  # noqa: ANN201, ARG002
        return []

    async def update_note(self, note_id: str, content: str) -> None:
        self.updated_notes.append((note_id, content))

    async def create_attribute(self, note_id: str, attr_type: str, name: str, value: str):  # noqa: ANN201
        self.created_attributes.append((note_id, attr_type, name, value))
        return {"attributeId": "attr-1"}


class _VaultSecretManager:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.requested_keys: list[str] = []

    def get_optional(self, name: str) -> str | None:
        self.requested_keys.append(name)
        return self.values.get(name)


class _DispatchTaskStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | bool]] = []

    def delay(self, **kwargs):  # noqa: ANN003, ANN201
        self.calls.append(dict(kwargs))
        return SimpleNamespace(id=f"task-{len(self.calls)}")


@pytest.fixture()
def isolated_mission_success_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    output_root = tmp_path / "output"
    artifacts_root = tmp_path / "artifacts"
    output_root.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    db_path = tmp_path / "mission_success.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("K1_WORKFLOW_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(artifacts_root))
    tables = [
        Program.__table__,
        ScopeTarget.__table__,
        CampaignRun.__table__,
        ExecutionBranch.__table__,
        PhaseJob.__table__,
        ApprovalGate.__table__,
        ToolExecution.__table__,
        AuditEvent.__table__,
        IntentionRecord.__table__,
        WorkflowRun.__table__,
        StageRun.__table__,
        WorkflowFinding.__table__,
        CorrelationRecord.__table__,
        HuntScheduleJob.__table__,
        HuntReadinessRecord.__table__,
        WorkflowDeltaRecord.__table__,
        AnalystQueueItem.__table__,
        SignalIntelligenceRecord.__table__,
        OpportunityInferenceRecord.__table__,
        SwarmReasoningRecord.__table__,
        AdaptiveScheduleActionRecord.__table__,
        NotificationAlertRecord.__table__,
        AnalystCaseRecord.__table__,
        DuplicateRiskRecord.__table__,
        EvidenceCompletenessRecord.__table__,
        WorkflowRecommendationRecord.__table__,
        VulnerabilityPredictionRecord.__table__,
        Finding.__table__,
    ]

    runtime_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(runtime_engine, "connect")
    def _register_sqlite_compat(dbapi_conn, _conn_record):  # type: ignore[unused-ignore]
        dbapi_conn.create_function("btrim", 1, str.strip)
        dbapi_conn.create_function(
            "btrim",
            2,
            lambda value, chars="": (value or "").strip(chars),
        )

    with runtime_engine.begin() as conn:
        Base.metadata.create_all(conn, tables=tables)
    sync_session_factory = sessionmaker(
        bind=runtime_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    yield {
        "db_path": db_path,
        "output_root": output_root,
        "artifacts_root": artifacts_root,
        "sync_session_factory": sync_session_factory,
    }
    runtime_engine.dispose()


def test_autonomous_daily_mission_success_cycle(
    monkeypatch: pytest.MonkeyPatch,
    isolated_mission_success_environment,
):
    db_path = isolated_mission_success_environment["db_path"]
    sync_session_factory = isolated_mission_success_environment["sync_session_factory"]

    def _local_async_session_maker():
        return _AsyncSessionContext(sync_session_factory)

    monkeypatch.setattr(campaign_tasks, "get_async_session_maker", lambda: _local_async_session_maker)

    def _input_should_never_be_called(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        raise AssertionError("operator input() was invoked in offline mission mode")

    monkeypatch.setattr(builtins, "input", _input_should_never_be_called)

    # 06:00 MST = 13:00 UTC during standard-time window.
    clock = {"now": datetime(2026, 1, 15, 13, 0, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(hunting_module, "_utcnow", lambda: clock["now"])
    monkeypatch.setattr(inference_module, "_utcnow", lambda: clock["now"])

    dashboard_checks: list[list[str]] = []

    def _healthy_dashboard(
        *,
        tool_names=None,
        enabled_only=False,
        run_smoke_tests=False,
        telemetry_window=10,
        install_timeout=4,
        use_cached_install_report=True,
    ):
        _ = (
            enabled_only,
            run_smoke_tests,
            telemetry_window,
            install_timeout,
            use_cached_install_report,
        )
        names = sorted(list(tool_names or []))
        dashboard_checks.append(names)
        return {
            "tools": [{"tool_name": name, "overall_health": "healthy"} for name in names],
            "summary": {"total_tools": len(names), "healthy_tools": len(names)},
        }

    monkeypatch.setattr(hunting_module, "build_dashboard", _healthy_dashboard)
    monkeypatch.setattr(
        hunting_module,
        "_run_in_thread",
        AsyncMock(side_effect=lambda fn, *a, **k: fn(*a, **k)),
    )

    # Stage 11 contract: protected-vault session restoration for API governor target context.
    free_tier_key = "trilium-free-tier-key-001"
    trilium_client = _FakeTriliumClient(free_tier_key)
    session_manager = SessionManager(trilium_client, protected_root_id="protected-root")
    restored = _run(session_manager.get_session("api-governor"))
    assert restored is not None
    assert restored.headers.get("X-API-Key") == free_tier_key

    vault_secret_manager = _VaultSecretManager({"TRILIUM_FREE_TIER_API_KEY": free_tier_key})
    monkeypatch.setattr(hunting_module, "get_secret_manager", lambda: vault_secret_manager)
    reset_tool_catalog()
    subfinder_entry = get_catalog_entry("subfinder")
    assert subfinder_entry is not None
    assert "TRILIUM_FREE_TIER_API_KEY" in subfinder_entry.api_keys_required

    # Real registration path with deterministic fake CLI binaries.
    executed_tool_ids: list[str] = []

    original_execute_registered_tool = workflow_executor_module.execute_registered_tool
    workflow_executor_module.initialize_default_tools()
    registry = workflow_executor_module.get_registry()
    quick_sweep_template = WORKFLOW_TEMPLATES["workflow_quick_vuln_sweep"]
    required_health_tools = sorted(
        {
            step.tool
            for step in quick_sweep_template.steps
            if not str(step.tool).lower().startswith("k1_")
        }
    )
    required_registry_tools = sorted(
        {
            catalog_name_to_registry_tool_id(step.tool)
            for step in quick_sweep_template.steps
            if not str(step.tool).lower().startswith("k1_")
        }
    )
    missing_registry_tools = [tool_id for tool_id in required_registry_tools if registry.get(tool_id) is None]
    assert missing_registry_tools == [], f"workflow_quick_vuln_sweep has unregistered tools: {missing_registry_tools}"

    def _recording_execute_registered_tool(tool, params):  # noqa: ANN001
        tool_id = str(getattr(tool, "id", "")).strip()
        executed_tool_ids.append(tool_id)
        return original_execute_registered_tool(tool, params)

    monkeypatch.setattr(workflow_executor_module, "execute_registered_tool", _recording_execute_registered_tool)
    fake_bin_dir = isolated_mission_success_environment["db_path"].parent / "fake_bin"
    fake_bin_dir.mkdir(parents=True, exist_ok=True)
    fake_cli_script = """#!/usr/bin/env bash
set -euo pipefail
tool="$(basename "$0")"
day="${K1_MISSION_TEST_DAY:-1}"

if [[ "$tool" == "subfinder" ]]; then
  printf "mvp.example.com\\n"
  exit 0
fi

if [[ "$tool" == "httpx" ]]; then
  printf '{"host":"mvp.example.com","url":"https://mvp.example.com/api/v1/users?id=1","port":443,"protocol":"tcp","service":"https","tech":["nginx","python"]}\\n'
  if [[ "$day" -ge 2 ]]; then
    printf '{"host":"mvp.example.com","url":"https://mvp.example.com/api/v2/admin?debug=1","port":443,"protocol":"tcp","service":"https","tech":["nginx","python"]}\\n'
  fi
  exit 0
fi

if [[ "$tool" == "naabu" ]]; then
  printf "443\\n8443\\n"
  exit 0
fi

if [[ "$tool" == "nuclei" ]]; then
  if [[ "$day" -ge 3 ]]; then
    printf '{"templateID":"custom-timeout","severity":"high","url":"https://mvp.example.com/api/v2/admin?debug=1","matched-at":"https://mvp.example.com/api/v2/admin?debug=1"}\\n'
    printf "deterministic simulated scanner failure\\n" >&2
    exit 2
  fi
  printf '{"templateID":"sqli-candidate","severity":"high","url":"https://mvp.example.com/api/v1/users?id=1","matched-at":"https://mvp.example.com/api/v1/users?id=1"}\\n'
  exit 0
fi

if [[ "$tool" == "nikto" ]]; then
  printf '{"results":[{"title":"Nikto baseline finding","severity":"medium","url":"https://mvp.example.com/api/v1/users?id=1"}]}\\n'
  exit 0
fi

if [[ "$tool" == "dalfox" ]]; then
  printf '{"results":[{"title":"Reflected XSS candidate","severity":"medium","url":"https://mvp.example.com/api/v1/users?id=1"}]}\\n'
  exit 0
fi

printf "unexpected tool: %s\\n" "$tool" >&2
exit 64
"""
    for binary_name in ("subfinder", "httpx", "naabu", "nuclei", "nikto", "dalfox"):
        script_path = fake_bin_dir / binary_name
        script_path.write_text(fake_cli_script, encoding="utf-8")
        script_path.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin_dir}:{Path.home() / '.local/bin'}:/usr/bin:/bin")
    monkeypatch.setenv("K1_MISSION_TEST_DAY", "1")

    # Celery dispatch contract: scheduler uses .delay; we stub queueing only.
    dispatch_stub = _DispatchTaskStub()
    monkeypatch.setattr(campaign_tasks.run_bug_bounty_schedule_task, "delay", dispatch_stub.delay)
    async def _approval_gate_should_not_run(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        raise AssertionError("ApprovalGateService.create_gate invoked in offline mission mode")
    monkeypatch.setattr(approval_gate_module.ApprovalGateService, "create_gate", _approval_gate_should_not_run)

    # Stage 7 contract: keep real critic loop, mock only scope backend + sandbox execution boundary.
    scope_checks: list[dict[str, str | None]] = []

    async def _scope_validator(target_url: str, program_id: str, method: str, workflow_id: str | None = None) -> bool:
        scope_checks.append(
            {
                "target_url": target_url,
                "program_id": program_id,
                "method": method,
                "workflow_id": workflow_id,
            }
        )
        return target_url.startswith("https://mvp.example.com") and method == "exploit_poc_validation"

    monkeypatch.setattr(exploit_module, "scope_validator_async", _scope_validator)
    monkeypatch.setattr(authorization_gate_module, "scope_validator_async", _scope_validator)

    # Topology/runtime surface: contract-faithful praison topology + scaffold path check.
    agent_specs = _make_minimal_agent_specs()
    mission_spec = PraisonTopology.build_standard_bug_bounty(
        workflow_id="wf-mission-success",
        program_id="program-mission-success",
        agent_specs=agent_specs,
    )
    topology_order = resolve_execution_order(mission_spec)
    topology_scaffold = PraisonLangGraphBuilder(mission_spec, {}).build_scaffold_spec()

    assert mission_spec.entry_node
    assert mission_spec.exit_node
    assert topology_order[0] == mission_spec.entry_node
    assert mission_spec.exit_node in topology_order
    assert topology_scaffold["execution_order"] == topology_order
    mission_runtime = MissionRuntime()
    runtime_handle = mission_runtime.create_mission(
        workflow_id="wf-mission-success",
        program_id="program-mission-success",
        execution_mode="graph_only",
        graph_spec=mission_spec,
    )
    runtime_state = mission_runtime.start_mission(
        runtime_handle.mission_id,
        tenant_id=runtime_handle.tenant_id,
    )
    assert runtime_state.get("mission_id") == runtime_handle.mission_id
    assert runtime_state.get("workflow_id") == "wf-mission-success"
    assert runtime_state.get("execution_mode") == "graph_only"
    assert runtime_state.get("completed") is True
    assert not runtime_state.get("error")
    assert len(runtime_state.get("node_history") or []) >= len(topology_order)

    async def _exercise_cycle() -> dict:
        maker = _local_async_session_maker

        async def _bounded(label: str, coro):  # noqa: ANN001, ANN202
            try:
                return await asyncio.wait_for(coro, timeout=45)
            except TimeoutError as exc:
                raise AssertionError(f"timeout while waiting for {label}") from exc

        async with maker() as session:
            service = BugBountyHuntingService(session)
            program = await _bounded(
                "import_program_opportunity",
                service.import_program_opportunity(
                ProgramOpportunityImportRequest(
                    source="manual",
                    platform="hackerone",
                    name="Mission Success Program",
                    program_key="mission-success-program",
                    status="ACTIVE",
                    require_safe_mode=False,
                    in_scope_assets=[
                        {
                            "target": "mvp.example.com",
                            "target_type": "domain",
                            "monitoring_enabled": True,
                            "safe_mode_required": False,
                            "priority_tier": 1,
                        }
                    ],
                    out_of_scope_assets=[],
                ),
                actor="tests.mission_success",
                ),
            )
            targets = await _bounded("list_monitored_targets", service.list_monitored_targets(program.id))
            scope_target = next(item for item in targets if item.is_in_scope)
            schedule = await _bounded(
                "create_schedule",
                service.create_schedule(
                HuntScheduleCreateRequest(
                    program_id=program.id,
                    scope_target_id=scope_target.id,
                    workflow_template="workflow_quick_vuln_sweep",
                    schedule_type="interval",
                    interval_minutes=1440,
                    safe_mode=False,
                    dry_run=False,
                    priority_tier=1,
                    created_by="tests.mission_success",
                    next_scheduled_run_at=clock["now"],
                )
                ),
            )
            initial_readiness = await _bounded(
                "evaluate_readiness(initial)",
                service.evaluate_readiness(
                    schedule,
                    trigger_source="scheduler",
                    persist=False,
                ),
            )
            vault_secret_manager.values.clear()
            missing_key_readiness = await _bounded(
                "evaluate_readiness(missing_key)",
                service.evaluate_readiness(
                    schedule,
                    trigger_source="scheduler",
                    persist=False,
                ),
            )
            vault_secret_manager.values["TRILIUM_FREE_TIER_API_KEY"] = free_tier_key
            await session.commit()
            program_id = program.id
            scope_target_id = scope_target.id
            schedule_id = schedule.id

        # Stage 11 runtime path: worker trigger continues with credential fallbacks.
        vault_secret_manager.values.clear()
        monkeypatch.setenv("K1_MISSION_TEST_DAY", "1")
        missing_key_worker = await _bounded(
            "worker_task(missing_key)",
            campaign_tasks._trigger_bug_bounty_schedule_async(
                schedule_id=str(schedule_id),
                actor="scheduler.daemon",
                worker_role="vuln_scan_worker",
                force=False,
            ),
        )
        vault_secret_manager.values["TRILIUM_FREE_TIER_API_KEY"] = free_tier_key
        async with maker() as session:
            schedule_reset = await BugBountyHuntingService(session).get_schedule(schedule_id)
            assert schedule_reset is not None
            schedule_reset.next_scheduled_run_at = clock["now"]
            schedule_reset.last_run_status = None
            schedule_reset.last_failure_reason = None
            await session.flush()
            await session.commit()

        # Scheduler daemon dispatch contract at 06:00 MST.
        async with maker() as session:
            service = BugBountyHuntingService(session)
            dispatched = await _bounded(
                "dispatch_due_schedules(day1)",
                service.dispatch_due_schedules(
                    actor="scheduler.daemon",
                    limit=25,
                    program_id=program_id,
                ),
            )
            await session.commit()

        assert len(dispatched) == 1
        assert dispatched[0].decision_status == "DISPATCHED"
        assert dispatched[0].worker_task_id == "task-1"
        assert dispatched[0].worker_role == "vuln_scan_worker"
        assert len(dispatch_stub.calls) == 1
        assert dispatch_stub.calls[0]["schedule_id"] == str(schedule_id)

        # Worker entrypoint executes mission run from real trigger path.
        first_payload = dict(dispatch_stub.calls[0])
        assert first_payload["actor"] == "scheduler.daemon"
        assert first_payload["worker_role"] == "vuln_scan_worker"
        assert first_payload["force"] is False
        first_worker_payload = {**first_payload, "force": True}
        monkeypatch.setenv("K1_MISSION_TEST_DAY", "1")
        first = await _bounded(
            "worker_task(day1)",
            campaign_tasks._trigger_bug_bounty_schedule_async(**first_worker_payload),
        )
        expected_run1 = f"bb-{UUID(str(schedule_id)).hex[:8]}-{int(clock['now'].timestamp())}"
        assert first["decision_status"] == "READY"
        assert first["run_id"] == expected_run1
        assert first["details"].get("status") in {"COMPLETED", "COMPLETED_WITH_FAILURES"}

        # Before next 06:00 MST run, schedule must remain blocked by scheduler policy.
        clock["now"] = clock["now"] + timedelta(days=1) - timedelta(minutes=1)
        async with maker() as session:
            service = BugBountyHuntingService(session)
            schedule_before_due = await service.get_schedule(schedule_id)
            assert schedule_before_due is not None
            pre_due_readiness = await _bounded(
                "evaluate_readiness(pre_due)",
                service.evaluate_readiness(
                    schedule_before_due,
                    trigger_source="scheduler",
                    persist=False,
                ),
            )
            pre_due_dispatch = await _bounded(
                "dispatch_due_schedules(pre_due)",
                service.dispatch_due_schedules(
                    actor="scheduler.daemon",
                    limit=25,
                    program_id=program_id,
                ),
            )
            await session.commit()
        assert pre_due_readiness.decision_status == hunting_module.READINESS_BLOCKED_COOLDOWN
        assert pre_due_dispatch == []
        assert len(dispatch_stub.calls) == 1

        # Exact next 06:00 MST: second mission run.
        clock["now"] = clock["now"] + timedelta(minutes=1)
        async with maker() as session:
            service = BugBountyHuntingService(session)
            dispatched_day2 = await _bounded(
                "dispatch_due_schedules(day2)",
                service.dispatch_due_schedules(
                    actor="scheduler.daemon",
                    limit=25,
                    program_id=program_id,
                ),
            )
            await session.commit()

        assert len(dispatched_day2) == 1
        assert dispatched_day2[0].decision_status == "DISPATCHED"
        assert dispatched_day2[0].worker_task_id == "task-2"
        assert len(dispatch_stub.calls) == 2
        second_payload = dict(dispatch_stub.calls[1])
        assert second_payload["actor"] == "scheduler.daemon"
        assert second_payload["force"] is False
        second_worker_payload = {**second_payload, "force": True}
        monkeypatch.setenv("K1_MISSION_TEST_DAY", "2")
        second = await _bounded(
            "worker_task(day2)",
            campaign_tasks._trigger_bug_bounty_schedule_async(**second_worker_payload),
        )
        expected_run2 = f"bb-{UUID(str(schedule_id)).hex[:8]}-{int(clock['now'].timestamp())}"
        assert second["decision_status"] == "READY"
        assert second["run_id"] == expected_run2
        assert second["details"].get("status") in {"COMPLETED", "COMPLETED_WITH_FAILURES"}

        # Stage 7 sandbox critic contract.
        execution_attempts: list[str] = []
        critic_feedback: list[str] = []
        query_layer = OrchestrationQueryLayer(trilium_client)
        coordinator = ExploitCoordinator(query_layer=query_layer, llm_client=object())

        async def _sandbox_exec(payload: str, payload_type: str = "python") -> ExecutionResult:
            execution_attempts.append(payload_type)
            if len(execution_attempts) == 1:
                return ExecutionResult(success=False, stdout="", stderr="blocked", error_message="blocked")
            return ExecutionResult(success=True, stdout="VERIFIED: POC", stderr="")

        def _critic_instruction(result: ExecutionResult) -> str:
            critic_feedback.append(result.error_message or "")
            return "adjust payload to bypass block"

        coordinator.sandbox.execute_payload = _sandbox_exec  # type: ignore[method-assign]
        monkeypatch.setattr(coordinator.sandbox, "generate_critic_instruction", _critic_instruction)
        stage7_workflow_id = str(second.get("workflow_run_id") or "")

        exploit_ok = await _bounded(
            "process_exploitable_note",
            coordinator.process_exploitable_note(
                "note-exploit",
                program_id=str(program_id),
                workflow_id=stage7_workflow_id or None,
            ),
        )
        assert exploit_ok is True
        assert len(execution_attempts) == 2
        assert critic_feedback == ["blocked"]
        assert ("note-exploit", "label", "status", "verified_poc") in trilium_client.created_attributes

        # Day 3 deterministic failure: mission must not silently drop.
        clock["now"] = clock["now"] + timedelta(days=1)
        async with maker() as session:
            service = BugBountyHuntingService(session)
            dispatched_day3 = await _bounded(
                "dispatch_due_schedules(day3)",
                service.dispatch_due_schedules(
                    actor="scheduler.daemon",
                    limit=25,
                    program_id=program_id,
                ),
            )
            await session.commit()

        assert len(dispatched_day3) == 1
        assert dispatched_day3[0].decision_status == "DISPATCHED"
        assert dispatched_day3[0].worker_task_id == "task-3"
        assert len(dispatch_stub.calls) == 3
        third_payload = dict(dispatch_stub.calls[2])
        assert third_payload["actor"] == "scheduler.daemon"
        assert third_payload["force"] is False
        third_worker_payload = {**third_payload, "force": True}
        monkeypatch.setenv("K1_MISSION_TEST_DAY", "3")
        third = await _bounded(
            "worker_task(day3)",
            campaign_tasks._trigger_bug_bounty_schedule_async(**third_worker_payload),
        )
        expected_run3 = f"bb-{UUID(str(schedule_id)).hex[:8]}-{int(clock['now'].timestamp())}"
        assert third["decision_status"] == "READY"
        assert third["run_id"] == expected_run3
        assert third["details"].get("status") == "COMPLETED_WITH_FAILURES"

        # Real aggregation + inference path.
        async with maker() as session:
            inference_payload = await _bounded(
                "run_inference",
                ReconInferenceService(session).run_inference(
                    program_id=program_id,
                    actor="scheduler.inference",
                    apply_adaptive=True,
                ),
            )
            await session.commit()

        async with maker() as session:
            schedule_row = await BugBountyHuntingService(session).get_schedule(schedule_id)
            readiness_rows = list(
                (
                    await session.execute(
                        select(HuntReadinessRecord).where(HuntReadinessRecord.schedule_job_id == schedule_id)
                    )
                ).scalars()
            )
            delta_rows = list(
                (
                    await session.execute(
                        select(WorkflowDeltaRecord).where(WorkflowDeltaRecord.program_id == program_id)
                    )
                ).scalars()
            )
            workflow_runs = list(
                (
                    await session.execute(
                        select(WorkflowRun).where(WorkflowRun.scope_target_id == scope_target_id)
                    )
                ).scalars()
            )
            signal_rows = list(
                (
                    await session.execute(
                        select(SignalIntelligenceRecord).where(SignalIntelligenceRecord.program_id == program_id)
                    )
                ).scalars()
            )
            inference_rows = list(
                (
                    await session.execute(
                        select(OpportunityInferenceRecord).where(OpportunityInferenceRecord.program_id == program_id)
                    )
                ).scalars()
            )
            alert_rows = list(
                (
                    await session.execute(
                        select(NotificationAlertRecord).where(NotificationAlertRecord.program_id == program_id)
                    )
                ).scalars()
            )
            audit_rows = list(
                (
                    await session.execute(
                        select(AuditEvent).where(AuditEvent.event_type.like("bugbounty.%"))
                    )
                ).scalars()
            )
            phase6_audits = list(
                (
                    await session.execute(
                        select(AuditEvent).where(AuditEvent.event_type.like("phase6.%"))
                    )
                ).scalars()
            )
            approval_gates = list((await session.execute(select(ApprovalGate))).scalars())
            tool_rows = list((await session.execute(select(ToolExecution))).scalars())

        return {
            "program_id": str(program_id),
            "scope_target_id": str(scope_target_id),
            "schedule_id": str(schedule_id),
            "due_statuses": [first["details"].get("status"), second["details"].get("status"), third["details"].get("status")],
            "run_ids": [first["run_id"], second["run_id"], third["run_id"]],
            "pre_due_status": pre_due_readiness.decision_status,
            "run_order_count": len({first["run_id"], second["run_id"], third["run_id"]}),
            "readiness": readiness_rows,
            "deltas": delta_rows,
            "workflow_runs": workflow_runs,
            "signals": signal_rows,
            "inferences": inference_rows,
            "alerts": alert_rows,
            "audit": audit_rows,
            "phase6_audit": phase6_audits,
            "schedule": schedule_row,
            "inference_payload": inference_payload,
            "approval_gates": approval_gates,
            "tool_rows": tool_rows,
            "executed_tool_ids": executed_tool_ids,
            "dashboard_checks": dashboard_checks,
            "scope_checks": scope_checks,
            "stage7_workflow_id": stage7_workflow_id,
            "missing_key_readiness": missing_key_readiness,
            "initial_readiness": initial_readiness,
            "missing_key_worker": missing_key_worker,
        }

    persisted = _run(_exercise_cycle())

    readiness_rows = persisted["readiness"]
    delta_rows = persisted["deltas"]
    workflow_runs = persisted["workflow_runs"]
    signal_rows = persisted["signals"]
    inference_rows = persisted["inferences"]
    alert_rows = persisted["alerts"]
    audit_rows = persisted["audit"]
    phase6_audit = persisted["phase6_audit"]
    schedule_row = persisted["schedule"]
    initial_readiness = persisted["initial_readiness"]

    assert persisted["pre_due_status"] == hunting_module.READINESS_BLOCKED_COOLDOWN
    assert len(persisted["due_statuses"]) == 3
    assert persisted["due_statuses"][0] in {"COMPLETED", "COMPLETED_WITH_FAILURES"}
    assert persisted["due_statuses"][1] in {"COMPLETED", "COMPLETED_WITH_FAILURES"}
    assert persisted["due_statuses"][2] == "COMPLETED_WITH_FAILURES"
    assert persisted["run_order_count"] == 3

    # Real readiness + Stage 11 credential requirement path.
    assert any(str(row.trigger_source).startswith("worker.") for row in readiness_rows)
    assert any(row.event_type == "bugbounty.schedule.dispatched" and row.actor == "scheduler.daemon" for row in audit_rows)
    assert initial_readiness.decision_status == hunting_module.READINESS_READY
    assert not initial_readiness.details.get("credentials", {}).get("missing_keys", [])
    assert "TRILIUM_FREE_TIER_API_KEY" in initial_readiness.details.get("credentials", {}).get(
        "present_keys", []
    )
    assert "TRILIUM_FREE_TIER_API_KEY" in vault_secret_manager.requested_keys
    assert persisted["missing_key_readiness"].decision_status == hunting_module.READINESS_READY
    assert "TRILIUM_FREE_TIER_API_KEY" in (
        persisted["missing_key_readiness"].details.get("credentials", {}).get("missing_keys", [])
    )
    assert persisted["missing_key_worker"]["decision_status"] == hunting_module.READINESS_READY
    assert persisted["missing_key_worker"].get("run_id")

    # Delta discovery propagation + inference provenance.
    assert any(row.event_type == "bugbounty.delta.detected" for row in audit_rows)
    assert len(delta_rows) >= 1
    assert any(str(row.change_type) == "NEW" for row in delta_rows)

    assert persisted["inference_payload"]["created_signals"] > 0
    assert persisted["inference_payload"]["scores_created"] > 0
    assert persisted["inference_payload"]["swarm_records_created"] >= 0
    assert len(signal_rows) >= 1
    assert len(inference_rows) >= 1
    assert any(row.recommended_workflow in WORKFLOW_TEMPLATES for row in inference_rows)
    assert all(0.0 <= float(row.opportunity_score or 0.0) <= 100.0 for row in inference_rows)
    assert all(str(row.next_best_action or "").strip() for row in inference_rows)
    assert all(
        isinstance(row.supporting_evidence_json, list) and len(row.supporting_evidence_json) > 0
        for row in inference_rows
    )
    assert all(
        isinstance(row.details_json, dict)
        and int(row.details_json.get("signals_total", 0)) > 0
        and int(row.details_json.get("delta_growth", 0)) > 0
        for row in inference_rows
    )
    assert any("delta_growth=" in str(row.reasoning_summary or "") for row in inference_rows)

    statuses = {row.status for row in workflow_runs}
    assert WorkflowRunStatusEnum.COMPLETED in statuses
    assert WorkflowRunStatusEnum.FAILED in statuses

    # No silent wiring skip: registry-backed tools must execute and unknown IDs fail fast.
    executed_tool_ids = persisted["executed_tool_ids"]
    assert any("subfinder" in tool_id for tool_id in executed_tool_ids)
    assert any("httpx" in tool_id for tool_id in executed_tool_ids)
    assert any("nuclei" in tool_id for tool_id in executed_tool_ids)
    assert any("nikto" in tool_id for tool_id in executed_tool_ids)
    assert any(tool_id.startswith("k1_") for tool_id in executed_tool_ids)
    assert "k1_sandbox_critic" in executed_tool_ids

    assert all("tool_not_registered" not in str(item.error_message or "") for item in persisted["tool_rows"])
    assert all("missing_tool_id" not in str(item.error_message or "") for item in persisted["tool_rows"])

    # Operator-offline proof: no interactive/HIL gate blocking for this mission path.
    assert persisted["approval_gates"] == []
    assert all(item.status != ToolExecutionStatusEnum.WAITING_APPROVAL for item in persisted["tool_rows"])

    # Stage 7 sandbox critic scope/policy semantics were exercised in-flow and via coordinator.
    scope_checks = persisted["scope_checks"]
    assert len(scope_checks) >= 2
    assert all(item["method"] == "exploit_poc_validation" for item in scope_checks)
    assert all(item["program_id"] == persisted["program_id"] for item in scope_checks)
    assert any(str(item["target_url"]).startswith("https://mvp.example.com") for item in scope_checks)
    assert any(str(item["target_url"]).endswith("/poc") for item in scope_checks)
    assert any(item["workflow_id"] == (persisted["stage7_workflow_id"] or None) for item in scope_checks)

    # Audit/event and downstream pipeline evidence.
    event_types = {row.event_type for row in audit_rows}
    assert "bugbounty.schedule.dispatched" in event_types
    assert "bugbounty.schedule.triggered" in event_types
    assert "bugbounty.readiness.evaluated" in event_types
    assert "bugbounty.delta.detected" in event_types
    triggered_events = [row for row in audit_rows if row.event_type == "bugbounty.schedule.triggered"]
    assert len(triggered_events) == 3
    triggered_payloads = [
        row.event_payload_json if isinstance(row.event_payload_json, dict) else {}
        for row in triggered_events
    ]
    assert {str(payload.get("run_id") or "") for payload in triggered_payloads} == set(persisted["run_ids"])
    assert any(str(payload.get("status") or "") == "COMPLETED_WITH_FAILURES" for payload in triggered_payloads)
    assert any(row.event_type == "phase6.signals.aggregated" for row in phase6_audit)
    assert any(row.event_type == "phase6.inference.completed" for row in phase6_audit)

    # Alert/case downstream contract is exercised via sync path.
    assert any(row.event_type == "bugbounty.alert.sync" for row in audit_rows)
    assert len(alert_rows) >= 1
    assert any(str(alert.alert_type) == "SEVERE_DELTA_DETECTED" for alert in alert_rows)
    assert all(str(alert.status) in {"OPEN", "ACKNOWLEDGED", "RESOLVED", "SUPPRESSED"} for alert in alert_rows)
    assert all(
        isinstance(alert.supporting_record_ids_json, list) and len(alert.supporting_record_ids_json) > 0
        for alert in alert_rows
    )

    # Scheduler readiness health gate was actually checked.
    assert len(persisted["dashboard_checks"]) >= 1
    assert all("subfinder" in tools for tools in persisted["dashboard_checks"])
    assert all(set(required_health_tools).issubset(set(tools)) for tools in persisted["dashboard_checks"])

    assert schedule_row is not None
    assert schedule_row.consecutive_failures == 1
    assert schedule_row.last_run_status == "COMPLETED_WITH_FAILURES"
    assert str(schedule_row.last_failure_reason or "").strip() in {
        "COMPLETED_WITH_FAILURES",
        "execution completed with failures",
    }

    output_root = Path(hunting_module.workflow_output_root())
    approval_required_execution_seen = False
    sandbox_critic_execution_seen = False
    for idx, run_id in enumerate(persisted["run_ids"], start=1):
        manifest = output_root / "workflows" / run_id / "manifest.json"
        summary = output_root / "workflows" / run_id / "summary.json"
        report = output_root / "reports" / run_id / "report.md"
        workflow_log = output_root / "logs" / f"workflow_{run_id}.jsonl"
        subfinder_raw = output_root / "raw" / run_id / "passive_recon" / "subfinder.json"
        httpx_raw = output_root / "raw" / run_id / "live_host_validation" / "httpx_probe.json"
        nuclei_raw = output_root / "raw" / run_id / "vuln_scan" / "nuclei_scan.json"
        sandbox_raw = output_root / "raw" / run_id / "report_prep" / "k1_sandbox_critic.json"

        assert manifest.exists()
        assert summary.exists()
        assert report.exists()
        assert workflow_log.exists()
        assert subfinder_raw.exists()
        assert httpx_raw.exists()
        assert nuclei_raw.exists()
        assert sandbox_raw.exists()

        manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
        summary_payload = json.loads(summary.read_text(encoding="utf-8"))
        assert manifest_payload.get("status") in {"COMPLETED", "COMPLETED_WITH_FAILURES"}
        assert manifest_payload.get("workflow_template") == "workflow_quick_vuln_sweep"
        assert manifest_payload.get("target") == "mvp.example.com"
        assert summary_payload.get("status") in {"COMPLETED", "COMPLETED_WITH_FAILURES"}
        assert isinstance(summary_payload.get("stage_results"), list)
        assert summary_payload.get("metrics", {}).get("tool_executions_total", 0) > 0
        stage_results = summary_payload.get("stage_results", [])
        assert [stage.get("stage") for stage in stage_results] == [
            "passive_recon",
            "live_host_validation",
            "vuln_scan",
            "prioritization_and_correlation",
            "report_prep",
        ]
        if any(
            bool((execution.get("metadata") or {}).get("approval_required"))
            for stage in stage_results
            for execution in (stage.get("executions") or [])
            if isinstance(execution, dict)
        ):
            approval_required_execution_seen = True
        if any(
            str((execution or {}).get("tool_id") or (execution or {}).get("tool_name") or "") == "k1_sandbox_critic"
            for stage in stage_results
            for execution in (stage.get("executions") or [])
            if isinstance(execution, dict)
        ):
            sandbox_critic_execution_seen = True

        httpx_payload = json.loads(httpx_raw.read_text(encoding="utf-8"))
        subfinder_payload = json.loads(subfinder_raw.read_text(encoding="utf-8"))
        sandbox_payload = json.loads(sandbox_raw.read_text(encoding="utf-8"))
        subfinder_result = subfinder_payload.get("result") if isinstance(subfinder_payload, dict) else {}
        subfinder_output = subfinder_result.get("output") if isinstance(subfinder_result, dict) else {}
        assert str(subfinder_result.get("status") or "").lower() == "completed"
        subfinder_subdomains = subfinder_output.get("subdomains") if isinstance(subfinder_output, dict) else []
        assert isinstance(subfinder_subdomains, list) and "mvp.example.com" in subfinder_subdomains
        assert str(subfinder_output.get("raw") or "").strip() == "mvp.example.com"

        sandbox_result = sandbox_payload.get("result") if isinstance(sandbox_payload, dict) else {}
        sandbox_metadata = sandbox_result.get("metadata") if isinstance(sandbox_result, dict) else {}
        assert sandbox_metadata.get("stage7_contract") is True
        assert sandbox_metadata.get("scope_gate_checked") is True
        assert sandbox_metadata.get("scope_gate_allowed") is True

        urls = [
            str(record.get("url") or "").strip()
            for record in (((httpx_payload.get("result") or {}).get("output") or {}).get("records") or [])
            if isinstance(record, dict)
        ]
        if idx == 1:
            assert not any("/api/v2/admin" in url for url in urls)
        else:
            assert any("/api/v2/admin" in url for url in urls)

        log_rows = [
            json.loads(line)
            for line in workflow_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert all(row.get("event") == "tool_execution" for row in log_rows)
        assert all(str(row.get("tool_id") or "").strip() for row in log_rows)
        if idx == 3:
            vuln_stage = next(stage for stage in stage_results if stage.get("stage") == "vuln_scan")
            assert int(vuln_stage.get("failed_count") or 0) >= 1
            nuclei_payload = json.loads(nuclei_raw.read_text(encoding="utf-8"))
            assert str((nuclei_payload.get("result") or {}).get("status") or "").lower() == "failed"
            nuclei_error_text = str(
                (nuclei_payload.get("result") or {}).get("error")
                or (((nuclei_payload.get("result") or {}).get("output") or {}).get("stderr") or "")
            )
            assert "deterministic simulated scanner failure" in nuclei_error_text
            assert any(str(row.get("status")) == "FAILED" and row.get("tool_id") == "nuclei_scan" for row in log_rows)

    assert approval_required_execution_seen
    assert sandbox_critic_execution_seen

    # Persistence continuity: reopen from disk-backed DB with a fresh engine/session.
    reopen_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    reopen_session_factory = sessionmaker(
        bind=reopen_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    reopen_session = reopen_session_factory()
    try:
        reopened_workflow_runs = list(reopen_session.execute(select(WorkflowRun.id)).scalars())
        reopened_audits = list(
            reopen_session.execute(
                select(AuditEvent.id).where(AuditEvent.event_type.like("bugbounty.%"))
            ).scalars()
        )
        reopened_alerts = list(
            reopen_session.execute(
                select(NotificationAlertRecord.id).where(
                    NotificationAlertRecord.program_id == UUID(persisted["program_id"])
                )
            ).scalars()
        )
        reopened_schedule = reopen_session.execute(
            select(HuntScheduleJob).where(HuntScheduleJob.id == UUID(persisted["schedule_id"]))
        ).scalar_one()
        assert len(reopened_workflow_runs) == len(workflow_runs)
        assert len(reopened_audits) == len(audit_rows)
        assert len(reopened_alerts) == len(alert_rows)
        assert reopened_schedule.last_run_status == "COMPLETED_WITH_FAILURES"
        assert reopened_schedule.consecutive_failures == 1
    finally:
        reopen_session.close()
        reopen_engine.dispose()
