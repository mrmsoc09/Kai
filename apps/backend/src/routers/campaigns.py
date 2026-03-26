from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.approval_gate_service import ApprovalGateService
from ..core.auth import (
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    User,
    get_current_user,
    require_roles,
)
from ..core.branch_scheduler import BranchScheduler
from ..core.bugbounty_workflow_engine import build_phase_specs_for_template, list_workflow_templates
from ..core.campaign_service import CampaignStartService
from ..core.execution_result_service import ExecutionResultIngestionService
from ..core.finding_correlation_service import FindingCorrelationService
from ..core.finding_review_service import FindingReviewService
from ..core.hil_db import get_db
from ..core.metrics_service import MetricsService
from ..core.review_queue_service import ReviewQueueService
from ..core.scope_guardrails import load_scope_policy
from ..core.submission_export_service import SubmissionExportService
from ..core.submission_package_service import SubmissionPackageService
from ..core.workflow_executor import WorkflowExecutor
from ..core.workflow_output_store import write_workflow_plan, write_workflow_summary
from ..core.workflow_run_service import WorkflowRunService
from ..models.campaign import (
    ApprovalGate,
    Artifact,
    AuditEvent,
    Observation,
    SubmissionDraft,
    ToolExecution,
)
from ..models.enums import ApprovalGateStatusEnum, WorkflowRunStatusEnum
from ..models.hil import Evidence, Finding
from ..schemas.campaigns import (
    ApprovalGateDecision,
    CampaignApprovalDecisionRequest,
    CampaignApprovalDecisionResponse,
    CampaignCorrelationResponse,
    CampaignDiagnosticsResponse,
    CampaignScheduleSummary,
    CampaignStartRequest,
    CampaignStartResponse,
    CampaignStatusEnum,
    CampaignStatusResponse,
    CorrelationRecordRead,
    DiagnosticsSummaryResponse,
    ExecutionResultIngestRequest,
    ExecutionResultIngestResponse,
    FindingDiagnosticsResponse,
    FindingReviewQueueResponse,
    FindingReviewResponse,
    PrepareSubmissionResponse,
    StageRunRead,
    SubmissionExportResponse,
    ToolExecutionRead,
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowFindingRead,
    WorkflowRunRead,
    WorkflowStartRequest,
    WorkflowStartResponse,
    WorkflowTemplateInfo,
)

router = APIRouter()
campaign_router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(get_current_user)],
)
findings_router = APIRouter(
    prefix="/api/v1/findings",
    tags=["findings"],
    dependencies=[Depends(get_current_user)],
)
diagnostics_router = APIRouter(
    prefix="/api/v1/diagnostics",
    tags=["diagnostics"],
    dependencies=[Depends(get_current_user)],
)


class FindingReviewRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    review_notes: str | None = Field(default=None, max_length=4000)
    reviewer_id: str = Field(..., min_length=1, max_length=255)
    intention_id: UUID | None = None
    duplicate_of_finding_id: UUID | None = None


class PrepareSubmissionRequest(BaseModel):
    reviewer_id: str = Field(..., min_length=1, max_length=255)
    intention_id: UUID | None = None


class FindingExportRequest(BaseModel):
    actor: str = Field(default="operator.submission_export", min_length=1, max_length=255)
    submission_draft_id: UUID | None = None
    intention_id: UUID | None = None


