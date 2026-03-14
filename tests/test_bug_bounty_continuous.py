from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import apps.backend.src.routers.bug_bounty as bug_bounty_router
from apps.backend.src.core.bug_bounty_hunting_service import BugBountyHuntingService
from apps.backend.src.core.hil_db import get_db
from apps.backend.src.main import app


def _program_obj():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        program_key="example-program",
        name="Example Program",
        platform="hackerone",
        handle="example",
        status="ACTIVE",
        policy_url="https://example.com/policy",
        created_by="test",
        config_json={},
        created_at=now,
        updated_at=now,
    )


def _target_obj(program_id):
    return SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        target="app.example.com",
        target_type="domain",
        is_in_scope=True,
        monitoring_enabled=True,
        monitoring_priority_tier=2,
        monitoring_status="ACTIVE",
        monitoring_source="import:manual",
        monitoring_notes=None,
        safe_mode_required=True,
        last_checked_at=None,
        last_success_at=None,
        last_failure_at=None,
        next_scheduled_run_at=None,
        details_json={},
    )


def _schedule_obj(program_id, scope_target_id):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        scope_target_id=scope_target_id,
        workflow_template="workflow_quick_vuln_sweep",
        schedule_type="interval",
        interval_minutes=60,
        cron_expr=None,
        status="ACTIVE",
        safe_mode=True,
        dry_run=False,
        priority_tier=2,
        max_concurrency=1,
        cooldown_minutes=60,
        failure_backoff_minutes=240,
        failure_pause_threshold=3,
        consecutive_failures=0,
        last_run_started_at=None,
        last_run_finished_at=None,
        last_run_status=None,
        last_failure_reason=None,
        next_scheduled_run_at=now,
        paused_at=None,
        paused_reason=None,
        created_by="test",
        updated_by="test",
        config_json={},
        created_at=now,
        updated_at=now,
    )


