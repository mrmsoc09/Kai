from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import AuditEvent
from ..schemas.campaigns import AuditEventCreate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, payload: AuditEventCreate) -> AuditEvent:
        event = AuditEvent(
            campaign_id=payload.campaign_id,
            branch_id=payload.branch_id,
            phase_job_id=payload.phase_job_id,
            tool_execution_id=payload.tool_execution_id,
            approval_gate_id=payload.approval_gate_id,
            artifact_id=payload.artifact_id,
            observation_id=payload.observation_id,
            finding_id=payload.finding_id,
            report_id=payload.report_id,
            intention_id=payload.intention_id,
            event_type=payload.event_type,
            actor=payload.actor,
            message=payload.message,
            policy_basis=payload.policy_basis,
            policy_class=payload.policy_class,
            risk_posture_changed=payload.risk_posture_changed,
            happened_at=payload.happened_at or _utcnow(),
            correlation_id=payload.correlation_id,
            event_payload_json=payload.event_payload_json,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def list_campaign_events(
        self,
        campaign_id: UUID,
        *,
        limit: int = 500,
    ) -> list[AuditEvent]:
        result = await self.db.execute(
            select(AuditEvent)
            .where(AuditEvent.campaign_id == campaign_id)
            .order_by(AuditEvent.happened_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_branch_events(
        self,
        branch_id: UUID,
        *,
        limit: int = 500,
    ) -> list[AuditEvent]:
        result = await self.db.execute(
            select(AuditEvent)
            .where(AuditEvent.branch_id == branch_id)
            .order_by(AuditEvent.happened_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def record_transition_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor: str | None,
    message: str | None,
    campaign_id: UUID | None = None,
    branch_id: UUID | None = None,
    phase_job_id: UUID | None = None,
    tool_execution_id: UUID | None = None,
    approval_gate_id: UUID | None = None,
    artifact_id: UUID | None = None,
    observation_id: UUID | None = None,
    finding_id: UUID | None = None,
    report_id: UUID | None = None,
    intention_id: UUID | None = None,
    payload: dict | None = None,
) -> AuditEvent:
    svc = AuditEventService(db)
    return await svc.create_event(
        AuditEventCreate(
            event_type=event_type,
            actor=actor,
            message=message,
            campaign_id=campaign_id,
            branch_id=branch_id,
            phase_job_id=phase_job_id,
            tool_execution_id=tool_execution_id,
            approval_gate_id=approval_gate_id,
            artifact_id=artifact_id,
            observation_id=observation_id,
            finding_id=finding_id,
            report_id=report_id,
            intention_id=intention_id,
            event_payload_json=payload or {},
        )
    )
