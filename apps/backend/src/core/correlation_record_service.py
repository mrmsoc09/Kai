from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.enums import CorrelationActionEnum
from ..models.workflow import CorrelationRecord


class CorrelationRecordService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(
        self,
        *,
        finding_id: UUID,
        observation_id: UUID,
        campaign_id: UUID,
        action: CorrelationActionEnum,
        correlation_rule: str = "deterministic_title_match",
        confidence: float | None = None,
        duplicate_of_finding_id: UUID | None = None,
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            finding_id=finding_id,
            observation_id=observation_id,
            campaign_id=campaign_id,
            correlation_rule=correlation_rule,
            confidence=confidence,
            action=action,
            duplicate_of_finding_id=duplicate_of_finding_id,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def list_by_finding(self, finding_id: UUID) -> list[CorrelationRecord]:
        result = await self.db.execute(
            select(CorrelationRecord)
            .where(CorrelationRecord.finding_id == finding_id)
            .order_by(CorrelationRecord.correlated_at.asc())
        )
        return list(result.scalars().all())

    async def list_by_campaign(self, campaign_id: UUID) -> list[CorrelationRecord]:
        result = await self.db.execute(
            select(CorrelationRecord)
            .where(CorrelationRecord.campaign_id == campaign_id)
            .order_by(CorrelationRecord.correlated_at.asc())
        )
        return list(result.scalars().all())

    async def list_by_workflow_run(self, workflow_run_id: UUID) -> list[CorrelationRecord]:
        result = await self.db.execute(
            select(CorrelationRecord)
            .where(CorrelationRecord.workflow_run_id == workflow_run_id)
            .order_by(CorrelationRecord.correlated_at.asc())
        )
        return list(result.scalars().all())

    async def list_by_observation(self, observation_id: UUID) -> list[CorrelationRecord]:
        result = await self.db.execute(
            select(CorrelationRecord)
            .where(CorrelationRecord.observation_id == observation_id)
            .order_by(CorrelationRecord.correlated_at.asc())
        )
        return list(result.scalars().all())