def test_bug_bounty_program_import_and_list_routes(client, monkeypatch):
    program = _program_obj()
    target = _target_obj(program.id)

    class _FakeService:
        def __init__(self, _db):
            pass

        async def list_programs(self):
            return [program]

        async def import_program_opportunity(self, _payload, *, actor):
            assert actor == "operator.bugbounty.import"
            return program

        async def list_monitored_targets(self, _program_id):
            return [target]

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "BugBountyHuntingService", _FakeService)
    app.dependency_overrides[get_db] = _override_db
    try:
        list_response = client.get("/api/v1/bug-bounty/programs")
        assert list_response.status_code == 200
        assert list_response.json()[0]["name"] == "Example Program"

        import_response = client.post(
            "/api/v1/bug-bounty/programs/import",
            json={
                "source": "manual",
                "platform": "hackerone",
                "name": "Example Program",
                "program_key": "example-program",
                "in_scope_assets": [{"target": "app.example.com", "target_type": "domain"}],
            },
        )
        assert import_response.status_code == 200
        assert import_response.json()["program_key"] == "example-program"

        targets_response = client.get(f"/api/v1/bug-bounty/programs/{program.id}/targets")
        assert targets_response.status_code == 200
        assert targets_response.json()[0]["target"] == "app.example.com"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_bug_bounty_schedule_routes(client, monkeypatch):
    program = _program_obj()
    target = _target_obj(program.id)
    schedule = _schedule_obj(program.id, target.id)
    readiness_record_id = uuid4()

    class _FakeService:
        def __init__(self, _db):
            pass

        async def create_schedule(self, _payload):
            return schedule

        async def list_schedules(self, *, program_id=None, status=None):
            assert program_id is None
            assert status is None
            return [schedule]

        async def get_scheduler_status(self, *, program_id=None):
            assert program_id is None
            return SimpleNamespace(
                total_schedules=1,
                active_schedules=1,
                paused_schedules=0,
                disabled_schedules=0,
                error_schedules=0,
                due_schedules=1,
                blocked_readiness_last_24h=0,
                ready_readiness_last_24h=3,
            )

        async def get_schedule(self, _schedule_id):
            return schedule

        async def get_schedule_for_target(self, *, program_id, scope_target_id, workflow_template):
            if (
                program_id == schedule.program_id
                and scope_target_id == schedule.scope_target_id
                and workflow_template == schedule.workflow_template
            ):
                return schedule
            return None

        async def evaluate_readiness(self, _schedule, *, trigger_source, persist):
            return SimpleNamespace(
                decision_status="READY",
                reason="ok",
                details={"trigger_source": trigger_source, "persist": persist},
                record_id=readiness_record_id,
            )

        async def trigger_schedule(self, _schedule_id, *, actor, force, trigger_source):
            assert actor
            return SimpleNamespace(
                schedule_id=schedule.id,
                decision_status="READY",
                reason="workflow launched",
                readiness_record_id=readiness_record_id,
                campaign_id=uuid4(),
                workflow_run_id=uuid4(),
                run_id="bb-test-run",
                next_scheduled_run_at=schedule.next_scheduled_run_at,
                details={"trigger_source": trigger_source, "force": force},
            )

        async def run_due_schedules(self, *, actor, limit, program_id):
            assert actor
            assert limit == 25
            assert program_id is None
            return [
                SimpleNamespace(
                    schedule_id=schedule.id,
                    decision_status="READY",
                    reason="workflow launched",
                    readiness_record_id=readiness_record_id,
                    campaign_id=uuid4(),
                    workflow_run_id=uuid4(),
                    run_id="bb-due-run",
                    next_scheduled_run_at=schedule.next_scheduled_run_at,
                    details={},
                )
            ]

        async def dispatch_due_schedules(self, *, actor, limit, program_id):
            assert actor
            assert limit == 25
            assert program_id is None
            return [
                SimpleNamespace(
                    schedule_id=schedule.id,
                    worker_task_id="task-1",
                    worker_role="recon_worker",
                    decision_status="DISPATCHED",
                    reason="queued for worker execution",
                )
            ]

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "BugBountyHuntingService", _FakeService)
    app.dependency_overrides[get_db] = _override_db
    try:
        create_response = client.post(
            "/api/v1/bug-bounty/schedules",
            json={
                "program_id": str(program.id),
                "scope_target_id": str(target.id),
                "workflow_template": "workflow_quick_vuln_sweep",
                "interval_minutes": 60,
            },
        )
        assert create_response.status_code == 200
        assert create_response.json()["workflow_template"] == "workflow_quick_vuln_sweep"

        list_response = client.get("/api/v1/bug-bounty/schedules")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        status_response = client.get("/api/v1/bug-bounty/schedules/status")
        assert status_response.status_code == 200
        assert status_response.json()["active_schedules"] == 1

        readiness_response = client.get(f"/api/v1/bug-bounty/schedules/{schedule.id}/readiness")
        assert readiness_response.status_code == 200
        assert readiness_response.json()["decision_status"] == "READY"

        ad_hoc_readiness = client.get(
            "/api/v1/bug-bounty/readiness",
            params={
                "program_id": str(program.id),
                "scope_target_id": str(target.id),
                "workflow_template": "workflow_quick_vuln_sweep",
            },
        )
        assert ad_hoc_readiness.status_code == 200
        assert ad_hoc_readiness.json()["decision_status"] == "READY"

        trigger_response = client.post(
            f"/api/v1/bug-bounty/schedules/{schedule.id}/trigger",
            json={"actor": "test.trigger", "force": False},
        )
        assert trigger_response.status_code == 200
        assert trigger_response.json()["run_id"] == "bb-test-run"

        due_response = client.post("/api/v1/bug-bounty/schedules/run-due", json={"limit": 25})
        assert due_response.status_code == 200
        assert due_response.json()[0]["run_id"] == "bb-due-run"

        dispatch_response = client.post("/api/v1/bug-bounty/schedules/dispatch-due", json={"limit": 25})
        assert dispatch_response.status_code == 200
        assert dispatch_response.json()[0]["decision_status"] == "DISPATCHED"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_bug_bounty_candidate_and_draft_routes(client, monkeypatch):
    now = datetime.now(timezone.utc)
    queue_item = SimpleNamespace(
        id=uuid4(),
        program_id=uuid4(),
        scope_target_id=uuid4(),
        workflow_run_id=uuid4(),
        workflow_finding_id=uuid4(),
        finding_id=None,
        workflow_template="workflow_quick_vuln_sweep",
        finding_type="workflow_candidate",
        vulnerability_type="sql_injection_candidate",
        affected_asset="api.example.com",
        affected_endpoint="/v1/users",
        parameter="id",
        evidence_summary="output/raw/x.json",
        confidence_score=0.9,
        severity_hint="high",
        novelty_score=1.0,
        reportability_score=0.88,
        duplicate_risk_hint="LOW",
        policy_fit_status="IN_SCOPE",
        status="ready_for_report",
        artifact_ref="output/raw/x.json",
        assigned_to=None,
        last_transition_at=now,
        details_json={},
        created_at=now,
        updated_at=now,
    )
    draft_response = SimpleNamespace(
        queue_item_id=queue_item.id,
        submission_draft_id=uuid4(),
        artifact_id=uuid4(),
        draft_path="output/reports/bug_bounty/candidate.md",
        status="ready_for_report",
    )
    delta = SimpleNamespace(
        id=uuid4(),
        schedule_job_id=uuid4(),
        program_id=uuid4(),
        scope_target_id=uuid4(),
        workflow_run_id=uuid4(),
        previous_workflow_run_id=None,
        delta_type="subdomain",
        delta_key="new.example.com",
        change_type="NEW",
        severity_hint=None,
        details_json={},
        created_at=now,
    )

    class _FakeService:
        def __init__(self, _db):
            pass

        async def list_candidate_queue(self, *, program_id=None, status=None, limit=500):
            assert limit == 500
            return [queue_item]

        async def list_deltas(self, *, program_id=None, scope_target_id=None, limit=500):
            assert limit == 500
            return [delta]

        async def update_candidate_queue_item(self, _queue_item_id, _body):
            queue_item.status = "triaged"
            queue_item.assigned_to = "analyst-1"
            return queue_item

        async def generate_report_draft(self, _queue_item_id, *, actor, analyst_notes):
            assert actor
            _ = analyst_notes
            return draft_response

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "BugBountyHuntingService", _FakeService)
    app.dependency_overrides[get_db] = _override_db
    try:
        queue_response = client.get("/api/v1/bug-bounty/candidates")
        assert queue_response.status_code == 200
        assert queue_response.json()[0]["affected_asset"] == "api.example.com"

        queue_update = client.patch(
            f"/api/v1/bug-bounty/candidates/{queue_item.id}",
            json={
                "status": "triaged",
                "assigned_to": "analyst-1",
                "analyst_notes": "needs follow-up",
            },
        )
        assert queue_update.status_code == 200
        assert queue_update.json()["status"] == "triaged"

        delta_response = client.get("/api/v1/bug-bounty/deltas")
        assert delta_response.status_code == 200
        assert delta_response.json()[0]["delta_key"] == "new.example.com"

        draft_gen_response = client.post(
            f"/api/v1/bug-bounty/candidates/{queue_item.id}/report-draft",
            json={"actor": "test.reviewer", "analyst_notes": "validated"},
        )
        assert draft_gen_response.status_code == 200
        assert draft_gen_response.json()["draft_path"].endswith(".md")
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_bug_bounty_service_helper_methods():
    svc = BugBountyHuntingService(db=object())  # type: ignore[arg-type]
    assert svc._severity_weight("critical") > svc._severity_weight("low")  # noqa: SLF001

    schedule = SimpleNamespace(schedule_type="interval", interval_minutes=15, cron_expr=None)
    next_run = svc._next_schedule_at(schedule, now=datetime.now(timezone.utc))  # noqa: SLF001
    assert next_run > datetime.now(timezone.utc)


