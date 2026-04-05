from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

import apps.backend.src.core.praison_mission_runtime as runtime_module
from apps.backend.src.agents.crew.api_security_agent import APISecurityAgent
from apps.backend.src.agents.crew.content_discovery_agent import ContentDiscoveryAgent
from apps.backend.src.agents.crew.dark_web_intel_agent import DarkWebIntelAgent
from apps.backend.src.agents.crew.faraday_coordinator_agent import FaradayCoordinatorAgent
from apps.backend.src.agents.crew.osint_intelligence_agent import OSINTIntelligenceAgent
from apps.backend.src.agents.crew.secret_scanner_agent import SecretScannerAgent
from apps.backend.src.agents.crew.vulnerability_agent import VulnerabilityAgent
from apps.backend.src.auth.dependencies import CurrentUser
from apps.backend.src.auth.models import UserRole
from apps.backend.src.core.praison_execution_events import get_event_bus, reset_event_bus
from apps.backend.src.core.praison_mission_runtime import get_mission_runtime
from apps.backend.src.routers import mission_control
from apps.backend.src.routers.mission_control import MissionCreateRequest


def _run(coro):
    return asyncio.run(coro)


def _drain_background_tasks(background: BackgroundTasks) -> None:
    for task in list(background.tasks):
        result = task.func(*task.args, **task.kwargs)
        if inspect.isawaitable(result):
            _run(result)


def _build_user() -> CurrentUser:
    tenant_id = uuid4()
    return CurrentUser(
        id=uuid4(),
        tenant_id=tenant_id,
        username="integration-user",
        email=None,
        full_name="Integration User",
        is_active=True,
        is_superuser=True,
        must_change_password=False,
        role=UserRole.ADMIN.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _node_index(node_history: list[dict], node_id: str) -> int:
    for idx, row in enumerate(node_history):
        if str(row.get("node_id", "")) == node_id:
            return idx
    raise AssertionError(f"node_id missing from history: {node_id}")


@pytest.fixture()
def mission_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(artifacts_root))
    monkeypatch.setenv("K1_OPERATOR", "false")

    runtime_module._RUNTIME = None
    reset_event_bus()
    yield {"artifacts_root": artifacts_root}
    runtime_module._RUNTIME = None
    reset_event_bus()


