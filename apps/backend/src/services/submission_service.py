"""Submission guardrails ensuring only analyst-approved findings are submitted."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.findings import FindingSubmission, ScanFinding

logger = logging.getLogger(__name__)


def _as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


async def ensure_finding_approved_for_submission(
    db: AsyncSession, finding_id: str | UUID
) -> tuple[Optional[ScanFinding], Optional[dict[str, Any]]]:
    """Validate that a finding is eligible for submission."""
    finding_uuid = _as_uuid(finding_id)
    finding = await db.scalar(select(ScanFinding).where(ScanFinding.id == finding_uuid))
    if not finding:
        return None, {"error": "Finding not found", "finding_id": str(finding_id)}

    if finding.validation_status == "excluded":
        return finding, {
            "error": "Finding is excluded",
            "status": finding.validation_status,
            "message": "Excluded findings cannot be submitted",
        }

    if finding.validation_status != "approved_for_submission":
        return finding, {
            "error": "Finding not approved for submission",
            "status": finding.validation_status or "pending_analyst_review",
            "message": "Analyst must approve before submission",
        }

    return finding, None


class SubmissionService:
    """Create platform submission records after validation gate checks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_finding_to_platform(
        self,
        finding_id: str | UUID,
        platform: str,
        platform_submission_id: Optional[str] = None,
        submission_url: Optional[str] = None,
        created_by: str = "submission_service",
    ) -> dict[str, Any]:
        finding, validation_error = await ensure_finding_approved_for_submission(self.db, finding_id)
        if validation_error:
            return validation_error

        now = datetime.now(timezone.utc)
        submission = FindingSubmission(
            id=uuid4(),
            finding_id=finding.id,
            submitted_to_platform=platform,
            platform_submission_id=platform_submission_id,
            submission_url=submission_url,
            submitted_at=now,
            current_status="pending",
            status_history=[
                {"status": "pending", "timestamp": now.isoformat(), "notes": "Submitted after analyst approval"}
            ],
            created_by=created_by,
        )

        finding.status = "submitted"
        finding.submitted_to_platform = platform
        finding.submission_id = platform_submission_id
        finding.submission_status = "pending"
        finding.submitted_at = now
        finding.updated_by = created_by
        finding.last_updated_at = now

        self.db.add(submission)
        await self.db.commit()

        logger.info("Finding %s submitted to %s after approval", finding.id, platform)
        return {
            "status": "submitted",
            "finding_id": str(finding.id),
            "platform": platform,
            "submission_id": str(submission.id),
            "platform_submission_id": platform_submission_id,
        }