def test_bug_bounty_phase6_inference_routes(client, monkeypatch):
    now = datetime.now(timezone.utc)
    signal = SimpleNamespace(
        id=uuid4(),
        program_id=uuid4(),
        scope_target_id=uuid4(),
        workflow_run_id=uuid4(),
        source="workflow_delta",
        source_record_id="1",
        signal_type="delta_endpoint",
        signal_key="NEW:/api/x",
        confidence_score=0.7,
        severity_hint="medium",
        evidence_refs_json=["output/normalized/a.jsonl"],
        correlation_refs_json=[],
        details_json={},
        observed_at=now,
        created_at=now,
        updated_at=now,
    )
    score = SimpleNamespace(
        id=uuid4(),
        program_id=signal.program_id,
        scope_target_id=signal.scope_target_id,
        workflow_run_id=signal.workflow_run_id,
        recommended_workflow="workflow_quick_vuln_sweep",
        next_best_action="schedule_vuln_validation",
        opportunity_score=88.1,
        target_priority_score=82.0,
        reasoning_summary="deterministic score",
        supporting_evidence_json=[str(signal.id)],
        details_json={},
        inferred_at=now,
        created_at=now,
        updated_at=now,
    )
    swarm = SimpleNamespace(
        id=uuid4(),
        program_id=signal.program_id,
        scope_target_id=signal.scope_target_id,
        workflow_run_id=signal.workflow_run_id,
        opportunity_inference_id=score.id,
        agent_role="recon_planning_agent",
        confidence_score=0.8,
        output_json={"recommended_workflow": "workflow_quick_vuln_sweep"},
        details_json={},
        reasoned_at=now,
        created_at=now,
        updated_at=now,
    )
    action = SimpleNamespace(
        id=uuid4(),
        program_id=signal.program_id,
        scope_target_id=signal.scope_target_id,
        schedule_job_id=uuid4(),
        opportunity_inference_id=score.id,
        action_type="schedule_adjustment",
        action_status="APPLIED",
        reason="adaptive prioritization applied",
        details_json={},
        executed_at=now,
        created_at=now,
        updated_at=now,
    )

    class _FakeInferenceService:
        def __init__(self, _db):
            pass

        async def run_inference(self, *, program_id, actor, apply_adaptive):
            assert actor
            _ = program_id
            _ = apply_adaptive
            return {
                "created_signals": 4,
                "considered_records": 5,
                "scores_created": 1,
                "swarm_records_created": 7,
                "adaptive_actions_applied": 1,
            }

        async def list_signals(self, *, program_id, scope_target_id, signal_type, limit):
            _ = (program_id, scope_target_id, signal_type, limit)
            return [signal]

        async def list_opportunity_scores(self, *, program_id, scope_target_id, limit):
            _ = (program_id, scope_target_id, limit)
            return [score]

        async def list_swarm_outputs(self, *, program_id, scope_target_id, agent_role, limit):
            _ = (program_id, scope_target_id, agent_role, limit)
            return [swarm]

        async def list_adaptive_actions(self, *, program_id, action_status, limit):
            _ = (program_id, action_status, limit)
            return [action]

        async def analyst_briefing(self, *, program_id, limit):
            _ = (program_id, limit)
            return {
                "generated_at": now.isoformat(),
                "top_targets": [{"scope_target_id": str(signal.scope_target_id)}],
                "top_candidates": [{"queue_item_id": str(uuid4())}],
                "adaptive_actions": [{"action_status": "APPLIED"}],
            }

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "ReconInferenceService", _FakeInferenceService)
    app.dependency_overrides[get_db] = _override_db
    try:
        run_response = client.post("/api/v1/bug-bounty/inference/run", json={})
        assert run_response.status_code == 200
        assert run_response.json()["scores_created"] == 1

        signals_response = client.get("/api/v1/bug-bounty/signals")
        assert signals_response.status_code == 200
        assert signals_response.json()[0]["signal_type"] == "delta_endpoint"

        scores_response = client.get("/api/v1/bug-bounty/opportunity-scores")
        assert scores_response.status_code == 200
        assert scores_response.json()[0]["opportunity_score"] == 88.1

        swarm_response = client.get("/api/v1/bug-bounty/swarm-outputs")
        assert swarm_response.status_code == 200
        assert swarm_response.json()[0]["agent_role"] == "recon_planning_agent"

        actions_response = client.get("/api/v1/bug-bounty/adaptive-actions")
        assert actions_response.status_code == 200
        assert actions_response.json()[0]["action_status"] == "APPLIED"

        briefing_response = client.get("/api/v1/bug-bounty/analyst-briefing")
        assert briefing_response.status_code == 200
        assert briefing_response.json()["adaptive_actions"][0]["action_status"] == "APPLIED"
    finally:
        app.dependency_overrides.pop(get_db, None)
