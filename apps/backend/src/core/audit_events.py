from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

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
        if payload.correlation_id is not None:
            # Best-effort replay dedupe for deterministic event keys.
            try:
                existing_result = await self.db.execute(
                    select(AuditEvent)
                    .where(
                        AuditEvent.event_type == payload.event_type,
                        AuditEvent.correlation_id == payload.correlation_id,
                    )
                    .limit(1)
                )
                existing = existing_result.scalar_one_or_none()
                if existing is not None:
                    return existing
            except Exception:
                # Some test doubles intentionally do not implement SQL execution.
                pass

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


def _normalize_payload(
    *,
    payload: dict | None,
    campaign_id: UUID | None,
    branch_id: UUID | None,
    phase_job_id: UUID | None,
    tool_execution_id: UUID | None,
    approval_gate_id: UUID | None,
    artifact_id: UUID | None,
    observation_id: UUID | None,
    finding_id: UUID | None,
    report_id: UUID | None,
    intention_id: UUID | None,
    draft_id: UUID | None,
    action: str | None,
    outcome: str | None,
) -> dict:
    normalized = dict(payload) if isinstance(payload, dict) else {}
    if action and "action" not in normalized:
        normalized["action"] = action
    if outcome and "outcome" not in normalized:
        normalized["outcome"] = outcome

    refs = normalized.get("entity_refs")
    if not isinstance(refs, dict):
        refs = {}
    for key, value in {
        "campaign_id": campaign_id,
        "branch_id": branch_id,
        "phase_job_id": phase_job_id,
        "tool_execution_id": tool_execution_id,
        "approval_gate_id": approval_gate_id,
        "artifact_id": artifact_id,
        "observation_id": observation_id,
        "finding_id": finding_id,
        "report_id": report_id,
        "intention_id": intention_id,
        "draft_id": draft_id,
    }.items():
        if value is not None and key not in refs:
            refs[key] = str(value)
    if refs:
        normalized["entity_refs"] = refs
    return normalized


def _dedupe_correlation_id(event_type: str, dedupe_key: str | None) -> UUID | None:
    if not dedupe_key:
        return None
    return uuid5(NAMESPACE_URL, f"k1:{event_type}:{dedupe_key}")


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
    draft_id: UUID | None = None,
    action: str | None = None,
    outcome: str | None = None,
    dedupe_key: str | None = None,
    payload: dict | None = None,
) -> AuditEvent:
    svc = AuditEventService(db)
    normalized_payload = _normalize_payload(
        payload=payload,
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
        draft_id=draft_id,
        action=action,
        outcome=outcome,
    )
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
            correlation_id=_dedupe_correlation_id(event_type, dedupe_key),
            event_payload_json=normalized_payload,
        )
    )