def test_wave45_enable_crew_agents_end_to_end_real_validation(
    monkeypatch: pytest.MonkeyPatch,
    mission_env,
    tmp_path: Path,
):
    tool_dir = tmp_path / "tool_boundaries"
    tool_dir.mkdir(parents=True, exist_ok=True)

    success_tool = tool_dir / "tool_success"
    success_tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n", encoding="utf-8")
    success_tool.chmod(0o755)

    slow_tool = tool_dir / "tool_slow"
    slow_tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\nsleep 2\necho slow\n", encoding="utf-8")
    slow_tool.chmod(0o755)

    async def _osint(self, mission_context: dict, prior_findings: list[dict]) -> dict:  # noqa: ANN001
        _ = prior_findings
        return {
            "osint_intelligence_complete": True,
            "findings": [
                {
                    "source": "OSINTIntelligenceAgent",
                    "finding_type": "domain_intel",
                    "target": mission_context.get("program_id", ""),
                    "severity": "info",
                }
            ],
        }

    async def _dark_web(self, mission_context: dict, prior_findings: list[dict]) -> dict:  # noqa: ANN001
        _ = prior_findings
        return {
            "dark_web_intel_complete": True,
            "findings": [
                {
                    "source": "DarkWebIntelAgent",
                    "finding_type": "darkweb_mention",
                    "target": mission_context.get("program_id", ""),
                    "severity": "medium",
                }
            ],
        }

    async def _secret(self, mission_context: dict, prior_findings: list[dict]) -> dict:  # noqa: ANN001
        _ = prior_findings
        return {
            "secret_scan_complete": True,
            "findings": [
                {
                    "source": "SecretScannerAgent",
                    "finding_type": "secret_candidate",
                    "target": mission_context.get("program_id", ""),
                    "severity": "high",
                }
            ],
        }

    async def _content(self, mission_context: dict, prior_findings: list[dict]) -> dict:  # noqa: ANN001
        _ = prior_findings
        return {
            "content_discovery_complete": True,
            "findings": [
                {
                    "source": "ContentDiscoveryAgent",
                    "finding_type": "endpoint",
                    "target": mission_context.get("program_id", ""),
                    "severity": "info",
                }
            ],
        }

    async def _vulnerability(self, mission_context: dict, prior_findings: list[dict]) -> dict:  # noqa: ANN001
        _ = mission_context
        _ = prior_findings
        subprocess.run([str(success_tool)], check=True, capture_output=True, text=True, timeout=1.0)

        partial_failures: list[dict[str, str]] = []
        timeout_seen = False
        missing_binary_seen = False

        try:
            subprocess.run([str(slow_tool)], check=True, capture_output=True, text=True, timeout=0.1)
        except subprocess.TimeoutExpired:
            timeout_seen = True
            partial_failures.append({"tool": "tool_slow", "error": "timeout"})

        try:
            subprocess.run(["k1_missing_binary_for_validation"], check=True, capture_output=True, text=True, timeout=1.0)
        except FileNotFoundError:
            missing_binary_seen = True
            partial_failures.append({"tool": "k1_missing_binary_for_validation", "error": "not_found"})

        return {
            "vulnerability_assessment_complete": True,
            "partial_failures": partial_failures,
            "boundary_checks": {
                "timeout_handled": timeout_seen,
                "unavailable_binary_handled": missing_binary_seen,
                "partial_failures_count": len(partial_failures),
            },
            "findings": [
                {
                    "source": "VulnerabilityAgent",
                    "finding_type": "vuln_candidate",
                    "target": "controlled.example.com",
                    "severity": "high",
                }
            ],
        }

    async def _api_security(self, mission_context: dict, prior_findings: list[dict]) -> dict:  # noqa: ANN001
        _ = prior_findings
        return {
            "api_security_complete": True,
            "findings": [
                {
                    "source": "APISecurityAgent",
                    "finding_type": "api_surface",
                    "target": mission_context.get("program_id", ""),
                    "severity": "medium",
                }
            ],
        }

    async def _faraday(self, mission_context: dict, prior_findings: list[dict]) -> dict:  # noqa: ANN001
        _ = mission_context
        sources = sorted(
            {
                str(row.get("source", "")).strip()
                for row in prior_findings
                if isinstance(row, dict) and str(row.get("source", "")).strip()
            }
        )
        return {
            "aggregation_complete": True,
            "master_findings_count": len(prior_findings),
            "d_stage_sources": sources,
        }

    monkeypatch.setattr(OSINTIntelligenceAgent, "execute", _osint)
    monkeypatch.setattr(DarkWebIntelAgent, "execute", _dark_web)
    monkeypatch.setattr(SecretScannerAgent, "execute", _secret)
    monkeypatch.setattr(ContentDiscoveryAgent, "execute", _content)
    monkeypatch.setattr(VulnerabilityAgent, "execute", _vulnerability)
    monkeypatch.setattr(APISecurityAgent, "execute", _api_security)
    monkeypatch.setattr(FaradayCoordinatorAgent, "execute", _faraday)

    user = _build_user()

    payload = MissionCreateRequest(
        workflow_id="wf-wave45-live",
        program_id="controlled.example.com",
        mission_name="wave45-live",
        execution_mode="live",
        enable_crew_agents=True,
    )
    created = _run(mission_control.create_mission(payload, current_user=user))
    created_status = _run(mission_control.get_mission_status(created.mission_id, current_user=user))

    bg = BackgroundTasks()
    started = _run(mission_control.start_mission(created.mission_id, bg, current_user=user))
    _drain_background_tasks(bg)

    completed_status = _run(mission_control.get_mission_status(created.mission_id, current_user=user))
    all_statuses = _run(mission_control.list_missions(current_user=user))

    runtime = get_mission_runtime()
    final_state = runtime.get_state(created.mission_id)
    events = get_event_bus().for_mission(created.mission_id)

    telemetry_path = Path(mission_env["artifacts_root"]) / "telemetry" / "mission_events.jsonl"
    report_artifact = next(
        (
            row
            for row in final_state.get("artifacts", [])
            if isinstance(row, dict) and row.get("artifact_type") == "final_report"
        ),
        None,
    )
    report_path = Path(str(report_artifact.get("artifact_path", ""))) if report_artifact else None
    report_payload = json.loads(report_path.read_text(encoding="utf-8")) if report_path and report_path.exists() else {}

    result = {
        "created": created,
        "created_status": created_status,
        "started": started,
        "completed_status": completed_status,
        "all_statuses": all_statuses,
        "final_state": final_state,
        "events": events,
        "telemetry_path": telemetry_path,
        "report_path": report_path,
        "report_payload": report_payload,
    }
    final_state = result["final_state"]
    node_history = [row for row in final_state.get("node_history", []) if isinstance(row, dict)]

    assert result["created"].state == "created"
    assert result["created_status"].state == "created"
    assert result["started"]["status"] == "started"
    assert result["completed_status"].state == "completed"
    assert any(row.mission_id == result["created"].mission_id for row in result["all_statuses"])

    idx_surface = _node_index(node_history, "specialist_cluster_surface_scan")
    idx_content = _node_index(node_history, "specialist_cluster_contentdiscoveryagent")
    idx_vuln = _node_index(node_history, "specialist_cluster_vulnerabilityagent")
    idx_api = _node_index(node_history, "specialist_cluster_apisecurityagent")
    idx_osint = _node_index(node_history, "specialist_cluster_osintintelligenceagent")
    idx_dark = _node_index(node_history, "specialist_cluster_darkwebintelagent")
    idx_secret = _node_index(node_history, "specialist_cluster_secretscanneragent")
    idx_faraday = _node_index(node_history, "specialist_cluster_faradaycoordinatoragent")
    idx_evidence = _node_index(node_history, "evidence_analysis")
    idx_report = _node_index(node_history, "report_synthesis")
    idx_handoff = _node_index(node_history, "handoff_liaison")

    assert idx_surface < idx_content
    assert idx_content < idx_vuln
    assert idx_content < idx_api
    assert max(idx_vuln, idx_api, idx_osint, idx_dark, idx_secret) < idx_faraday
    assert idx_faraday < idx_evidence < idx_report < idx_handoff

    assert final_state.get("aggregation_complete") is True
    assert int(final_state.get("master_findings_count", 0)) >= 6
    assert set(final_state.get("d_stage_sources", [])) >= {
        "OSINTIntelligenceAgent",
        "DarkWebIntelAgent",
        "SecretScannerAgent",
        "ContentDiscoveryAgent",
        "VulnerabilityAgent",
        "APISecurityAgent",
    }

    boundary_checks = final_state.get("boundary_checks", {})
    assert boundary_checks.get("timeout_handled") is True
    assert boundary_checks.get("unavailable_binary_handled") is True
    assert int(boundary_checks.get("partial_failures_count", 0)) >= 2
    assert len(final_state.get("partial_failures", [])) >= 2

    assert final_state.get("completed") is True
    assert float(final_state.get("progress", 0.0)) == 1.0
    assert str(final_state.get("final_report_id", "")).startswith("report-")

    report_path = result["report_path"]
    assert report_path is not None and report_path.exists()
    assert result["report_payload"].get("mission_id") == result["created"].mission_id
    assert int(result["report_payload"].get("finding_count", 0)) >= 6

    telemetry_path = result["telemetry_path"]
    assert telemetry_path.exists()
    telemetry_rows = [
        json.loads(line)
        for line in telemetry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    mission_rows = [row for row in telemetry_rows if row.get("mission_id") == result["created"].mission_id]
    assert any(row.get("event_type") == "mission_started" for row in mission_rows)
    assert any(row.get("event_type") == "mission_completed" for row in mission_rows)
    assert any(row.get("event_type") == "node_completed" and row.get("node_id") == "specialist_cluster_faradaycoordinatoragent" for row in mission_rows)
    assert len(result["events"]) >= len(node_history)


def test_wave45_flag_off_regression_and_graph_only_fallback(
    monkeypatch: pytest.MonkeyPatch,
    mission_env,
):
    user = _build_user()

    async def _run_mission(enable_crew_agents: bool, workflow_id: str) -> tuple[str, dict]:
        payload = MissionCreateRequest(
            workflow_id=workflow_id,
            program_id="controlled.example.com",
            mission_name=workflow_id,
            execution_mode="live",
            enable_crew_agents=enable_crew_agents,
        )
        created = await mission_control.create_mission(payload, current_user=user)
        return created.mission_id, {}

    mission_id_no_crew, _ = _run(_run_mission(enable_crew_agents=False, workflow_id="wf-wave45-no-crew"))
    bg_no_crew = BackgroundTasks()
    _run(mission_control.start_mission(mission_id_no_crew, bg_no_crew, current_user=user))
    _drain_background_tasks(bg_no_crew)
    state_no_crew = get_mission_runtime().get_state(mission_id_no_crew)
    assert state_no_crew.get("completed") is True
    assert not state_no_crew.get("error")
    assert str(state_no_crew.get("final_report_id", "")).startswith("report-")
    assert "boundary_checks" not in state_no_crew

    import apps.backend.src.core.crew_agent_factory as crew_factory

    monkeypatch.setattr(
        crew_factory,
        "instantiate_crew_agents",
        lambda: (_ for _ in ()).throw(RuntimeError("forced crew factory failure")),
    )
    mission_id_fallback, _ = _run(_run_mission(enable_crew_agents=True, workflow_id="wf-wave45-fallback"))
    bg_fallback = BackgroundTasks()
    _run(mission_control.start_mission(mission_id_fallback, bg_fallback, current_user=user))
    _drain_background_tasks(bg_fallback)
    state_fallback = get_mission_runtime().get_state(mission_id_fallback)
    assert state_fallback.get("completed") is True
    assert not state_fallback.get("error")
    assert str(state_fallback.get("final_report_id", "")).startswith("report-")
    assert "aggregation_complete" not in state_fallback
    fallback_nodes = {
        str(row.get("node_id", ""))
        for row in (state_fallback.get("node_history") or [])
        if isinstance(row, dict)
    }
    assert {
        "specialist_cluster_surface_scan",
        "specialist_cluster_contentdiscoveryagent",
        "specialist_cluster_vulnerabilityagent",
        "specialist_cluster_faradaycoordinatoragent",
    }.issubset(fallback_nodes)
    assert "osint_intelligence_complete" not in state_fallback
    assert any(
        row.get("node_id") == "specialist_cluster_surface_scan" and row.get("mode") == "live"
        for row in (state_fallback.get("events") or [])
        if isinstance(row, dict)
    )

    telemetry_path = Path(mission_env["artifacts_root"]) / "telemetry" / "mission_events.jsonl"
    assert telemetry_path.exists()
    telemetry_rows = [
        json.loads(line)
        for line in telemetry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    mission_ids = {row.get("mission_id") for row in telemetry_rows}
    assert mission_id_no_crew in mission_ids
    assert mission_id_fallback in mission_ids
