from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import CampaignRun, ExecutionBranch, PhaseJob, Program, ScopeTarget
from ..models.enums import (
    BranchStatusEnum,
    CampaignStatusEnum,
    IntentionSourceEnum,
    IntentionTypeEnum,
    PhaseJobStatusEnum,
)
from ..models.intention import IntentionRecord
from ..schemas.campaigns import (
    CampaignRunCreate,
    CampaignStartRequest,
    ExecutionBranchCreate,
    PhaseJobCreate,
    PhaseSeedSpec,
    ProgramCreate,
    ScopeTargetCreate,
)
from ..schemas.intention import IntentionCreate
from .audit_events import record_transition_event


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_PHASE_GRAPH: tuple[PhaseSeedSpec, ...] = (
    PhaseSeedSpec(
        phase_name="recon_discovery",
        phase_order=10,
        approval_required=False,
        queue_name="campaigns",
        input_payload_json={"dispatch": {"mode": "placeholder"}},
    ),
    PhaseSeedSpec(
        phase_name="target_validation",
        phase_order=20,
        approval_required=False,
        queue_name="campaigns",
        input_payload_json={"dispatch": {"mode": "placeholder"}},
    ),
    PhaseSeedSpec(
        phase_name="lightweight_analysis",
        phase_order=30,
        approval_required=True,
        queue_name="campaigns",
        input_payload_json={"dispatch": {"mode": "placeholder"}},
    ),
)


CAMPAIGN_ALLOWED_TRANSITIONS: dict[CampaignStatusEnum, set[CampaignStatusEnum]] = {
    CampaignStatusEnum.CREATED: {
        CampaignStatusEnum.READY,
        CampaignStatusEnum.CANCELED,
        CampaignStatusEnum.FAILED,
    },
    CampaignStatusEnum.READY: {
        CampaignStatusEnum.RUNNING,
        CampaignStatusEnum.BLOCKED,
        CampaignStatusEnum.PAUSED,
        CampaignStatusEnum.COMPLETED,
        CampaignStatusEnum.CANCELED,
        CampaignStatusEnum.FAILED,
    },
    CampaignStatusEnum.RUNNING: {
        CampaignStatusEnum.PAUSED,
        CampaignStatusEnum.BLOCKED,
        CampaignStatusEnum.COMPLETED,
        CampaignStatusEnum.FAILED,
        CampaignStatusEnum.CANCELED,
    },
    CampaignStatusEnum.PAUSED: {
        CampaignStatusEnum.READY,
        CampaignStatusEnum.RUNNING,
        CampaignStatusEnum.BLOCKED,
        CampaignStatusEnum.CANCELED,
        CampaignStatusEnum.FAILED,
    },
    CampaignStatusEnum.BLOCKED: {
        CampaignStatusEnum.READY,
        CampaignStatusEnum.RUNNING,
        CampaignStatusEnum.PAUSED,
        CampaignStatusEnum.COMPLETED,
        CampaignStatusEnum.CANCELED,
        CampaignStatusEnum.FAILED,
    },
    CampaignStatusEnum.COMPLETED: set(),
    CampaignStatusEnum.FAILED: set(),
    CampaignStatusEnum.CANCELED: set(),
}

