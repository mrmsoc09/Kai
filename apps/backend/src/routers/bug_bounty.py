from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import (
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    User,
    get_current_user,
    require_roles,
)
from ..core.bug_bounty_hunting_service import BugBountyHuntingService
from ..core.hil_db import get_db
from ..core.phase7_prediction_service import Phase7PredictionService
from ..core.phase9_alert_case_service import Phase9AlertCaseService
from ..core.phase10_retrospective_service import Phase10RetrospectiveService
from ..core.phase10_5_agent_framework_service import Phase10_5AgentFrameworkService
from ..core.recon_inference_service import ReconInferenceService
from ..schemas.bug_bounty_hunt import (
    AdaptiveScheduleActionRead,
    AgentEvaluateRequest,
    AgentEvaluationRead,
    AgentExecutionRead,
    AgentRegistryRead,
    AgentRegistrySyncResponse,
    AgentRunRequest,
    AlertActionRequest,
    AlertCaseCreateRequest,
    AlertSyncRequest,
    AlertSyncResponse,
    AnalystCaseRead,
    AnalystQueueItemRead,
    AnalystBriefingResponse,
    CaseAssignRequest,
    CaseCreateRequest,
    CaseNoteRequest,
    CaseUpdateRequest,
    CandidateQueueUpdateRequest,
    NotificationAlertRead,
    GenerateReportDraftRequest,
    GenerateReportDraftResponse,
    HuntScheduleCreateRequest,
    HuntScheduleRead,
    HuntScheduleUpdateRequest,
    MonitoredTargetRead,
    MonitoredTargetUpdateRequest,
    OpportunityInferenceRead,
    OpportunitySelectionRead,
    Phase7AnalystSupportResponse,
    Phase7RunRequest,
    Phase7RunResponse,
    RetrospectiveRunRequest,
    RetrospectiveRunResponse,
    RetrospectiveSummaryResponse,
    ProgramOpportunityImportRequest,
    ProgramOpportunityRead,
    ReadinessCheckResponse,
    ScheduleDispatchResponse,
    ScheduleTriggerResponse,
    SchedulerStatusResponse,
    SignalIntelligenceRead,
    SwarmReasoningRead,
    TargetYieldScoreRead,
    WorkflowPerformanceRead,
    TargetPerformanceRead,
    RecommendationOutcomeRead,
    AlertOutcomeRead,
    DuplicateRiskRead,
    EvidenceCompletenessRead,
    VulnerabilityPredictionRead,
    WorkflowRecommendationRead,
    WorkflowDeltaRead,
    InferenceRunRequest,
    InferenceRunResponse,
)


router = APIRouter(
    prefix="/api/v1/bug-bounty",
    tags=["bug-bounty"],
    dependencies=[Depends(get_current_user)],
)


class RunDueSchedulesRequest(BaseModel):
    actor: str = Field(default="operator.scheduler", min_length=1, max_length=255)
    limit: int = Field(default=25, ge=1, le=200)
    program_id: UUID | None = None


class TriggerScheduleRequest(BaseModel):
    actor: str = Field(default="operator.scheduler", min_length=1, max_length=255)
    force: bool = False


