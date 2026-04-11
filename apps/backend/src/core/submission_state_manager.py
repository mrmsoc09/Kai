"""
Submission state management and deduplication tracking.
Tracks which CVEs have been submitted to which targets on which platforms.
Prevents duplicate submissions and maintains submission history.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class SubmissionStatus(str, Enum):
    """Submission lifecycle status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    TRIAGED = "triaged"
    ACCEPTED = "accepted"
    BOUNTY_AWARDED = "bounty_awarded"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


@dataclass
class SubmissionRecord:
    """Record of a vulnerability submission."""

    submission_id: str
    platform: str
    target: str
    cve_id: str
    title: str
    submitted_at: str
    platform_submission_id: Optional[str] = None
    submission_url: Optional[str] = None
    status: SubmissionStatus = SubmissionStatus.SUBMITTED
    last_status_check: Optional[str] = None
    latest_status: Optional[str] = None
    bounty_amount: Optional[float] = None
    evidence_hashes: Set[str] = field(default_factory=set)
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "submission_id": self.submission_id,
            "platform": self.platform,
            "target": self.target,
            "cve_id": self.cve_id,
            "title": self.title,
            "submitted_at": self.submitted_at,
            "platform_submission_id": self.platform_submission_id,
            "submission_url": self.submission_url,
            "status": self.status.value,
            "last_status_check": self.last_status_check,
            "latest_status": self.latest_status,
            "bounty_amount": self.bounty_amount,
            "evidence_hashes": list(self.evidence_hashes),
            "rejection_reason": self.rejection_reason,
            "notes": self.notes,
        }


