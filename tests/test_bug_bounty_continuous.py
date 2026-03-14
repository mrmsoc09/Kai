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


def test_bug_bounty_phase7_prediction_routes(client, monkeypatch):
    now = datetime.now(timezone.utc)
    prediction_id = uuid4()
    target_id = uuid4()
    program_id = uuid4()

    prediction = SimpleNamespace(
        id=prediction_id,
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=uuid4(),
        analyst_queue_item_id=uuid4(),
        predicted_vulnerability_type="sql_injection_candidate",
        confidence_score=0.82,
        novelty_score=0.74,
        duplicate_risk_score=0.21,
        reportability_score=0.79,
        evidence_completeness_score=0.84,
        opportunity_score=86.5,
        recommended_next_workflow="workflow_quick_vuln_sweep",
        recommended_follow_up_action="route_to_manual_validation",
        reasoning_summary="deterministic-phase7",
        supporting_signal_ids_json=[],
        details_json={},
        predicted_at=now,
        created_at=now,
        updated_at=now,
    )
    ranking = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=prediction.workflow_run_id,
        analyst_queue_item_id=prediction.analyst_queue_item_id,
        subject_type="CANDIDATE",
        subject_key=str(prediction.analyst_queue_item_id),
        selection_score=73.1,
        priority_rank=3,
        confidence_score=0.82,
        duplicate_risk_score=0.21,
        evidence_completeness_score=0.84,
        reasoning_summary="deterministic-ranking",
        details_json={},
        scored_at=now,
        created_at=now,
        updated_at=now,
    )
    yield_record = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=prediction.workflow_run_id,
        signal_density_score=0.5,
        novelty_score=0.6,
        coverage_quality_score=0.5,
        candidate_quality_score=0.8,
        duplicate_penalty_score=0.2,
        confidence_score=0.7,
        yield_score=68.0,
        details_json={},
        scored_at=now,
        created_at=now,
        updated_at=now,
    )
    duplicate = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=prediction.workflow_run_id,
        analyst_queue_item_id=prediction.analyst_queue_item_id,
        candidate_key="api.example.com:sql_injection_candidate",
        duplicate_risk_score=0.21,
        risk_band="LOW",
        reasoning_summary="low duplicate risk",
        supporting_signal_ids_json=[],
        details_json={},
        assessed_at=now,
        created_at=now,
        updated_at=now,
    )
    completeness = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=prediction.workflow_run_id,
        analyst_queue_item_id=prediction.analyst_queue_item_id,
        candidate_key="api.example.com:sql_injection_candidate",
        evidence_completeness_score=0.84,
        readiness_state="READY_FOR_REPORT",
        missing_fields_json=[],
        reasoning_summary="evidence complete",
        details_json={},
        assessed_at=now,
        created_at=now,
        updated_at=now,
    )
    recommendation = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=prediction.workflow_run_id,
        analyst_queue_item_id=prediction.analyst_queue_item_id,
        prediction_record_id=prediction.id,
        selection_record_id=ranking.id,
        target_yield_score_id=yield_record.id,
        recommended_workflow="workflow_quick_vuln_sweep",
        recommended_action="route_to_manual_validation",
        action_priority=1,
        recommendation_status="PROPOSED",
        reasoning_summary="phase7 recommendation",
        supporting_record_ids_json=[],
        details_json={},
        recommended_at=now,
        created_at=now,
        updated_at=now,
    )

    class _FakePhase7Service:
        def __init__(self, _db):
            pass

        async def run_prediction_cycle(self, *, program_id, actor, apply_adaptive):
            assert actor
            _ = (program_id, apply_adaptive)
            return {
                "predictions_created": 1,
                "rankings_created": 2,
                "recommendations_created": 2,
                "yield_scores_created": 1,
                "duplicate_records_created": 1,
                "evidence_records_created": 1,
                "adaptive_actions_applied": 1,
            }

        async def list_predictions(self, *, program_id, scope_target_id, limit):
            _ = (program_id, scope_target_id, limit)
            return [prediction]

        async def list_opportunity_rankings(self, *, program_id, subject_type, limit):
            _ = (program_id, subject_type, limit)
            return [ranking]

        async def list_target_yields(self, *, program_id, scope_target_id, limit):
            _ = (program_id, scope_target_id, limit)
            return [yield_record]

        async def list_duplicate_risk(self, *, program_id, risk_band, limit):
            _ = (program_id, risk_band, limit)
            return [duplicate]

        async def list_evidence_completeness(self, *, program_id, readiness_state, limit):
            _ = (program_id, readiness_state, limit)
            return [completeness]

        async def list_recommendations(self, *, program_id, recommendation_status, limit):
            _ = (program_id, recommendation_status, limit)
            return [recommendation]

        async def analyst_decision_support(self, *, program_id, limit):
            _ = (program_id, limit)
            return {
                "generated_at": now.isoformat(),
                "top_predictions": [{"prediction_id": str(prediction.id)}],
                "top_target_yields": [{"yield_record_id": str(yield_record.id)}],
                "top_recommendations": [{"recommendation_id": str(recommendation.id)}],
            }

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "Phase7PredictionService", _FakePhase7Service)
    app.dependency_overrides[get_db] = _override_db
    try:
        run_response = client.post("/api/v1/bug-bounty/phase7/run", json={})
        assert run_response.status_code == 200
        assert run_response.json()["predictions_created"] == 1

        predictions_response = client.get("/api/v1/bug-bounty/phase7/predictions")
        assert predictions_response.status_code == 200
        assert predictions_response.json()[0]["predicted_vulnerability_type"] == "sql_injection_candidate"

        rankings_response = client.get("/api/v1/bug-bounty/phase7/opportunity-rankings")
        assert rankings_response.status_code == 200
        assert rankings_response.json()[0]["subject_type"] == "CANDIDATE"

        yields_response = client.get("/api/v1/bug-bounty/phase7/target-yields")
        assert yields_response.status_code == 200
        assert yields_response.json()[0]["yield_score"] == 68.0

        duplicate_response = client.get("/api/v1/bug-bounty/phase7/duplicate-risk")
        assert duplicate_response.status_code == 200
        assert duplicate_response.json()[0]["risk_band"] == "LOW"

        completeness_response = client.get("/api/v1/bug-bounty/phase7/evidence-completeness")
        assert completeness_response.status_code == 200
        assert completeness_response.json()[0]["readiness_state"] == "READY_FOR_REPORT"

        recommendation_response = client.get("/api/v1/bug-bounty/phase7/recommendations")
        assert recommendation_response.status_code == 200
        assert recommendation_response.json()[0]["recommended_action"] == "route_to_manual_validation"

        support_response = client.get("/api/v1/bug-bounty/phase7/analyst-support")
        assert support_response.status_code == 200
        assert support_response.json()["top_predictions"][0]["prediction_id"] == str(prediction.id)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_bug_bounty_phase9_alert_case_routes(client, monkeypatch):
    now = datetime.now(timezone.utc)
    program_id = uuid4()
    target_id = uuid4()
    alert_id = uuid4()
    case_id = uuid4()

    alert = SimpleNamespace(
        id=alert_id,
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=uuid4(),
        analyst_queue_item_id=uuid4(),
        prediction_record_id=uuid4(),
        recommendation_record_id=uuid4(),
        submission_draft_id=None,
        alert_type="LIKELY_REPORTABLE_FINDING",
        severity="HIGH",
        urgency="HIGH",
        alert_fingerprint="candidate:reportable:1",
        summary="Likely reportable candidate on app.example.com",
        reasoning_summary="reportability=0.93 confidence=0.88",
        supporting_signal_ids_json=[],
        supporting_record_ids_json=["queue-1"],
        status="OPEN",
        occurrence_count=1,
        first_seen_at=now,
        last_seen_at=now,
        acknowledged_at=None,
        acknowledged_by=None,
        resolved_at=None,
        resolved_by=None,
        details_json={},
        created_at=now,
        updated_at=now,
    )
    case = SimpleNamespace(
        id=case_id,
        program_id=program_id,
        scope_target_id=target_id,
        workflow_run_id=uuid4(),
        alert_id=alert_id,
        analyst_queue_item_id=uuid4(),
        prediction_record_id=uuid4(),
        recommendation_record_id=uuid4(),
        submission_draft_id=None,
        title="[HIGH] likely reportable finding",
        summary="Triage this candidate quickly",
        reasoning_summary="signal density elevated",
        priority="HIGH",
        status="new",
        owner=None,
        last_actor="test.operator",
        assigned_at=None,
        last_transition_at=now,
        closed_at=None,
        closure_reason=None,
        evidence_refs_json=[],
        triage_notes_json=[],
        details_json={},
        created_at=now,
        updated_at=now,
    )

    class _FakePhase9Service:
        def __init__(self, _db):
            pass

        async def sync_alerts(self, *, actor, program_id=None, cooldown_minutes=120):
            _ = (actor, program_id, cooldown_minutes)
            return {
                "scanned_sources": 5,
                "created_alerts": 2,
                "updated_alerts": 1,
                "suppressed_alerts": 0,
            }

        async def list_alerts(self, *, program_id=None, status=None, severity=None, limit=500):
            _ = (program_id, status, severity, limit)
            return [alert]

        async def get_alert_case_summary(self, *, program_id=None):
            _ = program_id
            return {
                "unresolved_alert_count": 3,
                "high_severity_alert_count": 2,
                "open_case_count": 4,
                "ready_for_report_case_count": 1,
                "stale_unowned_case_count": 1,
            }

        async def get_alert(self, _alert_id):
            return alert

        async def acknowledge_alert(self, _alert_id, *, actor, note=None):
            _ = (actor, note)
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_at = now
            alert.acknowledged_by = actor
            return alert

        async def resolve_alert(self, _alert_id, *, actor, note=None):
            _ = (actor, note)
            alert.status = "RESOLVED"
            alert.resolved_at = now
            alert.resolved_by = actor
            return alert

        async def create_case_from_alert(self, _alert_id, *, actor, owner=None):
            _ = (actor, owner)
            case.owner = owner
            return case

        async def list_cases(self, *, program_id=None, status=None, priority=None, owner=None, limit=500):
            _ = (program_id, status, priority, owner, limit)
            return [case]

        async def get_case(self, _case_id):
            return case

        async def create_case(self, **kwargs):
            _ = kwargs
            return case

        async def update_case(self, _case_id, **kwargs):
            if kwargs.get("status"):
                case.status = kwargs["status"]
            if kwargs.get("priority"):
                case.priority = kwargs["priority"]
            return case

        async def assign_case(self, _case_id, *, owner, actor):
            _ = actor
            case.owner = owner
            return case

        async def add_case_note(self, _case_id, *, note, actor):
            case.triage_notes_json = [{"note": note, "actor": actor, "at": now.isoformat()}]
            return case

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "Phase9AlertCaseService", _FakePhase9Service)
    app.dependency_overrides[get_db] = _override_db
    try:
        sync_response = client.post("/api/v1/bug-bounty/alerts/sync", json={})
        assert sync_response.status_code == 200
        assert sync_response.json()["created_alerts"] == 2

        list_alerts_response = client.get("/api/v1/bug-bounty/alerts")
        assert list_alerts_response.status_code == 200
        assert list_alerts_response.json()[0]["alert_type"] == "LIKELY_REPORTABLE_FINDING"

        summary_response = client.get("/api/v1/bug-bounty/alerts/summary")
        assert summary_response.status_code == 200
        assert summary_response.json()["open_case_count"] == 4

        alert_detail = client.get(f"/api/v1/bug-bounty/alerts/{alert_id}")
        assert alert_detail.status_code == 200
        assert alert_detail.json()["id"] == str(alert_id)

        ack_response = client.post(
            f"/api/v1/bug-bounty/alerts/{alert_id}/acknowledge",
            json={"actor": "test.operator"},
        )
        assert ack_response.status_code == 200
        assert ack_response.json()["status"] == "ACKNOWLEDGED"

        resolve_response = client.post(
            f"/api/v1/bug-bounty/alerts/{alert_id}/resolve",
            json={"actor": "test.operator"},
        )
        assert resolve_response.status_code == 200
        assert resolve_response.json()["status"] == "RESOLVED"

        case_from_alert = client.post(
            f"/api/v1/bug-bounty/alerts/{alert_id}/case",
            json={"actor": "test.operator", "owner": "analyst-1"},
        )
        assert case_from_alert.status_code == 200
        assert case_from_alert.json()["owner"] == "analyst-1"

        list_cases_response = client.get("/api/v1/bug-bounty/cases")
        assert list_cases_response.status_code == 200
        assert list_cases_response.json()[0]["title"] == "[HIGH] likely reportable finding"

        case_detail = client.get(f"/api/v1/bug-bounty/cases/{case_id}")
        assert case_detail.status_code == 200
        assert case_detail.json()["id"] == str(case_id)

        create_case_response = client.post(
            "/api/v1/bug-bounty/cases",
            json={
                "program_id": str(program_id),
                "title": "manual case",
                "summary": "manual summary",
            },
        )
        assert create_case_response.status_code == 200
        assert create_case_response.json()["id"] == str(case_id)

        update_case_response = client.patch(
            f"/api/v1/bug-bounty/cases/{case_id}",
            json={"status": "triaging"},
        )
        assert update_case_response.status_code == 200
        assert update_case_response.json()["status"] == "triaging"

        assign_case_response = client.post(
            f"/api/v1/bug-bounty/cases/{case_id}/assign",
            json={"owner": "analyst-2"},
        )
        assert assign_case_response.status_code == 200
        assert assign_case_response.json()["owner"] == "analyst-2"

        note_response = client.post(
            f"/api/v1/bug-bounty/cases/{case_id}/notes",
            json={"note": "triage note"},
        )
        assert note_response.status_code == 200
        assert note_response.json()["triage_notes_json"][0]["note"] == "triage note"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_bug_bounty_phase10_retrospective_routes(client, monkeypatch):
    now = datetime.now(timezone.utc)
    program_id = uuid4()
    target_id = uuid4()

    workflow_row = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        workflow_template="workflow_quick_vuln_sweep",
        window_start=now,
        window_end=now,
        signals_generated=10,
        candidates_produced=5,
        cases_created=3,
        reportable_outcomes=2,
        duplicate_outcomes=0,
        dismissed_outcomes=1,
        workflow_signal_value=74.0,
        workflow_reportability_rate=0.66,
        workflow_noise_rate=0.33,
        details_json={},
        computed_at=now,
        created_at=now,
        updated_at=now,
    )
    target_row = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        scope_target_id=target_id,
        window_start=now,
        window_end=now,
        signal_count=10,
        candidate_count=5,
        case_count=3,
        reportable_count=2,
        duplicate_count=0,
        dismissed_count=1,
        target_signal_rate=0.2,
        target_duplicate_rate=0.0,
        target_reportability_rate=0.66,
        target_yield_score=78.0,
        details_json={},
        computed_at=now,
        created_at=now,
        updated_at=now,
    )
    recommendation_row = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        recommendation_record_id=uuid4(),
        scope_target_id=target_id,
        workflow_run_id=uuid4(),
        analyst_case_id=uuid4(),
        outcome_status="SUCCEEDED",
        success_score=1.0,
        reasoning_summary="used and successful",
        details_json={},
        decided_at=now,
        created_at=now,
        updated_at=now,
    )
    alert_row = SimpleNamespace(
        id=uuid4(),
        program_id=program_id,
        alert_id=uuid4(),
        scope_target_id=target_id,
        analyst_case_id=uuid4(),
        outcome_status="RESOLVED_ACTIONABLE",
        acknowledgement_latency_seconds=120,
        led_to_case=True,
        led_to_reportable=True,
        reasoning_summary="actionable signal",
        details_json={},
        evaluated_at=now,
        created_at=now,
        updated_at=now,
    )

    class _FakePhase10Service:
        def __init__(self, _db):
            pass

        async def run_retrospective(self, *, actor, program_id, window_days):
            assert actor
            _ = (program_id, window_days)
            return {
                "feedback_signals_recorded": 4,
                "decision_outcomes_recorded": 3,
                "workflow_performance_records_created": 1,
                "target_performance_records_created": 1,
                "recommendation_outcomes_recorded": 1,
                "alert_outcomes_recorded": 1,
            }

        async def summary(self, *, program_id, window_days):
            _ = (program_id, window_days)
            return {
                "generated_at": now.isoformat(),
                "window_days": 30,
                "top_programs": [{"program_id": str(program_id), "avg_target_yield_score": 78.0}],
                "top_targets": [{"scope_target_id": str(target_id), "target_yield_score": 78.0}],
                "workflow_value_leaders": [{"workflow_template": "workflow_quick_vuln_sweep"}],
                "alert_noise_summary": {"noise_rate": 0.1},
                "recommendation_success_summary": {"weighted_success_rate": 0.9},
            }

        async def list_workflow_performance(self, *, program_id, limit):
            _ = (program_id, limit)
            return [workflow_row]

        async def list_target_performance(self, *, program_id, scope_target_id, limit):
            _ = (program_id, scope_target_id, limit)
            return [target_row]

        async def list_recommendation_outcomes(self, *, program_id, outcome_status, limit):
            _ = (program_id, outcome_status, limit)
            return [recommendation_row]

        async def list_alert_outcomes(self, *, program_id, outcome_status, limit):
            _ = (program_id, outcome_status, limit)
            return [alert_row]

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "Phase10RetrospectiveService", _FakePhase10Service)
    app.dependency_overrides[get_db] = _override_db
    try:
        run_response = client.post("/api/v1/bug-bounty/retrospective/run", json={})
        assert run_response.status_code == 200
        assert run_response.json()["feedback_signals_recorded"] == 4

        summary_response = client.get("/api/v1/bug-bounty/retrospective/summary")
        assert summary_response.status_code == 200
        assert summary_response.json()["window_days"] == 30

        workflows_response = client.get("/api/v1/bug-bounty/retrospective/workflows")
        assert workflows_response.status_code == 200
        assert workflows_response.json()[0]["workflow_template"] == "workflow_quick_vuln_sweep"

        targets_response = client.get("/api/v1/bug-bounty/retrospective/targets")
        assert targets_response.status_code == 200
        assert targets_response.json()[0]["target_yield_score"] == 78.0

        recommendations_response = client.get("/api/v1/bug-bounty/retrospective/recommendations")
        assert recommendations_response.status_code == 200
        assert recommendations_response.json()[0]["outcome_status"] == "SUCCEEDED"

        alerts_response = client.get("/api/v1/bug-bounty/retrospective/alerts")
        assert alerts_response.status_code == 200
        assert alerts_response.json()[0]["outcome_status"] == "RESOLVED_ACTIONABLE"
    finally:
        app.dependency_overrides.pop(get_db, None)
