"""Validation queue manager for analyst review workflow."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.findings import ScanFinding
from .false_positive_detector import FalsePositiveDetector
from .finding_override_service import FindingOverrideService

logger = logging.getLogger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ValidationQueueManager:
    """Manage findings awaiting analyst validation decisions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.detector = FalsePositiveDetector()
        self.override_service = FindingOverrideService(db)

    async def get_validation_queue(self, analyst_id: str) -> dict[str, Any]:
        stmt = (
            select(ScanFinding)
            .where(
                or_(
                    ScanFinding.validation_status == "pending_analyst_review",
                    ScanFinding.validation_status.is_(None),
                )
            )
            .order_by(desc(ScanFinding.cvss_score), desc(ScanFinding.discovered_at))
        )
        result = await self.db.scalars(stmt)
        findings = list(result.all())

        queue_items: list[dict[str, Any]] = []
        for finding in findings:
            heuristic_input = {
                "vulnerability_type": finding.vulnerability_type,
                "endpoint": finding.endpoint,
                "description": finding.description,
                "proof_of_concept": finding.proof_of_concept,
                "payload_used": finding.payload_used,
            }
            fp_confidence, fp_reason = await self.detector.analyze_finding_for_false_positive(
                str(finding.id), heuristic_input
            )
            queue_items.append(
                {
                    "finding_id": str(finding.id),
                    "vulnerability_type": finding.vulnerability_type,
                    "severity": finding.severity,
                    "cvss_score": _to_float(finding.cvss_score),
                    "endpoint": finding.endpoint,
                    "parameter": finding.parameter_name,
                    "payload": finding.payload_used,
                    "description": finding.description,
                    "proof_of_concept": finding.proof_of_concept,
                    "confidence_score": _to_float(finding.ai_confidence_score),
                    "estimated_payout": _to_float(finding.estimated_payout),
                    "false_positive_confidence": fp_confidence,
                    "false_positive_reason": fp_reason,
                }
            )

        return {
            "analyst_id": analyst_id,
            "queue_size": len(queue_items),
            "findings": queue_items,
        }

    async def submit_analyst_review(
        self,
        finding_id: str,
        decision: str,
        reason: str,
        notes: str,
        analyst_id: str,
    ) -> dict[str, Any]:
        normalized = decision.strip().lower()
        if normalized == "approve":
            return await self.override_service.approve_finding(finding_id, notes, analyst_id)
        if normalized == "exclude":
            return await self.override_service.exclude_finding(
                finding_id=finding_id,
                reason=reason or "Analyst marked false positive",
                analyst_notes=notes,
                analyst_id=analyst_id,
            )
        if normalized == "force_include":
            return await self.override_service.force_include_finding(
                finding_id=finding_id,
                analyst_notes=notes,
                analyst_id=analyst_id,
            )
        return {"error": f"Unknown decision: {decision}"}

    async def get_queue_stats(self) -> dict[str, Any]:
        pending = await self.db.scalar(
            select(func.count(ScanFinding.id)).where(
                or_(
                    ScanFinding.validation_status == "pending_analyst_review",
                    ScanFinding.validation_status.is_(None),
                )
            )
        )
        approved = await self.db.scalar(
            select(func.count(ScanFinding.id)).where(
                ScanFinding.validation_status == "approved_for_submission"
            )
        )
        excluded = await self.db.scalar(
            select(func.count(ScanFinding.id)).where(
                ScanFinding.validation_status == "excluded"
            )
        )

        pending_i = int(pending or 0)
        approved_i = int(approved or 0)
        excluded_i = int(excluded or 0)
        return {
            "pending_review": pending_i,
            "approved_for_submission": approved_i,
            "excluded": excluded_i,
            "total_findings": pending_i + approved_i + excluded_i,
        }
