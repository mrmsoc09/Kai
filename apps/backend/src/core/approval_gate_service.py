from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.models import Tenant
from ..models.approval_evidence_link import ApprovalEvidenceLink
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

    async def _resolve_tenant_id(self, tenant_id: UUID | None) -> UUID:
        if tenant_id is not None:
            return tenant_id
        try:
            result = await self.db.execute(select(Tenant.id).order_by(Tenant.created_at.asc()).limit(1))
            resolved = result.scalar_one_or_none()
            if resolved is not None:
                return resolved
        except Exception:
            pass
        return UUID(int=0)

    async def _latest_gate_for_scope(self, payload: ApprovalGateCreate, tenant_id: UUID) -> ApprovalGate | None:
        try:
            stmt = (
                select(ApprovalGate)
                .where(
                    ApprovalGate.campaign_id == payload.campaign_id,
                    ApprovalGate.tenant_id == tenant_id
                )
                .order_by(ApprovalGate.created_at.desc())
                .limit(1)
            )
            if payload.phase_job_id is not None:
                stmt = stmt.where(ApprovalGate.phase_job_id == payload.phase_job_id)
            elif payload.branch_id is not None:
                stmt = stmt.where(
                    ApprovalGate.branch_id == payload.branch_id,
                    ApprovalGate.gate_reason == payload.gate_reason,
                )
            else:
                stmt = stmt.where(
                    ApprovalGate.gate_reason == payload.gate_reason,
                    ApprovalGate.requested_by == payload.requested_by,
                )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def create_gate(
        self,
        payload: ApprovalGateCreate,
        tenant_id: UUID | None = None,
        *,
        actor: str | None = None,
    ) -> ApprovalGate:
        resolved_tenant_id = await self._resolve_tenant_id(tenant_id)
        existing = await self._latest_gate_for_scope(payload, resolved_tenant_id)
        if existing is not None:
            await record_transition_event(
                self.db,
                event_type="approval_gate.reused",
                actor=actor or payload.requested_by,
                message="Existing approval gate reused instead of creating duplicate",
                campaign_id=existing.campaign_id,
                branch_id=existing.branch_id,
                phase_job_id=existing.phase_job_id,
                approval_gate_id=existing.id,
                intention_id=existing.intention_id,
                action="create_approval_gate",
                outcome="reused_existing",
                dedupe_key=f"{existing.id}:reuse",
                payload={"status": existing.status.value, "reason": existing.gate_reason},
            )
            return existing

        record = ApprovalGate(
            campaign_id=payload.campaign_id,
            tenant_id=resolved_tenant_id,
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
            action="create_approval_gate",
            outcome="created",
            payload={
                "status": record.status.value,
                "reason": record.gate_reason,
                "requested_by": record.requested_by,
            },
        )
        return record

    async def get_gate(self, gate_id: UUID, tenant_id: UUID | None = None) -> ApprovalGate | None:
        resolved_tenant_id = await self._resolve_tenant_id(tenant_id)
        result = await self.db.execute(select(ApprovalGate).where(
            ApprovalGate.id == gate_id,
            ApprovalGate.tenant_id == resolved_tenant_id
        ))
        return result.scalar_one_or_none()

    async def list_pending_for_campaign(self, campaign_id: UUID, tenant_id: UUID | None = None) -> list[ApprovalGate]:
        resolved_tenant_id = await self._resolve_tenant_id(tenant_id)
        result = await self.db.execute(
            select(ApprovalGate)
            .where(
                ApprovalGate.campaign_id == campaign_id,
                ApprovalGate.tenant_id == resolved_tenant_id,
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
        # Enforce reviewer_intention before any transition checks so this guard
        # cannot be bypassed by reordering or future additions to the method.
        if decision.status == ApprovalGateStatusEnum.APPROVED:
            if not decision.reviewer_intention or not decision.reviewer_intention.strip():
                raise ValueError(
                    "reviewer_intention is required when approving a gate: "
                    f"gate_id={gate.id} campaign_id={gate.campaign_id}"
                )
        previous = gate.status
        if previous == decision.status:
            await record_transition_event(
                self.db,
                event_type="approval_gate.decision.duplicate",
                actor=actor or decision.decided_by,
                message="Duplicate approval decision ignored",
                campaign_id=gate.campaign_id,
                branch_id=gate.branch_id,
                phase_job_id=gate.phase_job_id,
                approval_gate_id=gate.id,
                intention_id=intention_id or gate.intention_id,
                action="decide_approval_gate",
                outcome="ignored_duplicate",
                dedupe_key=f"{gate.id}:decision:{decision.status.value}",
                payload={"status": decision.status.value},
            )
            return gate
        try:
            validate_approval_transition(gate.status, decision.status)
        except ValueError as exc:
            await record_transition_event(
                self.db,
                event_type="approval_gate.decision.conflict",
                actor=actor or decision.decided_by,
                message=str(exc),
                campaign_id=gate.campaign_id,
                branch_id=gate.branch_id,
                phase_job_id=gate.phase_job_id,
                approval_gate_id=gate.id,
                intention_id=intention_id or gate.intention_id,
                action="decide_approval_gate",
                outcome="conflict",
                dedupe_key=f"{gate.id}:decision-conflict:{decision.status.value}",
                payload={"from": gate.status.value, "to": decision.status.value},
            )
            raise
        gate.status = decision.status
        gate.decided_by = decision.decided_by
        gate.decided_at = _utcnow()
        gate.operator_notes = decision.operator_notes
        gate.decision_payload_json = decision.decision_payload_json
        gate.reviewer_intention = decision.reviewer_intention
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
            action="decide_approval_gate",
            outcome="applied",
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
            await record_transition_event(
                self.db,
                event_type="approval_gate.decision.duplicate",
                actor=actor,
                message="Cancel request ignored; gate already canceled",
                campaign_id=gate.campaign_id,
                branch_id=gate.branch_id,
                phase_job_id=gate.phase_job_id,
                approval_gate_id=gate.id,
                intention_id=intention_id or gate.intention_id,
                action="cancel_approval_gate",
                outcome="ignored_duplicate",
                dedupe_key=f"{gate.id}:cancel-already-canceled",
            )
            return gate
        try:
            validate_approval_transition(gate.status, ApprovalGateStatusEnum.CANCELED)
        except ValueError as exc:
            await record_transition_event(
                self.db,
                event_type="approval_gate.decision.conflict",
                actor=actor,
                message=str(exc),
                campaign_id=gate.campaign_id,
                branch_id=gate.branch_id,
                phase_job_id=gate.phase_job_id,
                approval_gate_id=gate.id,
                intention_id=intention_id or gate.intention_id,
                action="cancel_approval_gate",
                outcome="conflict",
                dedupe_key=f"{gate.id}:cancel-conflict",
                payload={"from": gate.status.value, "to": ApprovalGateStatusEnum.CANCELED.value},
            )
            raise
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
            action="cancel_approval_gate",
            outcome="applied",
            payload={"from": previous.value, "to": ApprovalGateStatusEnum.CANCELED.value},
        )
        return gate

    async def link_approval_to_evidence(
        self,
        gate_id: UUID,
        linked_by: str,
        *,
        evidence_id: UUID | None = None,
        validation_id: UUID | None = None,
        reason: str | None = None,
        tenant_id: UUID | None = None,
    ) -> ApprovalEvidenceLink:
        """Create an ApprovalEvidenceLink connecting *gate_id* to evidence/validation.

        Fetches the gate to copy ``reviewer_intention`` into the immutable
        ``reviewer_intention_snapshot`` field on the link record.

        Raises ``LookupError`` when the gate is not found.
        """
        import logging
        logger = logging.getLogger(__name__)

        gate = await self.get_gate(gate_id, tenant_id=tenant_id)
        if gate is None:
            raise LookupError(
                f"ApprovalGate not found: gate_id={gate_id}"
            )

        link = ApprovalEvidenceLink(
            approval_gate_id=gate_id,
            evidence_id=evidence_id,
            validation_id=validation_id,
            campaign_id=gate.campaign_id,
            linked_by=linked_by,
            link_reason=reason,
            reviewer_intention_snapshot=gate.reviewer_intention,
        )
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        logger.info(
            "approval_evidence_link.created id=%s gate_id=%s evidence_id=%s validation_id=%s actor=%s",
            link.id,
            gate_id,
            evidence_id,
            validation_id,
            linked_by,
        )
        return link

    async def expire_gate(
        self,
        gate: ApprovalGate,
        *,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> ApprovalGate:
        previous = gate.status
        if previous == ApprovalGateStatusEnum.EXPIRED:
            await record_transition_event(
                self.db,
                event_type="approval_gate.decision.duplicate",
                actor=actor,
                message="Expire request ignored; gate already expired",
                campaign_id=gate.campaign_id,
                branch_id=gate.branch_id,
                phase_job_id=gate.phase_job_id,
                approval_gate_id=gate.id,
                intention_id=intention_id or gate.intention_id,
                action="expire_approval_gate",
                outcome="ignored_duplicate",
                dedupe_key=f"{gate.id}:expire-already-expired",
            )
            return gate
        try:
            validate_approval_transition(gate.status, ApprovalGateStatusEnum.EXPIRED)
        except ValueError as exc:
            await record_transition_event(
                self.db,
                event_type="approval_gate.decision.conflict",
                actor=actor,
                message=str(exc),
                campaign_id=gate.campaign_id,
                branch_id=gate.branch_id,
                phase_job_id=gate.phase_job_id,
                approval_gate_id=gate.id,
                intention_id=intention_id or gate.intention_id,
                action="expire_approval_gate",
                outcome="conflict",
                dedupe_key=f"{gate.id}:expire-conflict",
                payload={"from": gate.status.value, "to": ApprovalGateStatusEnum.EXPIRED.value},
            )
            raise
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
            action="expire_approval_gate",
            outcome="applied",
            payload={"from": previous.value, "to": ApprovalGateStatusEnum.EXPIRED.value},
        )
        return gate
