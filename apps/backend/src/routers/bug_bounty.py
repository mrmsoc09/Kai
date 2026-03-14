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
from ..core.recon_inference_service import ReconInferenceService
from ..schemas.bug_bounty_hunt import (
    AdaptiveScheduleActionRead,
    AnalystQueueItemRead,
    AnalystBriefingResponse,
    CandidateQueueUpdateRequest,
    GenerateReportDraftRequest,
    GenerateReportDraftResponse,
    HuntScheduleCreateRequest,
    HuntScheduleRead,
    HuntScheduleUpdateRequest,
    MonitoredTargetRead,
    MonitoredTargetUpdateRequest,
    OpportunityInferenceRead,
    ProgramOpportunityImportRequest,
    ProgramOpportunityRead,
    ReadinessCheckResponse,
    ScheduleDispatchResponse,
    ScheduleTriggerResponse,
    SchedulerStatusResponse,
    SignalIntelligenceRead,
    SwarmReasoningRead,
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
