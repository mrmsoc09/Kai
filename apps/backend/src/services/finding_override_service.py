"""Analyst override service for inclusion/exclusion decisions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.finding_overrides import FindingOverride
from ..models.findings import ScanFinding

logger = logging.getLogger(__name__)


def _to_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


class FindingOverrideService:
    """Manage analyst override decisions with immutable audit logging."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def exclude_finding(
        self,
        finding_id: str,
        reason: str,
        analyst_notes: str,
        analyst_id: str,
    ) -> dict[str, Any]:
        finding_uuid = _to_uuid(finding_id)
        finding = await self.db.scalar(select(ScanFinding).where(ScanFinding.id == finding_uuid))
        if not finding:
            return {"error": "Finding not found", "finding_id": finding_id}

        finding.validation_status = "excluded"
        finding.finding_state = "false_positive"
        finding.analyst_notes = analyst_notes
        finding.updated_by = analyst_id
        finding.last_updated_at = datetime.now(timezone.utc)

        override = FindingOverride(
            finding_id=finding_uuid,
            override_decision="exclude",
            reason=reason,
            analyst_notes=analyst_notes,
            overridden_by=analyst_id,
            immutable=True,
        )

        self.db.add(override)
        await self.db.commit()

        logger.info("Finding %s excluded by analyst %s (%s)", finding_id, analyst_id, reason)
        return {
            "status": "success",
            "finding_id": finding_id,
            "decision": "excluded",
            "reason": reason,
        }

    async def force_include_finding(
        self,
        finding_id: str,
        analyst_notes: str,
        analyst_id: str,
    ) -> dict[str, Any]:
        finding_uuid = _to_uuid(finding_id)
        finding = await self.db.scalar(select(ScanFinding).where(ScanFinding.id == finding_uuid))
        if not finding:
            return {"error": "Finding not found", "finding_id": finding_id}

        finding.validation_status = "approved_for_submission"
        finding.finding_state = "valid"
        finding.analyst_notes = analyst_notes
        finding.updated_by = analyst_id
        finding.last_updated_at = datetime.now(timezone.utc)

        override = FindingOverride(
            finding_id=finding_uuid,
            override_decision="force_include",
            reason="Analyst override - include finding",
            analyst_notes=analyst_notes,
            overridden_by=analyst_id,
            immutable=True,
        )

        self.db.add(override)
        await self.db.commit()

        logger.info("Finding %s force-included by analyst %s", finding_id, analyst_id)
        return {
            "status": "success",
            "finding_id": finding_id,
            "decision": "force_included",
            "message": "Finding approved for submission",
        }

    async def approve_finding(
        self, finding_id: str, analyst_notes: str, analyst_id: str
    ) -> dict[str, Any]:
        """Approve finding without override semantics."""
        finding_uuid = _to_uuid(finding_id)
        finding = await self.db.scalar(select(ScanFinding).where(ScanFinding.id == finding_uuid))
        if not finding:
            return {"error": "Finding not found", "finding_id": finding_id}

        finding.validation_status = "approved_for_submission"
        finding.finding_state = "valid"
        finding.analyst_notes = analyst_notes
        finding.updated_by = analyst_id
        finding.last_updated_at = datetime.now(timezone.utc)

        override = FindingOverride(
            finding_id=finding_uuid,
            override_decision="approve",
            reason="Analyst approved finding for submission",
            analyst_notes=analyst_notes,
            overridden_by=analyst_id,
            immutable=True,
        )

        self.db.add(override)
        await self.db.commit()

        return {
            "status": "success",
            "finding_id": finding_id,
            "decision": "approved_for_submission",
        }

    async def batch_approve_findings(
        self, finding_ids: list[str], analyst_id: str
    ) -> dict[str, Any]:
        """Approve many findings in one transaction."""
        if not finding_ids:
            return {"status": "batch_approval_complete", "approved": 0, "failed": 0, "total": 0}

        parsed_ids: list[UUID] = []
        for finding_id in finding_ids:
            try:
                parsed_ids.append(_to_uuid(finding_id))
            except Exception:
                continue

        result = await self.db.scalars(select(ScanFinding).where(ScanFinding.id.in_(parsed_ids)))
        findings = list(result.all())
        found_ids = {f.id for f in findings}

        approved_count = 0
        now = datetime.now(timezone.utc)
        for finding in findings:
            finding.validation_status = "approved_for_submission"
            finding.finding_state = "valid"
            finding.updated_by = analyst_id
            finding.last_updated_at = now
            approved_count += 1
            self.db.add(
                FindingOverride(
                    finding_id=finding.id,
                    override_decision="approve",
                    reason="Batch approved by analyst",
                    analyst_notes="Batch approval",
                    overridden_by=analyst_id,
                    immutable=True,
                )
            )

        await self.db.commit()

        failed_count = len(parsed_ids) - len(found_ids)
        logger.info(
            "Batch approval by %s: %d approved, %d failed", analyst_id, approved_count, failed_count
        )
        return {
            "status": "batch_approval_complete",
            "approved": approved_count,
            "failed": failed_count,
            "total": len(finding_ids),
        }