def _phase_job_payload(job) -> dict:
    return {
        "id": job.id,
        "campaign_id": job.campaign_id,
        "branch_id": job.branch_id,
        "depends_on_job_id": job.depends_on_job_id,
        "phase_name": job.phase_name,
        "phase_order": job.phase_order,
        "status": job.status,
        "policy_class": job.policy_class,
        "approval_required": job.approval_required,
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "ended_at": job.ended_at,
        "canceled_at": job.canceled_at,
        "canceled_by": job.canceled_by,
        "blocked_reason": job.blocked_reason,
        "worker_task_id": job.worker_task_id,
        "queue_name": job.queue_name,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "input_payload_json": job.input_payload_json,
        "output_summary_json": job.output_summary_json,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _schedule_payload(summary) -> CampaignScheduleSummary:
    return CampaignScheduleSummary(
        campaign_id=summary.campaign_id,
        considered_jobs=summary.considered_jobs,
        queued_jobs=summary.queued_jobs,
        blocked_jobs=summary.blocked_jobs,
        waiting_approval_jobs=summary.waiting_approval_jobs,
        created_approval_gates=summary.created_approval_gates,
        dispatched_tool_executions=summary.dispatched_tool_executions,
    )


def _status_counts(items, *, attr: str = "status") -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = getattr(item, attr, None)
        key = value.value if hasattr(value, "value") else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _value_error_to_http(exc: ValueError) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    if "not found" in lowered:
        return HTTPException(status_code=404, detail=message)
    if (
        "unsupported" in lowered
        or "is required" in lowered
        or "either finding_id or submission_draft_id is required" in lowered
    ):
        return HTTPException(status_code=400, detail=message)
    return HTTPException(status_code=422, detail=message)


@campaign_router.post("/start", response_model=CampaignStartResponse)
async def start_campaign(
    body: CampaignStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    starter = CampaignStartService(db)
    scheduler = BranchScheduler(db)
    try:
        seeded = await starter.start_campaign(body)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    schedule_summary = await scheduler.schedule_campaign(
        seeded.campaign.id,
        actor=current_user.id,
    )
    refreshed_campaign = await starter.repo.get_campaign(seeded.campaign.id)
    refreshed_root_branch = await starter.repo.get_branch(seeded.root_branch.id)
    refreshed_jobs = await starter.repo.list_phase_jobs(
        seeded.campaign.id,
        branch_id=seeded.root_branch.id,
    )
    if refreshed_campaign is None or refreshed_root_branch is None:
        raise HTTPException(status_code=500, detail="Seeded campaign graph is incomplete")
    return CampaignStartResponse(
        campaign_id=refreshed_campaign.id,
        program_id=refreshed_campaign.program_id,
        branch_id=refreshed_root_branch.id,
        campaign_status=refreshed_campaign.status,
        branch_status=refreshed_root_branch.status,
        phase_jobs=[_phase_job_payload(job) for job in refreshed_jobs],
        scheduler=_schedule_payload(schedule_summary),
        idempotent_replay=seeded.idempotent_replay,
    )


@campaign_router.get("/workflow-templates", response_model=list[WorkflowTemplateInfo])
async def get_workflow_templates():
    return list_workflow_templates()


@campaign_router.post("/start-workflow", response_model=WorkflowStartResponse)
async def start_workflow_campaign(
    body: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    try:
        policy = load_scope_policy(body.scope_policy_path)
        phase_specs, workflow_metadata = build_phase_specs_for_template(
            template_name=body.workflow_template,
            target=body.target,
            safe_mode=body.safe_mode,
            scope_policy=policy,
            enable_steps=body.enable_steps,
            disable_steps=body.disable_steps,
            dry_run=body.dry_run,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    if body.dry_run:
        planned = [
            {
                "phase_name": phase.phase_name,
                "phase_order": phase.phase_order,
                "approval_required": phase.approval_required,
                "queue_name": phase.queue_name,
                "input_payload_json": phase.input_payload_json,
            }
            for phase in phase_specs
        ]
        workflow_key = f"dry-run-{body.workflow_template}-{body.target.replace('/', '_')}"
        plan_path = write_workflow_plan(
            workflow_key=workflow_key,
            workflow_template=body.workflow_template,
            metadata=workflow_metadata,
            phase_plan=planned,
        )
        workflow_metadata = {**workflow_metadata, "plan_artifact_path": plan_path}
        return WorkflowStartResponse(
            workflow_template=body.workflow_template,
            workflow_metadata=workflow_metadata,
            dry_run=True,
            phase_jobs=planned,
        )

    starter = CampaignStartService(db)
    scheduler = BranchScheduler(db)
    declared_goal = body.declared_goal or (
        f"Execute workflow template {body.workflow_template} against {body.target}"
    )
    run_config_json = dict(body.run_config_json)
    run_config_json.setdefault("workflow_template", body.workflow_template)
    run_config_json.setdefault("workflow_metadata", workflow_metadata)
    run_config_json.setdefault("safe_mode", body.safe_mode)
    start_request = CampaignStartRequest(
        program_id=body.program_id,
        program_name=body.program_name,
        program_key=body.program_key,
        target=body.target,
        target_type=body.target_type,
        campaign_name=body.campaign_name,
        initiated_by=body.initiated_by,
        declared_goal=declared_goal,
        declared_reason=body.declared_reason,
        policy_basis=body.policy_basis,
        risk_class=body.risk_class,
        approval_required=body.approval_required,
        idempotency_key=body.idempotency_key,
        initial_branch_key=body.initial_branch_key,
        initial_branch_name=body.initial_branch_name,
        run_config_json=run_config_json,
        phases=phase_specs,
        phase_approval_overrides=body.phase_approval_overrides,
    )
    try:
        seeded = await starter.start_campaign(start_request)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    schedule_summary = await scheduler.schedule_campaign(
        seeded.campaign.id,
        actor=body.initiated_by,
    )
    refreshed_campaign = await starter.repo.get_campaign(seeded.campaign.id)
    refreshed_root_branch = await starter.repo.get_branch(seeded.root_branch.id)
    refreshed_jobs = await starter.repo.list_phase_jobs(
        seeded.campaign.id,
        branch_id=seeded.root_branch.id,
    )
    if refreshed_campaign is None or refreshed_root_branch is None:
        raise HTTPException(status_code=500, detail="Seeded campaign graph is incomplete")
    plan_rows = [
        {
            "phase_name": phase.phase_name,
            "phase_order": phase.phase_order,
            "depends_on_phase_name": phase.depends_on_phase_name,
            "approval_required": phase.approval_required,
            "queue_name": phase.queue_name,
            "input_payload_json": phase.input_payload_json,
        }
        for phase in phase_specs
    ]
    plan_path = write_workflow_plan(
        workflow_key=str(refreshed_campaign.id),
        workflow_template=body.workflow_template,
        metadata=workflow_metadata,
        phase_plan=plan_rows,
    )
    summary_path = write_workflow_summary(
        workflow_key=str(refreshed_campaign.id),
        summary={
            "campaign_id": str(refreshed_campaign.id),
            "branch_id": str(refreshed_root_branch.id),
            "workflow_template": body.workflow_template,
            "scheduler": _schedule_payload(schedule_summary).model_dump(),
        },
    )

    workflow_svc = WorkflowRunService(db)
    workflow_run = await workflow_svc.create_workflow_run(
        campaign_run_id=refreshed_campaign.id,
        scope_target_id=refreshed_campaign.primary_scope_target_id,
        template_name=body.workflow_template,
        target=body.target,
        safe_mode=body.safe_mode,
        dry_run=False,
        trigger_source="API",
        total_phases=len(phase_specs),
        artifact_manifest_path=plan_path,
        plan_artifact_path=plan_path,
    )
    await workflow_svc.transition_workflow_run(
        workflow_run,
        WorkflowRunStatusEnum.RUNNING,
        summary_artifact_path=summary_path,
    )

    stage_counts: dict[str, int] = {}
    stage_order_map: dict[str, int] = {}
    for i, spec in enumerate(phase_specs):
        if isinstance(spec.input_payload_json, dict):
            stage_key = (
                spec.input_payload_json.get("workflow_stage")
                or spec.input_payload_json.get("stage")
                or spec.phase_name.rsplit("_", 1)[0]
            )
        else:
            stage_key = spec.phase_name
        stage_counts[stage_key] = stage_counts.get(stage_key, 0) + 1
        if stage_key not in stage_order_map:
            stage_order_map[stage_key] = i

    stage_run_by_name: dict[str, UUID] = {}
    for stage_name, count in stage_counts.items():
        stage_run = await workflow_svc.create_stage_run(
            workflow_run_id=workflow_run.id,
            campaign_run_id=refreshed_campaign.id,
            stage_name=stage_name,
            stage_order=stage_order_map[stage_name],
            phase_count=count,
        )
        stage_run_by_name[stage_name] = stage_run.id

    # Back-link seeded phase jobs to their workflow/stage records.
    for job in refreshed_jobs:
        payload = job.input_payload_json if isinstance(job.input_payload_json, dict) else {}
        stage_key = (
            payload.get("workflow_stage")
            or payload.get("stage")
            or job.phase_name.rsplit("_", 1)[0]
        )
        job.workflow_run_id = workflow_run.id
        job.stage_run_id = stage_run_by_name.get(stage_key)
    await db.flush()

    return WorkflowStartResponse(
        workflow_template=body.workflow_template,
        workflow_metadata={
            **workflow_metadata,
            "plan_artifact_path": plan_path,
            "summary_artifact_path": summary_path,
        },
        dry_run=False,
        campaign_id=refreshed_campaign.id,
        program_id=refreshed_campaign.program_id,
        branch_id=refreshed_root_branch.id,
        campaign_status=CampaignStatusEnum(refreshed_campaign.status.value),
        branch_status=refreshed_root_branch.status,
        phase_jobs=[_phase_job_payload(job) for job in refreshed_jobs],
        scheduler=_schedule_payload(schedule_summary),
        idempotent_replay=seeded.idempotent_replay,
    )


@campaign_router.post("/execute-workflow", response_model=WorkflowExecuteResponse)
async def execute_workflow_local(
    body: WorkflowExecuteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    executor = WorkflowExecutor(db=db, trigger_source="API")
    try:
        result = await executor.execute_template(
            workflow_template=body.workflow_template,
            target=body.target,
            run_id=body.run_id,
            safe_mode=body.safe_mode,
            dry_run=body.dry_run,
            concurrency_limit=body.concurrency_limit,
            enable_steps=body.enable_steps,
            disable_steps=body.disable_steps,
            scope_policy_path=body.scope_policy_path,
            resume=body.resume,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return result.as_dict()


@campaign_router.get("/workflows/runs", response_model=list[WorkflowRunRead])
async def list_workflow_runs(
    campaign_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    template_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    workflow_svc = WorkflowRunService(db)
    status_enum: WorkflowRunStatusEnum | None = None
    if status:
        try:
            status_enum = WorkflowRunStatusEnum(status)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid workflow status: {status}"
            ) from exc
    runs = await workflow_svc.list_workflow_runs(
        campaign_run_id=campaign_id,
        status=status_enum,
        template_name=template_name,
        limit=limit,
    )
    return runs


@campaign_router.get("/workflows/runs/{workflow_run_id}", response_model=WorkflowRunRead)
async def get_workflow_run(
    workflow_run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    workflow_svc = WorkflowRunService(db)
    record = await workflow_svc.get_workflow_run(workflow_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return record


@campaign_router.get("/workflows/runs/{workflow_run_id}/stages", response_model=list[StageRunRead])
async def list_workflow_stage_runs(
    workflow_run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    workflow_svc = WorkflowRunService(db)
    record = await workflow_svc.get_workflow_run(workflow_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return await workflow_svc.list_stage_runs(workflow_run_id)


@campaign_router.get(
    "/workflows/runs/{workflow_run_id}/tool-executions",
    response_model=list[ToolExecutionRead],
)
async def list_workflow_tool_executions(
    workflow_run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    workflow_svc = WorkflowRunService(db)
    record = await workflow_svc.get_workflow_run(workflow_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return await workflow_svc.list_tool_executions(workflow_run_id)


@campaign_router.get(
    "/workflows/runs/{workflow_run_id}/findings",
    response_model=list[WorkflowFindingRead],
)
async def list_workflow_findings(
    workflow_run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    workflow_svc = WorkflowRunService(db)
    record = await workflow_svc.get_workflow_run(workflow_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return await workflow_svc.list_workflow_findings(workflow_run_id)


@campaign_router.get(
    "/workflows/runs/{workflow_run_id}/correlations",
    response_model=list[CorrelationRecordRead],
)
async def list_workflow_correlations(
    workflow_run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    workflow_svc = WorkflowRunService(db)
    record = await workflow_svc.get_workflow_run(workflow_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return await workflow_svc.list_correlation_records(workflow_run_id)


@campaign_router.post("/{campaign_id}/schedule", response_model=CampaignScheduleSummary)
async def schedule_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    scheduler = BranchScheduler(db)
    try:
        summary = await scheduler.schedule_campaign(campaign_id)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return _schedule_payload(summary)


@campaign_router.get("/{campaign_id}", response_model=CampaignStatusResponse)
async def get_campaign_status(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    service = CampaignStartService(db)
    campaign = await service.repo.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    branches = await service.repo.list_branches(campaign_id)
    jobs = await service.repo.list_phase_jobs(campaign_id)
    return {
        "campaign": {
            "id": str(campaign.id),
            "status": campaign.status.value,
            "program_id": str(campaign.program_id),
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
        },
        "branches": [
            {
                "id": str(branch.id),
                "branch_key": branch.branch_key,
                "status": branch.status.value,
                "depends_on_branch_id": (
                    str(branch.depends_on_branch_id) if branch.depends_on_branch_id else None
                ),
            }
            for branch in branches
        ],
        "phase_jobs": [
            {
                "id": str(job.id),
                "phase_name": job.phase_name,
                "phase_order": job.phase_order,
                "status": job.status.value,
                "depends_on_job_id": str(job.depends_on_job_id) if job.depends_on_job_id else None,
                "approval_required": job.approval_required,
                "worker_task_id": job.worker_task_id,
            }
            for job in jobs
        ],
    }


@campaign_router.post("/executions/ingest", response_model=ExecutionResultIngestResponse)
async def ingest_execution_result(
    body: ExecutionResultIngestRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    ingestion = ExecutionResultIngestionService(db)
    try:
        return await ingestion.ingest_result(body, actor=body.actor)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@campaign_router.post(
    "/approvals/{gate_id}/decision",
    response_model=CampaignApprovalDecisionResponse,
)
async def decide_campaign_approval_gate(
    gate_id: UUID,
    body: CampaignApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    approvals = ApprovalGateService(db)
    scheduler = BranchScheduler(db)
    actor_id = getattr(current_user, "id", None) or body.decided_by or "operator"
    gate = await approvals.get_gate(gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail=f"Approval gate not found: {gate_id}")

    try:
        if body.status == ApprovalGateStatusEnum.CANCELED:
            decided = await approvals.cancel_gate(
                gate,
                actor=actor_id,
                note=body.operator_notes,
                intention_id=body.intention_id,
            )
        else:
            decided = await approvals.decide_gate(
                gate,
                ApprovalGateDecision(
                    status=body.status,
                    decided_by=actor_id,
                    operator_notes=body.operator_notes,
                    decision_payload_json=body.decision_payload_json,
                ),
                actor=actor_id,
                intention_id=body.intention_id,
            )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    schedule_summary = None
    if body.trigger_scheduler:
        schedule_summary = await scheduler.schedule_campaign(
            decided.campaign_id,
            actor=f"{actor_id}.approval",
        )
    return CampaignApprovalDecisionResponse(
        gate_id=decided.id,
        campaign_id=decided.campaign_id,
        status=decided.status,
        decided_by=decided.decided_by,
        decided_at=decided.decided_at,
        scheduler=_schedule_payload(schedule_summary) if schedule_summary else None,
    )


@campaign_router.post("/{campaign_id}/correlate", response_model=CampaignCorrelationResponse)
async def correlate_campaign_observations(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    service = CampaignStartService(db)
    campaign = await service.repo.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    correlator = FindingCorrelationService(db)
    summary = await correlator.process_campaign(
        campaign_id,
        actor="operator.correlation.manual",
    )
    return {"campaign_id": campaign_id, **summary}


@findings_router.get("/review-queue", response_model=FindingReviewQueueResponse)
async def finding_review_queue(
    campaign_id: UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    queue_service = ReviewQueueService(db)
    items = await queue_service.list_review_queue(campaign_id=campaign_id, limit=limit)
    return {"count": len(items), "items": items}


@findings_router.post("/{finding_id}/review", response_model=FindingReviewResponse)
async def review_finding(
    finding_id: UUID,
    body: FindingReviewRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    action = body.action.strip().upper()
    review_service = FindingReviewService(db)
    try:
        result = await review_service.review_finding(
            finding_id=finding_id,
            action=action,
            reviewer_id=body.reviewer_id,
            review_notes=body.review_notes,
            intention_id=body.intention_id,
            duplicate_of_finding_id=body.duplicate_of_finding_id,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return {
        "finding_id": result.finding_id,
        "finding_status": result.finding_status,
        "submission_draft_id": result.draft_id,
        "submission_draft_status": result.draft_status,
        "campaign_id": result.campaign_id,
        "review_timestamp": result.review_timestamp,
    }


@findings_router.post("/{finding_id}/prepare-submission", response_model=PrepareSubmissionResponse)
async def prepare_submission(
    finding_id: UUID,
    body: PrepareSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    service = SubmissionPackageService(db)
    try:
        result = await service.prepare_submission_package(
            finding_id=finding_id,
            prepared_by=body.reviewer_id,
            intention_id=body.intention_id,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return {
        "finding_id": result.finding_id,
        "submission_draft_id": result.draft_id,
        "submission_draft_status": result.draft_status,
        "package_json": result.package_json,
    }


@findings_router.get(
    "/{finding_id}/export/{provider}/preview",
    response_model=SubmissionExportResponse,
)
async def preview_finding_submission_export(
    finding_id: UUID,
    provider: str,
    actor: str = Query(default="operator.submission_export.preview", min_length=1, max_length=255),
    submission_draft_id: UUID | None = Query(default=None),
    intention_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = SubmissionExportService(db)
    try:
        result = await service.preview_payload(
            provider=provider,
            finding_id=finding_id,
            submission_draft_id=submission_draft_id,
            actor=actor,
            intention_id=intention_id,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return result.as_dict()


@findings_router.post("/{finding_id}/export/{provider}", response_model=SubmissionExportResponse)
async def export_finding_submission_payload(
    finding_id: UUID,
    provider: str,
    body: FindingExportRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    body = body or FindingExportRequest()
    service = SubmissionExportService(db)
    try:
        result = await service.export_payload(
            provider=provider,
            finding_id=finding_id,
            submission_draft_id=body.submission_draft_id,
            actor=body.actor,
            intention_id=body.intention_id,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    payload = result.as_dict()
    if not result.ready:
        return JSONResponse(status_code=422, content=payload)
    return payload


@diagnostics_router.get("/summary", response_model=DiagnosticsSummaryResponse)
async def diagnostics_summary(db: AsyncSession = Depends(get_db)):
    metrics = MetricsService(db)
    return await metrics.summary_counts()


@campaign_router.get("/{campaign_id}/diagnostics", response_model=CampaignDiagnosticsResponse)
async def campaign_diagnostics(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    service = CampaignStartService(db)
    campaign = await service.repo.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    branches = await service.repo.list_branches(campaign_id)
    phase_jobs = await service.repo.list_phase_jobs(campaign_id)

    tool_exec_result = await db.execute(
        select(ToolExecution)
        .where(ToolExecution.campaign_id == campaign_id)
        .order_by(ToolExecution.created_at.asc())
    )
    tool_executions = list(tool_exec_result.scalars().all())

    gates_result = await db.execute(
        select(ApprovalGate)
        .where(ApprovalGate.campaign_id == campaign_id)
        .order_by(ApprovalGate.created_at.asc())
    )
    approval_gates = list(gates_result.scalars().all())

    artifact_result = await db.execute(
        select(func.count(Artifact.id)).where(Artifact.campaign_id == campaign_id)
    )
    observation_result = await db.execute(
        select(func.count(Observation.id)).where(Observation.campaign_id == campaign_id)
    )
    drafts_result = await db.execute(
        select(SubmissionDraft)
        .where(SubmissionDraft.campaign_id == campaign_id)
        .order_by(SubmissionDraft.created_at.asc())
    )
    drafts = list(drafts_result.scalars().all())
    audit_result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.campaign_id == campaign_id)
        .order_by(AuditEvent.happened_at.desc())
        .limit(50)
    )
    audit_events = list(audit_result.scalars().all())

    return {
        "campaign": {
            "id": str(campaign.id),
            "status": campaign.status.value,
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
            "blocked_reason": campaign.blocked_reason,
            "last_error": campaign.last_error,
        },
        "counts": {
            "branches": len(branches),
            "phase_jobs": len(phase_jobs),
            "tool_executions": len(tool_executions),
            "approval_gates": len(approval_gates),
            "artifacts": int(artifact_result.scalar() or 0),
            "observations": int(observation_result.scalar() or 0),
            "submission_drafts": len(drafts),
        },
        "status_breakdown": {
            "branches": _status_counts(branches),
            "phase_jobs": _status_counts(phase_jobs),
            "tool_executions": _status_counts(tool_executions),
            "approval_gates": _status_counts(approval_gates),
            "submission_drafts": _status_counts(drafts),
        },
        "phase_links": [
            {
                "phase_job_id": str(job.id),
                "phase_name": job.phase_name,
                "phase_status": job.status.value,
                "worker_task_id": job.worker_task_id,
                "depends_on_job_id": str(job.depends_on_job_id) if job.depends_on_job_id else None,
            }
            for job in phase_jobs
        ],
        "recent_audit_events": [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "actor": event.actor,
                "happened_at": event.happened_at.isoformat() if event.happened_at else None,
                "phase_job_id": str(event.phase_job_id) if event.phase_job_id else None,
                "tool_execution_id": (
                    str(event.tool_execution_id) if event.tool_execution_id else None
                ),
                "approval_gate_id": str(event.approval_gate_id) if event.approval_gate_id else None,
                "message": event.message,
                "payload": event.event_payload_json,
            }
            for event in audit_events
        ],
    }


@findings_router.get("/{finding_id}/diagnostics", response_model=FindingDiagnosticsResponse)
async def finding_diagnostics(finding_id: UUID, db: AsyncSession = Depends(get_db)):
    finding_result = await db.execute(
        select(Finding).where(Finding.id == finding_id, Finding.is_deleted.is_(False))
    )
    finding = finding_result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    evidence_result = await db.execute(
        select(Evidence)
        .where(Evidence.finding_id == finding.id, Evidence.is_deleted.is_(False))
        .order_by(Evidence.created_at.asc())
    )
    evidences = list(evidence_result.scalars().all())
    observation_result = await db.execute(
        select(Observation)
        .where(Observation.finding_id == finding.id)
        .order_by(Observation.created_at.asc())
    )
    observations = list(observation_result.scalars().all())
    artifact_result = await db.execute(
        select(Artifact)
        .where(Artifact.finding_id == finding.id)
        .order_by(Artifact.created_at.asc())
    )
    artifacts = list(artifact_result.scalars().all())
    draft_result = await db.execute(
        select(SubmissionDraft)
        .where(SubmissionDraft.finding_id == finding.id)
        .order_by(SubmissionDraft.created_at.asc())
    )
    drafts = list(draft_result.scalars().all())
    audit_result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.finding_id == finding.id)
        .order_by(AuditEvent.happened_at.desc())
        .limit(50)
    )
    audit_events = list(audit_result.scalars().all())

    return {
        "finding": {
            "id": str(finding.id),
            "program": finding.program,
            "asset": finding.asset,
            "title": finding.title,
            "status": finding.status.value,
            "severity": finding.severity.value if finding.severity else None,
            "scope_json": finding.scope_json,
        },
        "counts": {
            "evidence": len(evidences),
            "observations": len(observations),
            "artifacts": len(artifacts),
            "submission_drafts": len(drafts),
            "audit_events": len(audit_events),
        },
        "submission_drafts": [
            {
                "id": str(draft.id),
                "campaign_id": str(draft.campaign_id),
                "branch_id": str(draft.branch_id) if draft.branch_id else None,
                "status": draft.status,
                "prepared_by": draft.prepared_by,
                "approved_by": draft.approved_by,
                "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
            }
            for draft in drafts
        ],
        "recent_observations": [
            {
                "id": str(obs.id),
                "category": obs.category,
                "title": obs.title,
                "summary": obs.summary,
                "tool_execution_id": str(obs.tool_execution_id) if obs.tool_execution_id else None,
                "phase_job_id": str(obs.phase_job_id) if obs.phase_job_id else None,
            }
            for obs in observations[-10:]
        ],
        "recent_audit_events": [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "actor": event.actor,
                "happened_at": event.happened_at.isoformat() if event.happened_at else None,
                "message": event.message,
                "payload": event.event_payload_json,
            }
            for event in audit_events
        ],
    }


router.include_router(campaign_router)
router.include_router(findings_router)
router.include_router(diagnostics_router)
