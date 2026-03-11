from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import (
    ApprovalGate,
    CampaignRun,
    ExecutionBranch,
    PhaseJob,
    SubmissionDraft,
    ToolExecution,
)
from ..models.hil import Finding


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetricsService:
    """Lightweight diagnostics counters backed by canonical persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _count_total(self, model, *, where=None) -> int:
        stmt = select(func.count()).select_from(model)
        if where is not None:
            stmt = stmt.where(where)
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def _count_by_status(self, model, status_column, *, where=None) -> dict[str, int]:
        stmt = select(status_column, func.count()).select_from(model).group_by(status_column)
        if where is not None:
            stmt = stmt.where(where)
        result = await self.db.execute(stmt)
        counts: dict[str, int] = {}
        for status, count in result.all():
            key = status.value if hasattr(status, "value") else str(status)
            counts[key] = int(count)
        return counts

    async def summary_counts(self) -> dict[str, Any]:
        findings_filter = Finding.is_deleted.is_(False)
        return {
            "generated_at": _utcnow_iso(),
            "campaigns": {
                "total": await self._count_total(CampaignRun),
                "by_status": await self._count_by_status(CampaignRun, CampaignRun.status),
            },
            "branches": {
                "total": await self._count_total(ExecutionBranch),
                "by_status": await self._count_by_status(ExecutionBranch, ExecutionBranch.status),
            },
            "phase_jobs": {
                "total": await self._count_total(PhaseJob),
                "by_status": await self._count_by_status(PhaseJob, PhaseJob.status),
            },
            "approval_gates": {
                "total": await self._count_total(ApprovalGate),
                "by_status": await self._count_by_status(ApprovalGate, ApprovalGate.status),
            },
            "tool_executions": {
                "total": await self._count_total(ToolExecution),
                "by_status": await self._count_by_status(ToolExecution, ToolExecution.status),
            },
            "findings": {
                "total": await self._count_total(Finding, where=findings_filter),
                "by_status": await self._count_by_status(
                    Finding,
                    Finding.status,
                    where=findings_filter,
                ),
            },
            "submission_drafts": {
                "total": await self._count_total(SubmissionDraft),
                "by_status": await self._count_by_status(SubmissionDraft, SubmissionDraft.status),
            },
        }