BRANCH_ALLOWED_TRANSITIONS: dict[BranchStatusEnum, set[BranchStatusEnum]] = {
    BranchStatusEnum.PENDING: {
        BranchStatusEnum.READY,
        BranchStatusEnum.BLOCKED,
        BranchStatusEnum.CANCELED,
    },
    BranchStatusEnum.READY: {
        BranchStatusEnum.RUNNING,
        BranchStatusEnum.WAITING_APPROVAL,
        BranchStatusEnum.BLOCKED,
        BranchStatusEnum.COMPLETED,
        BranchStatusEnum.CANCELED,
        BranchStatusEnum.FAILED,
    },
    BranchStatusEnum.RUNNING: {
        BranchStatusEnum.WAITING_APPROVAL,
        BranchStatusEnum.BLOCKED,
        BranchStatusEnum.COMPLETED,
        BranchStatusEnum.FAILED,
        BranchStatusEnum.CANCELED,
    },
    BranchStatusEnum.WAITING_APPROVAL: {
        BranchStatusEnum.READY,
        BranchStatusEnum.RUNNING,
        BranchStatusEnum.BLOCKED,
        BranchStatusEnum.COMPLETED,
        BranchStatusEnum.CANCELED,
        BranchStatusEnum.FAILED,
    },
    BranchStatusEnum.BLOCKED: {
        BranchStatusEnum.READY,
        BranchStatusEnum.RUNNING,
        BranchStatusEnum.WAITING_APPROVAL,
        BranchStatusEnum.COMPLETED,
        BranchStatusEnum.CANCELED,
        BranchStatusEnum.FAILED,
    },
    BranchStatusEnum.COMPLETED: set(),
    BranchStatusEnum.FAILED: set(),
    BranchStatusEnum.CANCELED: set(),
}

PHASE_ALLOWED_TRANSITIONS: dict[PhaseJobStatusEnum, set[PhaseJobStatusEnum]] = {
    PhaseJobStatusEnum.CREATED: {
        PhaseJobStatusEnum.QUEUED,
        PhaseJobStatusEnum.WAITING_APPROVAL,
        PhaseJobStatusEnum.BLOCKED,
        PhaseJobStatusEnum.SKIPPED,
        PhaseJobStatusEnum.CANCELED,
    },
    PhaseJobStatusEnum.QUEUED: {
        PhaseJobStatusEnum.RUNNING,
        PhaseJobStatusEnum.WAITING_APPROVAL,
        PhaseJobStatusEnum.BLOCKED,
        PhaseJobStatusEnum.COMPLETED,
        PhaseJobStatusEnum.CANCELED,
        PhaseJobStatusEnum.FAILED,
    },
    PhaseJobStatusEnum.RUNNING: {
        PhaseJobStatusEnum.WAITING_APPROVAL,
        PhaseJobStatusEnum.BLOCKED,
        PhaseJobStatusEnum.COMPLETED,
        PhaseJobStatusEnum.FAILED,
        PhaseJobStatusEnum.CANCELED,
    },
    PhaseJobStatusEnum.WAITING_APPROVAL: {
        PhaseJobStatusEnum.QUEUED,
        PhaseJobStatusEnum.RUNNING,
        PhaseJobStatusEnum.BLOCKED,
        PhaseJobStatusEnum.FAILED,
        PhaseJobStatusEnum.CANCELED,
    },
    PhaseJobStatusEnum.BLOCKED: {
        PhaseJobStatusEnum.QUEUED,
        PhaseJobStatusEnum.RUNNING,
        PhaseJobStatusEnum.WAITING_APPROVAL,
        PhaseJobStatusEnum.FAILED,
        PhaseJobStatusEnum.CANCELED,
    },
    PhaseJobStatusEnum.COMPLETED: set(),
    PhaseJobStatusEnum.FAILED: set(),
    PhaseJobStatusEnum.SKIPPED: set(),
    PhaseJobStatusEnum.CANCELED: set(),
}


def _validate_transition(current_status: str, target_status: str, allowed: dict, entity: str) -> None:
    if current_status not in allowed:
        raise ValueError(f"{entity} has unknown current status: {current_status}")
    if target_status not in allowed[current_status]:
        raise ValueError(f"Invalid {entity} transition {current_status} -> {target_status}")


@dataclass
class CampaignSeedResult:
    campaign: CampaignRun
    root_branch: ExecutionBranch
    phase_jobs: list[PhaseJob]
    intention: IntentionRecord | None
    idempotent_replay: bool


