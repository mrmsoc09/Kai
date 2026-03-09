from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.approval_gate_service import ApprovalGateService
from ..core.branch_scheduler import BranchScheduler
from ..core.campaign_service import CampaignStartService
from ..core.execution_result_service import ExecutionResultIngestionService
from ..core.finding_correlation_service import FindingCorrelationService
from ..core.finding_review_service import FindingReviewService
from ..core.hil_db import get_db
from ..core.review_queue_service import ReviewQueueService
from ..core.submission_package_service import SubmissionPackageService
from ..models.enums import ApprovalGateStatusEnum
from ..schemas.campaigns import (
    ApprovalGateDecision,
    CampaignApprovalDecisionRequest,
    CampaignApprovalDecisionResponse,
    CampaignScheduleSummary,
    CampaignStartRequest,
    CampaignStartResponse,
    ExecutionResultIngestRequest,
    ExecutionResultIngestResponse,
)


router = APIRouter()
campaign_router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])
findings_router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


class FindingReviewRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    review_notes: str | None = Field(default=None, max_length=4000)
    reviewer_id: str = Field(..., min_length=1, max_length=255)
    intention_id: UUID | None = None
    duplicate_of_finding_id: UUID | None = None


class PrepareSubmissionRequest(BaseModel):
    reviewer_id: str = Field(..., min_length=1, max_length=255)
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


@campaign_router.post("/start", response_model=CampaignStartResponse)
async def start_campaign(body: CampaignStartRequest, db: AsyncSession = Depends(get_db)):
    starter = CampaignStartService(db)
    scheduler = BranchScheduler(db)
    try:
        seeded = await starter.start_campaign(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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


@campaign_router.post("/{campaign_id}/schedule", response_model=CampaignScheduleSummary)
async def schedule_campaign(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    scheduler = BranchScheduler(db)
    try:
        summary = await scheduler.schedule_campaign(campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _schedule_payload(summary)


@campaign_router.get("/{campaign_id}")
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
                "depends_on_branch_id": str(branch.depends_on_branch_id)
                if branch.depends_on_branch_id
                else None,
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
):
    ingestion = ExecutionResultIngestionService(db)
    try:
        return await ingestion.ingest_result(body, actor=body.actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@campaign_router.post(
    "/approvals/{gate_id}/decision",
    response_model=CampaignApprovalDecisionResponse,
)
async def decide_campaign_approval_gate(
    gate_id: UUID,
    body: CampaignApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    approvals = ApprovalGateService(db)
    scheduler = BranchScheduler(db)
    gate = await approvals.get_gate(gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail=f"Approval gate not found: {gate_id}")

    try:
        if body.status == gate.status:
            decided = gate
        elif body.status == ApprovalGateStatusEnum.CANCELED:
            decided = await approvals.cancel_gate(
                gate,
                actor=body.decided_by,
                note=body.operator_notes,
                intention_id=body.intention_id,
            )
        else:
            decided = await approvals.decide_gate(
                gate,
                ApprovalGateDecision(
                    status=body.status,
                    decided_by=body.decided_by,
                    operator_notes=body.operator_notes,
                    decision_payload_json=body.decision_payload_json,
                ),
                actor=body.decided_by,
                intention_id=body.intention_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    schedule_summary = None
    if body.trigger_scheduler:
        schedule_summary = await scheduler.schedule_campaign(
            decided.campaign_id,
            actor=f"{body.decided_by}.approval",
        )
    return CampaignApprovalDecisionResponse(
        gate_id=decided.id,
        campaign_id=decided.campaign_id,
        status=decided.status,
        decided_by=decided.decided_by,
        decided_at=decided.decided_at,
        scheduler=_schedule_payload(schedule_summary) if schedule_summary else None,
    )


@campaign_router.post("/{campaign_id}/correlate")
async def correlate_campaign_observations(campaign_id: UUID, db: AsyncSession = Depends(get_db)):
    service = CampaignStartService(db)
    campaign = await service.repo.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    correlator = FindingCorrelationService(db)
    summary = await correlator.process_campaign(
        campaign_id,
        actor="operator.correlation.manual",
    )
    return {"campaign_id": str(campaign_id), **summary}


@findings_router.get("/review-queue")
async def finding_review_queue(
    campaign_id: UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    queue_service = ReviewQueueService(db)
    items = await queue_service.list_review_queue(campaign_id=campaign_id, limit=limit)
    return {"count": len(items), "items": items}


@findings_router.post("/{finding_id}/review")
async def review_finding(
    finding_id: UUID,
    body: FindingReviewRequest,
    db: AsyncSession = Depends(get_db),
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
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 422
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        "finding_id": str(result.finding_id),
        "finding_status": result.finding_status.value,
        "submission_draft_id": str(result.draft_id),
        "submission_draft_status": result.draft_status,
        "campaign_id": str(result.campaign_id),
        "review_timestamp": result.review_timestamp.isoformat(),
    }


@findings_router.post("/{finding_id}/prepare-submission")
async def prepare_submission(
    finding_id: UUID,
    body: PrepareSubmissionRequest,
    db: AsyncSession = Depends(get_db),
):
    service = SubmissionPackageService(db)
    try:
        result = await service.prepare_submission_package(
            finding_id=finding_id,
            prepared_by=body.reviewer_id,
            intention_id=body.intention_id,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 422
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        "finding_id": str(result.finding_id),
        "submission_draft_id": str(result.draft_id),
        "submission_draft_status": result.draft_status,
        "package_json": result.package_json,
    }


router.include_router(campaign_router)
router.include_router(findings_router)
