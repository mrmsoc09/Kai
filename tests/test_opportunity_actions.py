from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from apps.backend.src.core.opportunity_actions import OpportunityActionService
from apps.backend.src.core.opportunity_catalog import Opportunity
from apps.backend.src.core.scope_guardrails import ScopePolicy


@dataclass
class _FakeMissionHandle:
    mission_id: str


@dataclass
class _FakeMissionStatus:
    state: str


class _FakeRuntime:
    def __init__(self) -> None:
        self._created: list[str] = []
        self._state_by_mission: dict[str, dict] = {}
        self._status_by_mission: dict[str, str] = {}

    def create_mission(self, **kwargs):
        mission_id = f"mission-{len(self._created) + 1}"
        self._created.append(mission_id)
        self._status_by_mission[mission_id] = "created"
        self._state_by_mission[mission_id] = {"findings": [], "validated_findings": []}
        return _FakeMissionHandle(mission_id=mission_id)

    def start_mission(self, mission_id, tenant_id):
        del tenant_id
        self._status_by_mission[mission_id] = "completed"
        self._state_by_mission[mission_id] = {
            "findings": [{"id": "f1"}],
            "validated_findings": [{"id": "vf1"}],
            "vuln_candidates": [{"id": "vc1"}],
        }
        return self._state_by_mission[mission_id]

    def get_status(self, mission_id, tenant_id):
        del tenant_id
        return _FakeMissionStatus(state=self._status_by_mission.get(mission_id, "unknown"))

    def get_state(self, mission_id):
        return dict(self._state_by_mission.get(mission_id, {}))


def _sample_opportunity(*, scope_domains: list[str]) -> Opportunity:
    return Opportunity(
        id="hackerone:test_program",
        name="Test Program",
        organization="Test Org",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://example.com/program",
        scope_url="https://example.com/scope",
        scope_summary="test scope",
        scope_domains=scope_domains,
        max_payout_usd=10000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web"],
        vuln_types=["xss"],
        priority_score=0.8,
        notes="",
    )


def test_opportunity_approve_execute_refresh_flow(tmp_path, monkeypatch):
    state_path = tmp_path / "opportunity_state.json"
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("K1_OPPORTUNITY_ACTION_STATE_PATH", str(state_path))
    monkeypatch.setenv("K1_AUDIT_LOG_PATH", str(audit_path))
    monkeypatch.setenv("K1_OPPORTUNITY_EXECUTION_TARGET_CAP", "3")
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "report_state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))

    runtime = _FakeRuntime()
    events: list[str] = []
    service = OpportunityActionService(
        runtime_provider=lambda: runtime,
        event_emitter=lambda event: events.append(event.event_type),
    )
    service._policy = ScopePolicy()

    tenant_id = str(uuid4())
    actor = "analyst-1"
    opportunity = _sample_opportunity(scope_domains=["api.example.com", "admin.example.com"])

    approved = service.approve(opportunity, tenant_id=tenant_id, actor=actor, reason="meets policy")
    assert approved.status == "approved"
    assert approved.approval_state == "approved"
    assert "opportunity_approved" in events

    executing = service.execute(opportunity, tenant_id=tenant_id, actor=actor, reason="launch")
    assert executing.status == "executing"
    assert len(executing.execution_metadata.get("mission_ids", [])) == 2
    assert "opportunity_execution_started" in events

    service.start_execution_missions(executing)
    refreshed = service.refresh_execution(executing)
    assert refreshed.status == "completed"
    assert int(refreshed.execution_metadata.get("missions_completed", 0)) == 2
    assert int(refreshed.execution_metadata.get("validated_findings_produced", 0)) == 2
    assert "opportunity_execution_completed" in events

    lines = [json.loads(line) for line in Path(audit_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = {row["event_type"] for row in lines}
    assert "opportunity.approved" in event_types
    assert "opportunity.execution.started" in event_types
    assert "opportunity.execution.completed" in event_types


def test_execute_requires_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_OPPORTUNITY_ACTION_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("K1_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "report_state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))

    runtime = _FakeRuntime()
    service = OpportunityActionService(runtime_provider=lambda: runtime, event_emitter=lambda event: None)
    service._policy = ScopePolicy()
    tenant_id = str(uuid4())
    opportunity = _sample_opportunity(scope_domains=["api.example.com"])

    try:
        service.execute(opportunity, tenant_id=tenant_id, actor="analyst-1")
        assert False, "execute should require prior approval"
    except ValueError as exc:
        assert str(exc) == "approval_required"


def test_execute_materializes_wildcard_targets_and_blocks_non_network_targets(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_OPPORTUNITY_ACTION_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("K1_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "report_state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))

    runtime = _FakeRuntime()
    events: list[str] = []
    service = OpportunityActionService(
        runtime_provider=lambda: runtime,
        event_emitter=lambda event: events.append(event.event_type),
    )
    service._policy = ScopePolicy(strict_allowlist=True)
    tenant_id = str(uuid4())
    opportunity = _sample_opportunity(scope_domains=["*.example.com", "ios"])

    service.approve(opportunity, tenant_id=tenant_id, actor="analyst-1", reason="ready")
    result = service.execute(opportunity, tenant_id=tenant_id, actor="analyst-1", reason="launch")

    assert result.status == "executing"
    selected_targets = result.execution_metadata.get("selected_targets", [])
    assert selected_targets == ["example.com"]
    blocked = result.execution_metadata.get("blocked_targets", [])
    assert len(blocked) == 1
    assert blocked[0]["target"] == "ios"
    assert blocked[0]["reason"] == "non_network_target"
    assert "opportunity_execution_started" in events