class SubmissionStateManager:
    """
    Manages submission state and prevents duplicate submissions.
    Tracks submissions across multiple platforms with status updates.
    """

    def __init__(self, storage_backend=None):
        """
        Initialize submission state manager.

        Args:
            storage_backend: Optional storage backend (Redis, database, etc.)
        """
        self.storage_backend = storage_backend
        self.submissions: Dict[str, SubmissionRecord] = {}
        self._submission_index: Dict[str, Set[str]] = {}

    async def register_submission(
        self,
        platform: str,
        target: str,
        cve_id: str,
        title: str,
        evidence_hashes: Optional[Set[str]] = None,
    ) -> str:
        """
        Register a new submission attempt.

        Args:
            platform: Target platform
            target: Target URL
            cve_id: CVE identifier
            title: Submission title
            evidence_hashes: SHA256 hashes of associated evidence

        Returns:
            Unique submission ID
        """
        # Generate submission ID
        submission_id = self._generate_submission_id(
            platform, target, cve_id
        )

        record = SubmissionRecord(
            submission_id=submission_id,
            platform=platform,
            target=target,
            cve_id=cve_id,
            title=title,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            evidence_hashes=evidence_hashes or set(),
        )

        self.submissions[submission_id] = record

        # Update index for quick lookups
        index_key = f"{platform}:{target}:{cve_id}"
        if index_key not in self._submission_index:
            self._submission_index[index_key] = set()
        self._submission_index[index_key].add(submission_id)

        logger.info(
            f"Registered submission {submission_id} for {cve_id} on {target}"
        )
        return submission_id

    async def mark_submitted(
        self,
        submission_id: str,
        platform_submission_id: Optional[str] = None,
        submission_url: Optional[str] = None,
    ) -> None:
        """
        Mark submission as successfully submitted to platform.

        Args:
            submission_id: Submission ID
            platform_submission_id: ID from platform
            submission_url: URL to view submission
        """
        if submission_id not in self.submissions:
            logger.error(f"Unknown submission ID: {submission_id}")
            return

        record = self.submissions[submission_id]
        record.status = SubmissionStatus.SUBMITTED
        record.platform_submission_id = platform_submission_id
        record.submission_url = submission_url
        record.last_status_check = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Marked submission {submission_id} as submitted "
            f"({record.platform}:{record.cve_id})"
        )

    async def check_duplicate_submission(
        self, platform: str, target: str, cve_id: str
    ) -> bool:
        """
        Check if CVE has been submitted to target on platform.

        Args:
            platform: Target platform
            target: Target URL
            cve_id: CVE identifier

        Returns:
            True if already submitted
        """
        index_key = f"{platform}:{target}:{cve_id}"
        existing = self._submission_index.get(index_key, set())

        for submission_id in existing:
            record = self.submissions.get(submission_id)
            if record and record.status != SubmissionStatus.REJECTED:
                logger.warning(
                    f"Found existing submission {submission_id} for "
                    f"{cve_id} on {target}/{platform}"
                )
                return True

        return False

    async def update_submission_status(
        self,
        submission_id: str,
        platform_status: Optional[str] = None,
        new_status: Optional[SubmissionStatus] = None,
        bounty_amount: Optional[float] = None,
        rejection_reason: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[SubmissionRecord]:
        """
        Update submission status after platform check.

        Args:
            submission_id: Submission ID
            platform_status: Status from platform
            new_status: New status to set
            bounty_amount: Bounty awarded (if applicable)
            rejection_reason: Reason for rejection (if rejected)
            notes: Additional notes

        Returns:
            Updated SubmissionRecord or None if not found
        """
        if submission_id not in self.submissions:
            logger.error(f"Unknown submission ID: {submission_id}")
            return None

        record = self.submissions[submission_id]
        record.latest_status = platform_status
        record.last_status_check = datetime.now(
            timezone.utc
        ).isoformat()

        if new_status:
            record.status = new_status

        if bounty_amount:
            record.bounty_amount = bounty_amount

        if rejection_reason:
            record.rejection_reason = rejection_reason

        if notes:
            record.notes = notes

        logger.info(
            f"Updated submission {submission_id} status to "
            f"{new_status or record.status}"
        )

        return record

    def get_submission_history(
        self,
        cve_id: Optional[str] = None,
        target: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> list[SubmissionRecord]:
        """
        Get submission history with optional filtering.

        Args:
            cve_id: Filter by CVE ID
            target: Filter by target URL
            platform: Filter by platform

        Returns:
            List of matching submission records
        """
        results = []

        for record in self.submissions.values():
            if cve_id and record.cve_id != cve_id:
                continue
            if target and record.target != target:
                continue
            if platform and record.platform != platform:
                continue

            results.append(record)

        return sorted(
            results, key=lambda r: r.submitted_at, reverse=True
        )

    def get_submission_stats(self) -> Dict[str, Any]:
        """Get submission statistics."""
        by_status = {}
        by_platform = {}
        by_cve = {}
        total_bounty = 0.0

        for record in self.submissions.values():
            # By status
            status_str = record.status.value
            by_status[status_str] = by_status.get(status_str, 0) + 1

            # By platform
            by_platform[record.platform] = (
                by_platform.get(record.platform, 0) + 1
            )

            # By CVE
            by_cve[record.cve_id] = by_cve.get(record.cve_id, 0) + 1

            # Total bounty
            if record.bounty_amount:
                total_bounty += record.bounty_amount

        return {
            "total_submissions": len(self.submissions),
            "by_status": by_status,
            "by_platform": by_platform,
            "by_cve": by_cve,
            "total_bounty_awarded": total_bounty,
            "accepted_count": by_status.get(
                SubmissionStatus.ACCEPTED.value, 0
            ),
            "rejected_count": by_status.get(
                SubmissionStatus.REJECTED.value, 0
            ),
            "duplicate_count": by_status.get(
                SubmissionStatus.DUPLICATE.value, 0
            ),
        }

    async def mark_duplicate(
        self, submission_id: str, duplicate_of: Optional[str] = None
    ) -> None:
        """
        Mark submission as duplicate.

        Args:
            submission_id: Submission ID
            duplicate_of: Original submission ID (if known)
        """
        if submission_id not in self.submissions:
            logger.error(f"Unknown submission ID: {submission_id}")
            return

        record = self.submissions[submission_id]
        record.status = SubmissionStatus.DUPLICATE
        if duplicate_of:
            record.notes = f"Duplicate of {duplicate_of}"

        logger.info(f"Marked submission {submission_id} as duplicate")

    async def cleanup_stale_submissions(self, days: int = 90) -> int:
        """
        Remove submissions older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of submissions removed
        """
        cutoff = datetime.now(timezone.utc)
        cutoff_seconds = days * 86400

        removed = 0
        to_remove = []

        for submission_id, record in self.submissions.items():
            submitted_time = datetime.fromisoformat(
                record.submitted_at
            )
            age_seconds = (cutoff - submitted_time).total_seconds()

            if age_seconds > cutoff_seconds:
                to_remove.append(submission_id)

        for submission_id in to_remove:
            del self.submissions[submission_id]
            removed += 1

        logger.info(
            f"Removed {removed} stale submissions older than {days} days"
        )
        return removed

    @staticmethod
    def _generate_submission_id(
        platform: str, target: str, cve_id: str
    ) -> str:
        """Generate unique submission ID."""
        combined = f"{platform}:{target}:{cve_id}:{datetime.now(timezone.utc).isoformat()}"
        hash_obj = hashlib.sha256(combined.encode())
        return f"sub_{hash_obj.hexdigest()[:16]}"

    async def export_submissions(
        self, format: str = "json"
    ) -> Dict[str, Any] | str:
        """
        Export all submissions.

        Args:
            format: Export format ('json', 'csv')

        Returns:
            Exported data
        """
        if format == "json":
            return {
                "submissions": [
                    r.to_dict() for r in self.submissions.values()
                ],
                "stats": self.get_submission_stats(),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }
        elif format == "csv":
            import csv
            from io import StringIO

            output = StringIO()
            fieldnames = [
                "submission_id",
                "platform",
                "target",
                "cve_id",
                "status",
                "submitted_at",
                "bounty_amount",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for record in self.submissions.values():
                writer.writerow(
                    {
                        "submission_id": record.submission_id,
                        "platform": record.platform,
                        "target": record.target,
                        "cve_id": record.cve_id,
                        "status": record.status.value,
                        "submitted_at": record.submitted_at,
                        "bounty_amount": record.bounty_amount or "",
                    }
                )

            return output.getvalue()

        raise ValueError(f"Unsupported export format: {format}")
