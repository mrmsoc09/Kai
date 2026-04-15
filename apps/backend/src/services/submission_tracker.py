"""Submission tracking service for managing platform submissions and payouts.

This module tracks the lifecycle of finding submissions across different
bug bounty platforms and records payout information.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from ..models.findings import ScanFinding, FindingSubmission
from .submission_service import ensure_finding_approved_for_submission

logger = logging.getLogger(__name__)


class SubmissionTracker:
    """Tracks submission lifecycle and payout receipt."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_submission(
        self,
        finding_id: UUID,
        platform: str,
        platform_submission_id: str,
        submission_url: Optional[str] = None,
    ) -> FindingSubmission:
        """Record that a finding has been submitted to a platform.

        Args:
            finding_id: ID of the finding being submitted
            platform: Platform name (h1, intigriti, bugcrowd, direct)
            platform_submission_id: Submission ID assigned by platform
            submission_url: URL to view submission on platform

        Returns:
            Created FindingSubmission object
        """
        finding, validation_error = await ensure_finding_approved_for_submission(self.db, finding_id)
        if validation_error:
            raise ValueError(validation_error["message"])

        now = datetime.now(timezone.utc)

        submission = FindingSubmission(
            id=uuid4(),
            finding_id=finding_id,
            submitted_to_platform=platform,
            platform_submission_id=platform_submission_id,
            submission_url=submission_url,
            current_status="pending",
            status_history=[
                {
                    "status": "pending",
                    "timestamp": now.isoformat(),
                    "notes": "Submission recorded",
                }
            ],
            submitted_at=now,
            created_by="submission_service",
        )

        self.db.add(submission)
        await self.db.flush()
        await self.db.refresh(submission)

        if finding:
            finding.status = "submitted"
            finding.submitted_to_platform = platform
            finding.submission_id = platform_submission_id
            finding.submission_status = "pending"
            finding.submitted_at = now
            finding.updated_by = "submission_service"
            finding.last_updated_at = now

        logger.info(
            f"Submission recorded: {platform} submission #{platform_submission_id} "
            f"for finding {finding_id}"
        )

        return submission

    async def update_submission_status(
        self,
        finding_id: UUID,
        platform: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> FindingSubmission:
        """Update the status of a submission.

        Args:
            finding_id: Finding ID
            platform: Platform name
            new_status: New status (pending, accepted, rejected, duplicate, out_of_scope, paid)
            notes: Optional notes about the status change

        Returns:
            Updated FindingSubmission object
        """
        stmt = select(FindingSubmission).where(
            (FindingSubmission.finding_id == finding_id)
            & (FindingSubmission.submitted_to_platform == platform)
        )
        submission = await self.db.scalar(stmt)

        if not submission:
            raise ValueError(
                f"Submission not found for finding {finding_id} on platform {platform}"
            )

        if submission.current_status != new_status:
            # Add to status history
            history = list(submission.status_history or [])
            history.append(
                {
                    "status": new_status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": notes or "",
                }
            )

            submission.current_status = new_status
            submission.status_history = history
            submission.updated_by = "status_checker_service"
            submission.last_updated_at = datetime.now(timezone.utc)

            # Mark the status_history as modified for SQLAlchemy
            attributes.flag_modified(submission, "status_history")

            await self.db.flush()
            await self.db.refresh(submission)

            logger.info(
                f"Submission status updated: {finding_id} on {platform} → {new_status}"
            )

        return submission

    async def record_payout(
        self,
        finding_id: UUID,
        platform: str,
        payout_amount: Decimal | float,
        payout_currency: str = "USD",
    ) -> tuple[ScanFinding, FindingSubmission]:
        """Record that payout was received for a finding.

        Args:
            finding_id: Finding ID
            platform: Platform where payout was received
            payout_amount: Amount paid
            payout_currency: Currency code (default: USD)

        Returns:
            Tuple of (updated ScanFinding, updated FindingSubmission)
        """
        # Convert to Decimal
        amount = Decimal(str(payout_amount))

        # Get finding
        finding_stmt = select(ScanFinding).where(ScanFinding.id == finding_id)
        finding = await self.db.scalar(finding_stmt)
        if not finding:
            raise ValueError(f"Finding {finding_id} not found")

        # Record payout on finding
        finding.actual_payout = amount
        finding.payout_received_at = datetime.now(timezone.utc)
        finding.payout_currency = payout_currency
        finding.status = "paid"

        # Calculate accuracy
        if finding.estimated_payout and finding.estimated_payout > 0:
            accuracy = (amount / finding.estimated_payout) * 100
            finding.payout_accuracy_percentage = accuracy
            logger.info(
                f"Payout accuracy: {accuracy:.1f}% "
                f"(estimated ${finding.estimated_payout}, received ${amount})"
            )

        # Update submission status
        submission_stmt = select(FindingSubmission).where(
            (FindingSubmission.finding_id == finding_id)
            & (FindingSubmission.submitted_to_platform == platform)
        )
        submission = await self.db.scalar(submission_stmt)
        if submission:
            submission.payout_amount = amount
            submission.payout_currency = payout_currency
            submission.payout_received_at = datetime.now(timezone.utc)
            submission.current_status = "paid"

            # Add to status history
            history = list(submission.status_history or [])
            history.append(
                {
                    "status": "paid",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": f"Payout received: ${amount} {payout_currency}",
                }
            )
            submission.status_history = history
            # Mark the status_history as modified for SQLAlchemy
            attributes.flag_modified(submission, "status_history")

        await self.db.flush()

        if submission:
            await self.db.refresh(submission)
        await self.db.refresh(finding)

        return finding, submission if submission else None

    async def get_submission_status(
        self, finding_id: UUID, platform: str
    ) -> Optional[dict[str, Any]]:
        """Get current status of a submission.

        Args:
            finding_id: Finding ID
            platform: Platform name

        Returns:
            Dictionary with submission status or None if not found
        """
        stmt = select(FindingSubmission).where(
            (FindingSubmission.finding_id == finding_id)
            & (FindingSubmission.submitted_to_platform == platform)
        )
        submission = await self.db.scalar(stmt)

        if not submission:
            return None

        return {
            "platform": platform,
            "status": submission.current_status,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "payout_amount": float(submission.payout_amount) if submission.payout_amount else None,
            "payout_currency": submission.payout_currency,
            "payout_received_at": submission.payout_received_at.isoformat()
            if submission.payout_received_at
            else None,
            "status_history": submission.status_history or [],
        }

    async def list_submissions_for_finding(
        self, finding_id: UUID
    ) -> list[FindingSubmission]:
        """Get all submissions for a finding.

        Args:
            finding_id: Finding ID

        Returns:
            List of FindingSubmission objects
        """
        stmt = select(FindingSubmission).where(
            FindingSubmission.finding_id == finding_id
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_pending_submissions(self, limit: int = 100) -> list[FindingSubmission]:
        """Get all pending submissions across all platforms.

        Args:
            limit: Maximum number to return

        Returns:
            List of pending FindingSubmission objects
        """
        stmt = (
            select(FindingSubmission)
            .where(FindingSubmission.current_status == "pending")
            .limit(limit)
        )
        result = await self.db.scalars(stmt)
        return list(result.all())