def _value_error_to_http(exc: ValueError) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    if "not found" in lowered:
        return HTTPException(status_code=404, detail=message)
    if "unknown" in lowered or "required" in lowered or "invalid" in lowered:
        return HTTPException(status_code=422, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/programs", response_model=list[ProgramOpportunityRead])
async def list_programs(db: AsyncSession = Depends(get_db)):
    return await BugBountyHuntingService(db).list_programs()


@router.post("/programs/import", response_model=ProgramOpportunityRead)
async def import_program_opportunity(
    body: ProgramOpportunityImportRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    svc = BugBountyHuntingService(db)
    try:
        return await svc.import_program_opportunity(body, actor="operator.bugbounty.import")
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/programs/{program_id}/targets", response_model=list[MonitoredTargetRead])
async def list_program_targets(program_id: UUID, db: AsyncSession = Depends(get_db)):
    return await BugBountyHuntingService(db).list_monitored_targets(program_id)


@router.patch("/targets/{scope_target_id}", response_model=MonitoredTargetRead)
async def update_monitored_target(
    scope_target_id: UUID,
    body: MonitoredTargetUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    svc = BugBountyHuntingService(db)
    try:
        return await svc.update_monitored_target(
            scope_target_id,
            body,
            actor="operator.bugbounty.target.update",
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/schedules", response_model=HuntScheduleRead)
async def create_schedule(
    body: HuntScheduleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    svc = BugBountyHuntingService(db)
    try:
        return await svc.create_schedule(body)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/schedules", response_model=list[HuntScheduleRead])
async def list_schedules(
    program_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await BugBountyHuntingService(db).list_schedules(program_id=program_id, status=status)


@router.get("/schedules/status", response_model=SchedulerStatusResponse)
async def scheduler_status(
    program_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await BugBountyHuntingService(db).get_scheduler_status(program_id=program_id)


@router.patch("/schedules/{schedule_id}", response_model=HuntScheduleRead)
async def update_schedule(
    schedule_id: UUID,
    body: HuntScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    svc = BugBountyHuntingService(db)
    try:
        return await svc.update_schedule(schedule_id, body)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/schedules/{schedule_id}/readiness", response_model=ReadinessCheckResponse)
async def check_schedule_readiness(
    schedule_id: UUID,
    persist: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    svc = BugBountyHuntingService(db)
    schedule = await svc.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return await svc.evaluate_readiness(schedule, trigger_source="api.readiness", persist=persist)


@router.get("/readiness", response_model=ReadinessCheckResponse)
async def check_program_target_readiness(
    program_id: UUID,
    scope_target_id: UUID,
    workflow_template: str,
    safe_mode: bool = Query(default=True),
    persist: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    svc = BugBountyHuntingService(db)
    schedule = await svc.get_schedule_for_target(
        program_id=program_id,
        scope_target_id=scope_target_id,
        workflow_template=workflow_template,
    )
    if schedule is None:
        schedule = SimpleNamespace(
            id=uuid4(),
            program_id=program_id,
            scope_target_id=scope_target_id,
            workflow_template=workflow_template,
            status="ACTIVE",
            schedule_type="interval",
            interval_minutes=60,
            cron_expr=None,
            safe_mode=safe_mode,
            dry_run=False,
            max_concurrency=1,
            cooldown_minutes=0,
            failure_backoff_minutes=240,
            failure_pause_threshold=3,
            consecutive_failures=0,
            last_run_finished_at=None,
            next_scheduled_run_at=None,
            config_json={},
        )
    return await svc.evaluate_readiness(
        schedule,
        trigger_source="api.readiness.ad_hoc",
        persist=persist,
    )


@router.post("/schedules/{schedule_id}/trigger", response_model=ScheduleTriggerResponse)
async def trigger_schedule(
    schedule_id: UUID,
    body: TriggerScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    svc = BugBountyHuntingService(db)
    try:
        return await svc.trigger_schedule(
            schedule_id,
            actor=body.actor,
            force=body.force,
            trigger_source="api.trigger",
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/schedules/run-due", response_model=list[ScheduleTriggerResponse])
async def run_due_schedules(
    body: RunDueSchedulesRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    return await BugBountyHuntingService(db).run_due_schedules(
        actor=body.actor,
        limit=body.limit,
        program_id=body.program_id,
    )


@router.post("/schedules/dispatch-due", response_model=list[ScheduleDispatchResponse])
async def dispatch_due_schedules(
    body: RunDueSchedulesRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    return await BugBountyHuntingService(db).dispatch_due_schedules(
        actor=body.actor,
        limit=body.limit,
        program_id=body.program_id,
    )


@router.get("/readiness-records", response_model=list[ReadinessCheckResponse])
async def list_readiness_records(
    program_id: UUID | None = Query(default=None),
    decision_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    records = await BugBountyHuntingService(db).list_readiness_records(
        program_id=program_id,
        decision_status=decision_status,
        limit=limit,
    )
    return [
        ReadinessCheckResponse(
            decision_status=record.decision_status,
            reason=record.reason,
            details=record.details_json if isinstance(record.details_json, dict) else {},
            record_id=record.id,
        )
        for record in records
    ]


@router.post("/inference/run", response_model=InferenceRunResponse)
async def run_phase6_inference(
    body: InferenceRunRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    return await ReconInferenceService(db).run_inference(
        program_id=body.program_id,
        actor=body.actor,
        apply_adaptive=body.apply_adaptive,
    )


@router.get("/signals", response_model=list[SignalIntelligenceRead])
async def list_signals(
    program_id: UUID | None = Query(default=None),
    scope_target_id: UUID | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await ReconInferenceService(db).list_signals(
        program_id=program_id,
        scope_target_id=scope_target_id,
        signal_type=signal_type,
        limit=limit,
    )


@router.get("/opportunity-scores", response_model=list[OpportunityInferenceRead])
async def list_opportunity_scores(
    program_id: UUID | None = Query(default=None),
    scope_target_id: UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await ReconInferenceService(db).list_opportunity_scores(
        program_id=program_id,
        scope_target_id=scope_target_id,
        limit=limit,
    )


@router.get("/swarm-outputs", response_model=list[SwarmReasoningRead])
async def list_swarm_outputs(
    program_id: UUID | None = Query(default=None),
    scope_target_id: UUID | None = Query(default=None),
    agent_role: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await ReconInferenceService(db).list_swarm_outputs(
        program_id=program_id,
        scope_target_id=scope_target_id,
        agent_role=agent_role,
        limit=limit,
    )


@router.get("/adaptive-actions", response_model=list[AdaptiveScheduleActionRead])
async def list_adaptive_actions(
    program_id: UUID | None = Query(default=None),
    action_status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await ReconInferenceService(db).list_adaptive_actions(
        program_id=program_id,
        action_status=action_status,
        limit=limit,
    )


@router.get("/analyst-briefing", response_model=AnalystBriefingResponse)
async def analyst_briefing(
    program_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await ReconInferenceService(db).analyst_briefing(
        program_id=program_id,
        limit=limit,
    )


@router.post("/phase7/run", response_model=Phase7RunResponse)
async def run_phase7_prediction(
    body: Phase7RunRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    return await Phase7PredictionService(db).run_prediction_cycle(
        program_id=body.program_id,
        actor=body.actor,
        apply_adaptive=body.apply_adaptive,
    )


@router.get("/phase7/predictions", response_model=list[VulnerabilityPredictionRead])
async def list_phase7_predictions(
    program_id: UUID | None = Query(default=None),
    scope_target_id: UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase7PredictionService(db).list_predictions(
        program_id=program_id,
        scope_target_id=scope_target_id,
        limit=limit,
    )


@router.get("/phase7/opportunity-rankings", response_model=list[OpportunitySelectionRead])
async def list_phase7_opportunity_rankings(
    program_id: UUID | None = Query(default=None),
    subject_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase7PredictionService(db).list_opportunity_rankings(
        program_id=program_id,
        subject_type=subject_type,
        limit=limit,
    )


@router.get("/phase7/target-yields", response_model=list[TargetYieldScoreRead])
async def list_phase7_target_yields(
    program_id: UUID | None = Query(default=None),
    scope_target_id: UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase7PredictionService(db).list_target_yields(
        program_id=program_id,
        scope_target_id=scope_target_id,
        limit=limit,
    )


@router.get("/phase7/duplicate-risk", response_model=list[DuplicateRiskRead])
async def list_phase7_duplicate_risk(
    program_id: UUID | None = Query(default=None),
    risk_band: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase7PredictionService(db).list_duplicate_risk(
        program_id=program_id,
        risk_band=risk_band,
        limit=limit,
    )


@router.get(
    "/phase7/evidence-completeness",
    response_model=list[EvidenceCompletenessRead],
)
async def list_phase7_evidence_completeness(
    program_id: UUID | None = Query(default=None),
    readiness_state: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase7PredictionService(db).list_evidence_completeness(
        program_id=program_id,
        readiness_state=readiness_state,
        limit=limit,
    )


@router.get("/phase7/recommendations", response_model=list[WorkflowRecommendationRead])
async def list_phase7_recommendations(
    program_id: UUID | None = Query(default=None),
    recommendation_status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase7PredictionService(db).list_recommendations(
        program_id=program_id,
        recommendation_status=recommendation_status,
        limit=limit,
    )


@router.get("/phase7/analyst-support", response_model=Phase7AnalystSupportResponse)
async def phase7_analyst_support(
    program_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await Phase7PredictionService(db).analyst_decision_support(
        program_id=program_id,
        limit=limit,
    )


@router.post("/retrospective/run", response_model=RetrospectiveRunResponse)
async def run_phase10_retrospective(
    body: RetrospectiveRunRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    return await Phase10RetrospectiveService(db).run_retrospective(
        actor=body.actor,
        program_id=body.program_id,
        window_days=body.window_days,
    )


@router.get("/retrospective/summary", response_model=RetrospectiveSummaryResponse)
async def phase10_retrospective_summary(
    program_id: UUID | None = Query(default=None),
    window_days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10RetrospectiveService(db).summary(
        program_id=program_id,
        window_days=window_days,
    )


@router.get("/retrospective/workflows", response_model=list[WorkflowPerformanceRead])
async def list_phase10_workflow_performance(
    program_id: UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10RetrospectiveService(db).list_workflow_performance(
        program_id=program_id,
        limit=limit,
    )


@router.get("/retrospective/targets", response_model=list[TargetPerformanceRead])
async def list_phase10_target_performance(
    program_id: UUID | None = Query(default=None),
    scope_target_id: UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10RetrospectiveService(db).list_target_performance(
        program_id=program_id,
        scope_target_id=scope_target_id,
        limit=limit,
    )


@router.get(
    "/retrospective/recommendations",
    response_model=list[RecommendationOutcomeRead],
)
async def list_phase10_recommendation_outcomes(
    program_id: UUID | None = Query(default=None),
    outcome_status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10RetrospectiveService(db).list_recommendation_outcomes(
        program_id=program_id,
        outcome_status=outcome_status,
        limit=limit,
    )


@router.get("/retrospective/alerts", response_model=list[AlertOutcomeRead])
async def list_phase10_alert_outcomes(
    program_id: UUID | None = Query(default=None),
    outcome_status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10RetrospectiveService(db).list_alert_outcomes(
        program_id=program_id,
        outcome_status=outcome_status,
        limit=limit,
    )


@router.post("/agents/sync", response_model=AgentRegistrySyncResponse)
async def sync_phase10_5_agent_registry(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    return await Phase10_5AgentFrameworkService(db).sync_registry(
        actor="operator.phase10_5.registry.sync"
    )


@router.get("/agents", response_model=list[AgentRegistryRead])
async def list_phase10_5_agents(
    enabled_only: bool = Query(default=False),
    category: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10_5AgentFrameworkService(db).list_agents(
        enabled_only=enabled_only,
        category=category,
        limit=limit,
    )


@router.get("/agents/executions", response_model=list[AgentExecutionRead])
async def list_phase10_5_agent_executions(
    program_id: UUID | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    execution_status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10_5AgentFrameworkService(db).list_executions(
        program_id=program_id,
        agent_id=agent_id,
        execution_status=execution_status,
        limit=limit,
    )


@router.get("/agents/evaluations", response_model=list[AgentEvaluationRead])
async def list_phase10_5_agent_evaluations(
    agent_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase10_5AgentFrameworkService(db).list_evaluations(
        agent_id=agent_id,
        status=status,
        limit=limit,
    )


@router.get("/agents/{agent_id}", response_model=AgentRegistryRead)
async def get_phase10_5_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await Phase10_5AgentFrameworkService(db).get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/agents/{agent_id}/run", response_model=AgentExecutionRead)
async def run_phase10_5_agent(
    agent_id: str,
    body: AgentRunRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        result = await Phase10_5AgentFrameworkService(db).run_agent(
            agent_id=agent_id,
            actor=body.actor,
            input_payload=body.input_payload,
            program_id=body.program_id,
            scope_target_id=body.scope_target_id,
            workflow_run_id=body.workflow_run_id,
            analyst_case_id=body.analyst_case_id,
            analyst_queue_item_id=body.analyst_queue_item_id,
            persist_record=True,
        )
        return result
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/agents/{agent_id}/evaluate", response_model=AgentEvaluationRead)
async def evaluate_phase10_5_agent(
    agent_id: str,
    body: AgentEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase10_5AgentFrameworkService(db).evaluate_agent(
            agent_id=agent_id,
            actor=body.actor,
            benchmark_name=body.benchmark_name,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/deltas", response_model=list[WorkflowDeltaRead])
async def list_deltas(
    program_id: UUID | None = Query(default=None),
    scope_target_id: UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await BugBountyHuntingService(db).list_deltas(
        program_id=program_id,
        scope_target_id=scope_target_id,
        limit=limit,
    )


@router.get("/candidates", response_model=list[AnalystQueueItemRead])
async def list_candidates(
    program_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await BugBountyHuntingService(db).list_candidate_queue(
        program_id=program_id,
        status=status,
        limit=limit,
    )


@router.patch("/candidates/{queue_item_id}", response_model=AnalystQueueItemRead)
async def update_candidate(
    queue_item_id: UUID,
    body: CandidateQueueUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    svc = BugBountyHuntingService(db)
    try:
        return await svc.update_candidate_queue_item(queue_item_id, body)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/alerts/sync", response_model=AlertSyncResponse)
async def sync_alerts(
    body: AlertSyncRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    return await Phase9AlertCaseService(db).sync_alerts(
        actor=body.actor,
        program_id=body.program_id,
        cooldown_minutes=body.cooldown_minutes,
    )


@router.get("/alerts", response_model=list[NotificationAlertRead])
async def list_alerts(
    program_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase9AlertCaseService(db).list_alerts(
        program_id=program_id,
        status=status,
        severity=severity,
        limit=limit,
    )


@router.get("/alerts/summary")
async def alerts_summary(
    program_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await Phase9AlertCaseService(db).get_alert_case_summary(program_id=program_id)


@router.get("/alerts/{alert_id}", response_model=NotificationAlertRead)
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    alert = await Phase9AlertCaseService(db).get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/alerts/{alert_id}/acknowledge", response_model=NotificationAlertRead)
async def acknowledge_alert(
    alert_id: UUID,
    body: AlertActionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase9AlertCaseService(db).acknowledge_alert(
            alert_id,
            actor=body.actor,
            note=body.note,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/alerts/{alert_id}/resolve", response_model=NotificationAlertRead)
async def resolve_alert(
    alert_id: UUID,
    body: AlertActionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase9AlertCaseService(db).resolve_alert(
            alert_id,
            actor=body.actor,
            note=body.note,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/alerts/{alert_id}/case", response_model=AnalystCaseRead)
async def create_case_from_alert(
    alert_id: UUID,
    body: AlertCaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase9AlertCaseService(db).create_case_from_alert(
            alert_id,
            actor=body.actor,
            owner=body.owner,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/cases", response_model=list[AnalystCaseRead])
async def list_cases(
    program_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    return await Phase9AlertCaseService(db).list_cases(
        program_id=program_id,
        status=status,
        priority=priority,
        owner=owner,
        limit=limit,
    )


@router.post("/cases", response_model=AnalystCaseRead)
async def create_case(
    body: CaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase9AlertCaseService(db).create_case(
            program_id=body.program_id,
            scope_target_id=body.scope_target_id,
            workflow_run_id=body.workflow_run_id,
            alert_id=body.alert_id,
            analyst_queue_item_id=body.analyst_queue_item_id,
            prediction_record_id=body.prediction_record_id,
            recommendation_record_id=body.recommendation_record_id,
            submission_draft_id=body.submission_draft_id,
            title=body.title,
            summary=body.summary,
            reasoning_summary=body.reasoning_summary,
            priority=body.priority,
            owner=body.owner,
            evidence_refs=body.evidence_refs_json,
            actor=body.actor,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get("/cases/{case_id}", response_model=AnalystCaseRead)
async def get_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    case = await Phase9AlertCaseService(db).get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/cases/{case_id}", response_model=AnalystCaseRead)
async def update_case(
    case_id: UUID,
    body: CaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase9AlertCaseService(db).update_case(
            case_id,
            actor=body.actor,
            status=body.status,
            priority=body.priority,
            summary=body.summary,
            reasoning_summary=body.reasoning_summary,
            closure_reason=body.closure_reason,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/cases/{case_id}/assign", response_model=AnalystCaseRead)
async def assign_case(
    case_id: UUID,
    body: CaseAssignRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase9AlertCaseService(db).assign_case(
            case_id,
            owner=body.owner,
            actor=body.actor,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post("/cases/{case_id}/notes", response_model=AnalystCaseRead)
async def add_case_note(
    case_id: UUID,
    body: CaseNoteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        return await Phase9AlertCaseService(db).add_case_note(
            case_id,
            note=body.note,
            actor=body.actor,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post(
    "/candidates/{queue_item_id}/report-draft",
    response_model=GenerateReportDraftResponse,
)
async def generate_report_draft(
    queue_item_id: UUID,
    body: GenerateReportDraftRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    svc = BugBountyHuntingService(db)
    try:
        return await svc.generate_report_draft(
            queue_item_id,
            actor=body.actor,
            analyst_notes=body.analyst_notes,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
