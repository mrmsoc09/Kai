from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import ApprovalGate
from ..models.enums import ApprovalGateStatusEnum
from ..schemas.campaigns import ApprovalGateCreate, ApprovalGateDecision
from .audit_events import record_transition_event


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


APPROVAL_ALLOWED_TRANSITIONS: dict[ApprovalGateStatusEnum, set[ApprovalGateStatusEnum]] = {
    ApprovalGateStatusEnum.PENDING: {
        ApprovalGateStatusEnum.APPROVED,
        ApprovalGateStatusEnum.REJECTED,
        ApprovalGateStatusEnum.DEFERRED,
        ApprovalGateStatusEnum.EXPIRED,
        ApprovalGateStatusEnum.CANCELED,
    },
    ApprovalGateStatusEnum.DEFERRED: {
        ApprovalGateStatusEnum.PENDING,
        ApprovalGateStatusEnum.APPROVED,
        ApprovalGateStatusEnum.REJECTED,
        ApprovalGateStatusEnum.EXPIRED,
        ApprovalGateStatusEnum.CANCELED,
    },
    ApprovalGateStatusEnum.APPROVED: set(),
    ApprovalGateStatusEnum.REJECTED: set(),
    ApprovalGateStatusEnum.EXPIRED: set(),
    ApprovalGateStatusEnum.CANCELED: set(),
}


def validate_approval_transition(
    current: ApprovalGateStatusEnum,
    target: ApprovalGateStatusEnum,
) -> None:
    if target not in APPROVAL_ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid approval gate transition {current.value} -> {target.value}")


class ApprovalGateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_gate(
        self,
        payload: ApprovalGateCreate,
        *,
        actor: str | None = None,
    ) -> ApprovalGate:
        record = ApprovalGate(
            campaign_id=payload.campaign_id,
            branch_id=payload.branch_id,
            phase_job_id=payload.phase_job_id,
            intention_id=payload.intention_id,
            gate_reason=payload.gate_reason,
            policy_basis=payload.policy_basis,
            risk_class=payload.risk_class,
            requested_by=payload.requested_by,
            expires_at=payload.expires_at,
            operator_notes=payload.operator_notes,
            decision_payload_json=payload.decision_payload_json,
            status=ApprovalGateStatusEnum.PENDING,
        )
        self.db.add(record)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="approval_gate.created",
            actor=actor or payload.requested_by,
            message="Approval gate created",
            campaign_id=record.campaign_id,
            branch_id=record.branch_id,
            phase_job_id=record.phase_job_id,
            approval_gate_id=record.id,
            intention_id=record.intention_id,
            payload={
                "status": record.status.value,
                "reason": record.gate_reason,
                "requested_by": record.requested_by,
            },
        )
        return record

    async def get_gate(self, gate_id: UUID) -> ApprovalGate | None:
        result = await self.db.execute(select(ApprovalGate).where(ApprovalGate.id == gate_id))
        return result.scalar_one_or_none()

    async def list_pending_for_campaign(self, campaign_id: UUID) -> list[ApprovalGate]:
        result = await self.db.execute(
            select(ApprovalGate)
            .where(
                ApprovalGate.campaign_id == campaign_id,
                ApprovalGate.status.in_(
                    [ApprovalGateStatusEnum.PENDING, ApprovalGateStatusEnum.DEFERRED]
                ),
            )
            .order_by(ApprovalGate.requested_at.asc())
        )
        return list(result.scalars().all())

    async def decide_gate(
        self,
        gate: ApprovalGate,
        decision: ApprovalGateDecision,
        *,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> ApprovalGate:
        previous = gate.status
        if previous == decision.status:
            return gate
        validate_approval_transition(gate.status, decision.status)
        gate.status = decision.status
        gate.decided_by = decision.decided_by
        gate.decided_at = _utcnow()
        gate.operator_notes = decision.operator_notes
        gate.decision_payload_json = decision.decision_payload_json
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="approval_gate.status.changed",
            actor=actor or decision.decided_by,
            message=f"Approval gate status {previous.value} -> {decision.status.value}",
            campaign_id=gate.campaign_id,
            branch_id=gate.branch_id,
            phase_job_id=gate.phase_job_id,
            approval_gate_id=gate.id,
            intention_id=intention_id or gate.intention_id,
            payload={"from": previous.value, "to": decision.status.value},
        )
        return gate

    async def cancel_gate(
        self,
        gate: ApprovalGate,
        *,
        actor: str,
        note: str | None = None,
        intention_id: UUID | None = None,
    ) -> ApprovalGate:
        previous = gate.status
        if previous == ApprovalGateStatusEnum.CANCELED:
            return gate
        validate_approval_transition(gate.status, ApprovalGateStatusEnum.CANCELED)
        gate.status = ApprovalGateStatusEnum.CANCELED
        gate.canceled_at = _utcnow()
        gate.canceled_by = actor
        gate.operator_notes = note or gate.operator_notes
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="approval_gate.status.changed",
            actor=actor,
            message=f"Approval gate status {previous.value} -> CANCELED",
            campaign_id=gate.campaign_id,
            branch_id=gate.branch_id,
            phase_job_id=gate.phase_job_id,
            approval_gate_id=gate.id,
            intention_id=intention_id or gate.intention_id,
            payload={"from": previous.value, "to": ApprovalGateStatusEnum.CANCELED.value},
        )
        return gate

    async def expire_gate(
        self,
        gate: ApprovalGate,
        *,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> ApprovalGate:
        previous = gate.status
        if previous == ApprovalGateStatusEnum.EXPIRED:
            return gate
        validate_approval_transition(gate.status, ApprovalGateStatusEnum.EXPIRED)
        gate.status = ApprovalGateStatusEnum.EXPIRED
        gate.decided_at = _utcnow()
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="approval_gate.status.changed",
            actor=actor,
            message=f"Approval gate status {previous.value} -> EXPIRED",
            campaign_id=gate.campaign_id,
            branch_id=gate.branch_id,
            phase_job_id=gate.phase_job_id,
            approval_gate_id=gate.id,
            intention_id=intention_id or gate.intention_id,
            payload={"from": previous.value, "to": ApprovalGateStatusEnum.EXPIRED.value},
        )
        return gate