@dataclass
class CampaignRepository:
    db: AsyncSession

    async def add(self, model: object) -> None:
        self.db.add(model)
        await self.db.flush()

    async def get_program(self, program_id: UUID) -> Program | None:
        result = await self.db.execute(select(Program).where(Program.id == program_id))
        return result.scalar_one_or_none()

    async def get_campaign(self, campaign_id: UUID) -> CampaignRun | None:
        result = await self.db.execute(select(CampaignRun).where(CampaignRun.id == campaign_id))
        return result.scalar_one_or_none()

    async def get_campaign_by_idempotency(self, idempotency_key: UUID) -> CampaignRun | None:
        result = await self.db.execute(
            select(CampaignRun).where(CampaignRun.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def get_branch(self, branch_id: UUID) -> ExecutionBranch | None:
        result = await self.db.execute(select(ExecutionBranch).where(ExecutionBranch.id == branch_id))
        return result.scalar_one_or_none()

    async def get_scope_target(
        self,
        program_id: UUID,
        *,
        target: str,
        target_type: str,
    ) -> ScopeTarget | None:
        result = await self.db.execute(
            select(ScopeTarget).where(
                ScopeTarget.program_id == program_id,
                ScopeTarget.target == target,
                ScopeTarget.target_type == target_type,
            )
        )
        return result.scalar_one_or_none()

    async def get_campaign_start_intention(self, campaign_id: UUID) -> IntentionRecord | None:
        result = await self.db.execute(
            select(IntentionRecord)
            .where(
                IntentionRecord.campaign_id == campaign_id,
                IntentionRecord.intention_type == IntentionTypeEnum.CAMPAIGN_START,
            )
            .order_by(IntentionRecord.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_phase_job(self, phase_job_id: UUID) -> PhaseJob | None:
        result = await self.db.execute(select(PhaseJob).where(PhaseJob.id == phase_job_id))
        return result.scalar_one_or_none()

    async def list_branches(self, campaign_id: UUID) -> list[ExecutionBranch]:
        result = await self.db.execute(
            select(ExecutionBranch)
            .where(ExecutionBranch.campaign_id == campaign_id)
            .order_by(ExecutionBranch.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_phase_jobs(
        self,
        campaign_id: UUID,
        branch_id: UUID | None = None,
    ) -> list[PhaseJob]:
        stmt: Select[tuple[PhaseJob]] = (
            select(PhaseJob)
            .where(PhaseJob.campaign_id == campaign_id)
            .order_by(PhaseJob.phase_order.asc(), PhaseJob.created_at.asc())
        )
        if branch_id is not None:
            stmt = stmt.where(PhaseJob.branch_id == branch_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class CampaignService:
    def __init__(self, db: AsyncSession):
        self.repo = CampaignRepository(db=db)

    async def create_program(self, payload: ProgramCreate) -> Program:
        record = Program(
            program_key=payload.program_key,
            name=payload.name,
            platform=payload.platform,
            handle=payload.handle,
            policy_url=payload.policy_url,
            created_by=payload.created_by,
            config_json=payload.config_json,
        )
        await self.repo.add(record)
        return record

    async def create_scope_target(self, payload: ScopeTargetCreate) -> ScopeTarget:
        record = ScopeTarget(
            program_id=payload.program_id,
            target=payload.target,
            target_type=payload.target_type,
            is_in_scope=payload.is_in_scope,
            policy_class=payload.policy_class,
            normalization_key=payload.normalization_key,
            details_json=payload.details_json,
        )
        await self.repo.add(record)
        return record

    async def create_campaign_run(self, payload: CampaignRunCreate) -> CampaignRun:
        record = CampaignRun(
            program_id=payload.program_id,
            primary_scope_target_id=payload.primary_scope_target_id,
            idempotency_key=payload.idempotency_key,
            campaign_name=payload.campaign_name,
            initiated_by=payload.initiated_by,
            declared_goal=payload.declared_goal,
            declared_reason=payload.declared_reason,
            policy_basis=payload.policy_basis,
            risk_class=payload.risk_class,
            approval_required=payload.approval_required,
            run_config_json=payload.run_config_json,
            status=CampaignStatusEnum.CREATED,
        )
        await self.repo.add(record)
        return record

    async def create_execution_branch(self, payload: ExecutionBranchCreate) -> ExecutionBranch:
        record = ExecutionBranch(
            campaign_id=payload.campaign_id,
            parent_branch_id=payload.parent_branch_id,
            depends_on_branch_id=payload.depends_on_branch_id,
            branch_key=payload.branch_key,
            branch_name=payload.branch_name,
            declared_goal=payload.declared_goal,
            policy_basis=payload.policy_basis,
            risk_class=payload.risk_class,
            approval_required=payload.approval_required,
            max_retries=max(0, payload.max_retries),
            branch_config_json=payload.branch_config_json,
            status=BranchStatusEnum.PENDING,
        )
        await self.repo.add(record)
        return record

    async def create_phase_job(self, payload: PhaseJobCreate) -> PhaseJob:
        record = PhaseJob(
            campaign_id=payload.campaign_id,
            branch_id=payload.branch_id,
            depends_on_job_id=payload.depends_on_job_id,
            phase_name=payload.phase_name,
            phase_order=payload.phase_order,
            policy_class=payload.policy_class,
            approval_required=payload.approval_required,
            queue_name=payload.queue_name,
            max_retries=max(0, payload.max_retries),
            input_payload_json=payload.input_payload_json,
            status=PhaseJobStatusEnum.CREATED,
        )
        await self.repo.add(record)
        return record

    async def create_intention(self, payload: IntentionCreate) -> IntentionRecord:
        record = IntentionRecord(
            campaign_id=payload.campaign_id,
            branch_id=payload.branch_id,
            phase_job_id=payload.phase_job_id,
            parent_intention_id=payload.parent_intention_id,
            source=payload.source,
            intention_type=payload.intention_type,
            initiated_by=payload.initiated_by,
            declared_goal=payload.declared_goal,
            declared_reason=payload.declared_reason,
            policy_basis=payload.policy_basis,
            risk_class=payload.risk_class,
            risk_posture_changed=payload.risk_posture_changed,
            approval_required=payload.approval_required,
            approval_reason=payload.approval_reason,
            context_json=payload.context_json,
        )
        await self.repo.add(record)
        return record

    async def transition_campaign_status(
        self,
        campaign: CampaignRun,
        target_status: CampaignStatusEnum,
        *,
        reason: str | None = None,
        canceled_by: str | None = None,
        actor: str | None = None,
        intention_id: UUID | None = None,
        event_payload: dict | None = None,
    ) -> CampaignRun:
        previous = campaign.status
        if previous == target_status:
            return campaign
        _validate_transition(previous.value, target_status.value, CAMPAIGN_ALLOWED_TRANSITIONS, "campaign")

        campaign.status = target_status
        if target_status == CampaignStatusEnum.READY and campaign.queued_at is None:
            campaign.queued_at = _utcnow()
        if target_status == CampaignStatusEnum.RUNNING and campaign.started_at is None:
            campaign.started_at = _utcnow()
        if target_status == CampaignStatusEnum.PAUSED:
            campaign.paused_at = _utcnow()
        if target_status == CampaignStatusEnum.BLOCKED:
            campaign.blocked_reason = reason
        if target_status == CampaignStatusEnum.CANCELED:
            campaign.canceled_at = _utcnow()
            campaign.canceled_by = canceled_by
        if target_status in {CampaignStatusEnum.COMPLETED, CampaignStatusEnum.FAILED}:
            campaign.ended_at = _utcnow()

        await self.repo.db.flush()
        await record_transition_event(
            self.repo.db,
            event_type="campaign.status.changed",
            actor=actor,
            message=f"Campaign status {previous.value} -> {target_status.value}",
            campaign_id=campaign.id,
            intention_id=intention_id,
            payload={
                "from": previous.value,
                "to": target_status.value,
                "reason": reason,
                **(event_payload or {}),
            },
        )
        return campaign

    async def transition_branch_status(
        self,
        branch: ExecutionBranch,
        target_status: BranchStatusEnum,
        *,
        reason: str | None = None,
        canceled_by: str | None = None,
        actor: str | None = None,
        intention_id: UUID | None = None,
        event_payload: dict | None = None,
    ) -> ExecutionBranch:
        previous = branch.status
        if previous == target_status:
            return branch
        _validate_transition(previous.value, target_status.value, BRANCH_ALLOWED_TRANSITIONS, "branch")

        branch.status = target_status
        if target_status == BranchStatusEnum.READY and branch.queued_at is None:
            branch.queued_at = _utcnow()
        if target_status == BranchStatusEnum.RUNNING and branch.started_at is None:
            branch.started_at = _utcnow()
        if target_status in {BranchStatusEnum.WAITING_APPROVAL, BranchStatusEnum.BLOCKED}:
            branch.blocked_reason = reason
        if target_status == BranchStatusEnum.CANCELED:
            branch.canceled_at = _utcnow()
            branch.canceled_by = canceled_by
        if target_status in {BranchStatusEnum.COMPLETED, BranchStatusEnum.FAILED}:
            branch.ended_at = _utcnow()

        await self.repo.db.flush()
        await record_transition_event(
            self.repo.db,
            event_type="branch.status.changed",
            actor=actor,
            message=f"Branch status {previous.value} -> {target_status.value}",
            campaign_id=branch.campaign_id,
            branch_id=branch.id,
            intention_id=intention_id,
            payload={
                "from": previous.value,
                "to": target_status.value,
                "reason": reason,
                **(event_payload or {}),
            },
        )
        return branch

    async def transition_phase_status(
        self,
        phase_job: PhaseJob,
        target_status: PhaseJobStatusEnum,
        *,
        reason: str | None = None,
        canceled_by: str | None = None,
        actor: str | None = None,
        intention_id: UUID | None = None,
        event_payload: dict | None = None,
    ) -> PhaseJob:
        previous = phase_job.status
        if previous == target_status:
            return phase_job
        _validate_transition(previous.value, target_status.value, PHASE_ALLOWED_TRANSITIONS, "phase")

        phase_job.status = target_status
        if target_status == PhaseJobStatusEnum.QUEUED and phase_job.queued_at is None:
            phase_job.queued_at = _utcnow()
        if target_status == PhaseJobStatusEnum.RUNNING and phase_job.started_at is None:
            phase_job.started_at = _utcnow()
        if target_status in {PhaseJobStatusEnum.WAITING_APPROVAL, PhaseJobStatusEnum.BLOCKED}:
            phase_job.blocked_reason = reason
        if target_status == PhaseJobStatusEnum.CANCELED:
            phase_job.canceled_at = _utcnow()
            phase_job.canceled_by = canceled_by
        if target_status in {
            PhaseJobStatusEnum.COMPLETED,
            PhaseJobStatusEnum.FAILED,
            PhaseJobStatusEnum.SKIPPED,
        }:
            phase_job.ended_at = _utcnow()

        await self.repo.db.flush()
        await record_transition_event(
            self.repo.db,
            event_type="phase_job.status.changed",
            actor=actor,
            message=f"Phase job status {previous.value} -> {target_status.value}",
            campaign_id=phase_job.campaign_id,
            branch_id=phase_job.branch_id,
            phase_job_id=phase_job.id,
            intention_id=intention_id,
            payload={
                "from": previous.value,
                "to": target_status.value,
                "reason": reason,
                **(event_payload or {}),
            },
        )
        return phase_job

    async def mark_phase_retry(
        self,
        phase_job: PhaseJob,
        *,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> PhaseJob:
        phase_job.retry_count += 1
        phase_job.status = PhaseJobStatusEnum.QUEUED
        phase_job.error_message = None
        phase_job.queued_at = _utcnow()
        await self.repo.db.flush()
        await record_transition_event(
            self.repo.db,
            event_type="phase_job.retry.queued",
            actor=actor,
            message="Phase job queued for retry",
            campaign_id=phase_job.campaign_id,
            branch_id=phase_job.branch_id,
            phase_job_id=phase_job.id,
            intention_id=intention_id,
            payload={"retry_count": phase_job.retry_count},
        )
        return phase_job


class CampaignStartService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.campaigns = CampaignService(db)
        self.repo = self.campaigns.repo

    def _phase_specs(self, request: CampaignStartRequest) -> Sequence[PhaseSeedSpec]:
        if request.phases:
            phases = list(request.phases)
        else:
            phases = [spec.model_copy(deep=True) for spec in DEFAULT_PHASE_GRAPH]
        for spec in phases:
            if spec.phase_name in request.phase_approval_overrides:
                spec.approval_required = bool(request.phase_approval_overrides[spec.phase_name])
        phases.sort(key=lambda spec: spec.phase_order)
        return phases

    async def _resolve_program(self, request: CampaignStartRequest) -> Program:
        if request.program_id is not None:
            program = await self.repo.get_program(request.program_id)
            if program is None:
                raise ValueError(f"Program not found: {request.program_id}")
            return program
        if not request.program_name:
            raise ValueError("Either program_id or program_name is required")
        return await self.campaigns.create_program(
            ProgramCreate(
                program_key=request.program_key,
                name=request.program_name,
                created_by=request.initiated_by,
                config_json={"created_via": "campaign.start"},
            )
        )

    async def _resolve_scope_target(
        self,
        request: CampaignStartRequest,
        *,
        program: Program,
    ) -> ScopeTarget | None:
        if not request.target:
            return None
        existing = await self.repo.get_scope_target(
            program.id,
            target=request.target,
            target_type=request.target_type,
        )
        if existing is not None:
            return existing
        return await self.campaigns.create_scope_target(
            ScopeTargetCreate(
                program_id=program.id,
                target=request.target,
                target_type=request.target_type,
                is_in_scope=True,
                details_json={"seeded_via": "campaign.start"},
            )
        )

    async def start_campaign(self, request: CampaignStartRequest) -> CampaignSeedResult:
        if request.idempotency_key is not None:
            existing = await self.repo.get_campaign_by_idempotency(request.idempotency_key)
            if existing is not None:
                branches = await self.repo.list_branches(existing.id)
                phase_jobs = await self.repo.list_phase_jobs(existing.id)
                intention = await self.repo.get_campaign_start_intention(existing.id)
                if not branches or not phase_jobs:
                    raise ValueError(
                        f"Idempotent campaign {existing.id} is missing seeded graph records"
                    )
                return CampaignSeedResult(
                    campaign=existing,
                    root_branch=branches[0],
                    phase_jobs=phase_jobs,
                    intention=intention,
                    idempotent_replay=True,
                )

        program = await self._resolve_program(request)
        scope_target = await self._resolve_scope_target(request, program=program)

        campaign = await self.campaigns.create_campaign_run(
            CampaignRunCreate(
                program_id=program.id,
                primary_scope_target_id=scope_target.id if scope_target else None,
                idempotency_key=request.idempotency_key,
                campaign_name=request.campaign_name,
                initiated_by=request.initiated_by,
                declared_goal=request.declared_goal,
                declared_reason=request.declared_reason,
                policy_basis=request.policy_basis,
                risk_class=request.risk_class,
                approval_required=request.approval_required,
                run_config_json=request.run_config_json,
            )
        )

        start_intention = await self.campaigns.create_intention(
            IntentionCreate(
                campaign_id=campaign.id,
                source=IntentionSourceEnum.USER,
                intention_type=IntentionTypeEnum.CAMPAIGN_START,
                initiated_by=request.initiated_by,
                declared_goal=request.declared_goal,
                declared_reason=request.declared_reason,
                policy_basis=request.policy_basis,
                risk_class=request.risk_class,
                approval_required=request.approval_required,
                context_json={
                    "target": request.target,
                    "target_type": request.target_type,
                    "campaign_name": request.campaign_name,
                },
            )
        )

        await record_transition_event(
            self.db,
            event_type="campaign.created",
            actor=request.initiated_by,
            message="Campaign created and seeded",
            campaign_id=campaign.id,
            intention_id=start_intention.id,
            payload={"program_id": str(program.id)},
        )

        root_branch = await self.campaigns.create_execution_branch(
            ExecutionBranchCreate(
                campaign_id=campaign.id,
                branch_key=request.initial_branch_key,
                branch_name=request.initial_branch_name,
                declared_goal=request.declared_goal,
                policy_basis=request.policy_basis,
                risk_class=request.risk_class,
                approval_required=request.approval_required,
                branch_config_json={
                    "target": request.target,
                    "target_type": request.target_type,
                    "seed_intention_id": str(start_intention.id),
                },
            )
        )
        await record_transition_event(
            self.db,
            event_type="branch.seeded",
            actor=request.initiated_by,
            message="Initial branch seeded",
            campaign_id=campaign.id,
            branch_id=root_branch.id,
            intention_id=start_intention.id,
            payload={"branch_key": root_branch.branch_key},
        )

        phase_jobs: list[PhaseJob] = []
        previous_phase_id: UUID | None = None
        phase_id_by_name: dict[str, UUID] = {}
        for spec in self._phase_specs(request):
            depends_on_job_id = previous_phase_id
            if spec.depends_on_phase_name:
                depends_on_job_id = phase_id_by_name.get(spec.depends_on_phase_name)
            seeded_payload = {
                "target": request.target,
                "target_type": request.target_type,
                "seed_intention_id": str(start_intention.id),
            }
            seeded_payload.update(spec.input_payload_json or {})
            phase_job = await self.campaigns.create_phase_job(
                PhaseJobCreate(
                    campaign_id=campaign.id,
                    branch_id=root_branch.id,
                    depends_on_job_id=depends_on_job_id,
                    phase_name=spec.phase_name,
                    phase_order=spec.phase_order,
                    approval_required=spec.approval_required,
                    queue_name=spec.queue_name,
                    input_payload_json=seeded_payload,
                )
            )
            phase_jobs.append(phase_job)
            previous_phase_id = phase_job.id
            phase_id_by_name[phase_job.phase_name] = phase_job.id
            await record_transition_event(
                self.db,
                event_type="phase_job.seeded",
                actor=request.initiated_by,
                message=f"Seeded phase {phase_job.phase_name}",
                campaign_id=campaign.id,
                branch_id=root_branch.id,
                phase_job_id=phase_job.id,
                intention_id=start_intention.id,
                payload={
                    "phase_order": phase_job.phase_order,
                    "approval_required": phase_job.approval_required,
                    "depends_on_job_id": str(phase_job.depends_on_job_id)
                    if phase_job.depends_on_job_id
                    else None,
                },
            )

        await self.campaigns.transition_campaign_status(
            campaign,
            CampaignStatusEnum.READY,
            actor=request.initiated_by,
            intention_id=start_intention.id,
        )
        await self.campaigns.transition_branch_status(
            root_branch,
            BranchStatusEnum.READY,
            actor=request.initiated_by,
            intention_id=start_intention.id,
        )

        return CampaignSeedResult(
            campaign=campaign,
            root_branch=root_branch,
            phase_jobs=phase_jobs,
            intention=start_intention,
            idempotent_replay=False,
        )


def validate_campaign_transition(
    current: CampaignStatusEnum,
    target: CampaignStatusEnum,
) -> None:
    _validate_transition(current.value, target.value, CAMPAIGN_ALLOWED_TRANSITIONS, "campaign")


def validate_branch_transition(current: BranchStatusEnum, target: BranchStatusEnum) -> None:
    _validate_transition(current.value, target.value, BRANCH_ALLOWED_TRANSITIONS, "branch")


def validate_phase_transition(current: PhaseJobStatusEnum, target: PhaseJobStatusEnum) -> None:
    _validate_transition(current.value, target.value, PHASE_ALLOWED_TRANSITIONS, "phase")


def all_terminal_statuses() -> set[str]:
    return {"COMPLETED", "FAILED", "CANCELED", "SKIPPED"}


def is_terminal_status(status: str) -> bool:
    return status in all_terminal_statuses()


def collect_branch_ids(branches: Iterable[ExecutionBranch]) -> list[UUID]:
    return [branch.id for branch in branches]
