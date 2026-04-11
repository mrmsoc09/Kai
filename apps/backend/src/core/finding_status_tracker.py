"""
Finding Status Tracker — Non-Blocking Hunter-Reviewer Loop.

Manages the lifecycle of findings as they flow through:
DETECTED → EVIDENCE_COLLECTING → AWAITING_REVIEW → APPROVED/REJECTED

Enables concurrent processing of multiple findings without blocking
the main scanner loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class FindingStatusEnum(str, Enum):
    """Finding lifecycle states."""
    DETECTED = "detected"                   # Finding identified by tool
    EVIDENCE_COLLECTING = "evidence_collecting"  # Recording/scripts/bundling in progress
    AWAITING_REVIEW = "awaiting_review"    # Awaiting HiL approval
    APPROVED = "approved"                   # Approved via PGP signature
    REJECTED = "rejected"                   # Rejected by reviewer
    EXPIRED = "expired"                     # Approval window expired
    SUBMITTED = "submitted"                 # Submitted to platform


@dataclass
class FindingStatus:
    """Finding status record."""
    finding_id: str
    task_id: str
    status: FindingStatusEnum
    target_url: str
    vulnerability_type: str
    severity: str
    tool_name: str
    detected_at: str  # ISO 8601 timestamp
    evidence_started_at: Optional[str] = None
    evidence_completed_at: Optional[str] = None
    awaiting_review_at: Optional[str] = None
    approver_id: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    submitted_at: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FindingStatus:
        """Create from dictionary."""
        data['status'] = FindingStatusEnum(data['status'])
        return cls(**data)


class FindingStatusTracker:
    """
    Concurrent finding status tracker.

    Tracks multiple findings in flight simultaneously, allowing:
    - Independent evidence collection for each finding
    - Non-blocking scanner loop (continues while evidence is being collected)
    - Status queries without locking the scanner
    - Immutable audit trail
    """

    def __init__(self, db_path: str = "output/logs/finding_status.jsonl"):
        """
        Initialize tracker with JSONL backend (append-only log).

        Args:
            db_path: Path to finding_status.jsonl log file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # Thread-safe writes
        self._in_memory: Dict[str, FindingStatus] = {}  # Cache for fast lookups

        # Load existing records
        self._load_from_disk()

        logger.info(f"FindingStatusTracker initialized: {self.db_path}")

    def _load_from_disk(self) -> None:
        """Load all findings from JSONL log file."""
        if not self.db_path.exists():
            return

        try:
            with open(self.db_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        status = FindingStatus.from_dict(data)
                        self._in_memory[status.finding_id] = status
            logger.info(f"Loaded {len(self._in_memory)} existing findings from disk")
        except Exception as e:
            logger.error(f"Error loading finding status from disk: {e}")

    def _write_to_disk(self, status: FindingStatus) -> None:
        """Append finding status to JSONL log (atomic)."""
        try:
            with self._lock:
                with open(self.db_path, 'a') as f:
                    f.write(json.dumps(status.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Error writing finding status to disk: {e}")

    async def create_finding(
        self,
        task_id: str,
        target_url: str,
        vulnerability_type: str,
        severity: str,
        tool_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FindingStatus:
        """
        Create a new finding record in DETECTED state.

        Args:
            task_id: Task identifier
            target_url: Target URL
            vulnerability_type: Type of vulnerability
            severity: Severity level
            tool_name: Tool that detected it
            metadata: Additional metadata

        Returns:
            FindingStatus object
        """
        finding_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        status = FindingStatus(
            finding_id=finding_id,
            task_id=task_id,
            status=FindingStatusEnum.DETECTED,
            target_url=target_url,
            vulnerability_type=vulnerability_type,
            severity=severity,
            tool_name=tool_name,
            detected_at=now,
            metadata=metadata or {},
        )

        self._in_memory[finding_id] = status
        self._write_to_disk(status)

        logger.info(f"✓ Finding created: {finding_id} ({vulnerability_type} @ {target_url})")
        return status

    async def start_evidence_collection(self, finding_id: str) -> bool:
        """
        Mark finding as EVIDENCE_COLLECTING.

        Args:
            finding_id: Finding identifier

        Returns:
            True if successful
        """
        if finding_id not in self._in_memory:
            logger.error(f"Finding not found: {finding_id}")
            return False

        status = self._in_memory[finding_id]
        now = datetime.now(timezone.utc).isoformat()

        status.status = FindingStatusEnum.EVIDENCE_COLLECTING
        status.evidence_started_at = now

        self._write_to_disk(status)
        logger.info(f"→ Finding {finding_id}: EVIDENCE_COLLECTING")
        return True

    async def complete_evidence_collection(self, finding_id: str) -> bool:
        """
        Mark finding as AWAITING_REVIEW (evidence complete).

        Args:
            finding_id: Finding identifier

        Returns:
            True if successful
        """
        if finding_id not in self._in_memory:
            logger.error(f"Finding not found: {finding_id}")
            return False

        status = self._in_memory[finding_id]
        now = datetime.now(timezone.utc).isoformat()

        status.status = FindingStatusEnum.AWAITING_REVIEW
        status.evidence_completed_at = now
        status.awaiting_review_at = now

        self._write_to_disk(status)
        logger.warning(f"⏸️  Finding {finding_id}: AWAITING_REVIEW (PGP signature required)")
        return True

    async def approve_finding(
        self,
        finding_id: str,
        approver_id: str,
    ) -> bool:
        """
        Mark finding as APPROVED (by human reviewer).

        Args:
            finding_id: Finding identifier
            approver_id: ID of approver

        Returns:
            True if successful
        """
        if finding_id not in self._in_memory:
            logger.error(f"Finding not found: {finding_id}")
            return False

        status = self._in_memory[finding_id]
        now = datetime.now(timezone.utc).isoformat()

        status.status = FindingStatusEnum.APPROVED
        status.approver_id = approver_id
        status.approved_at = now

        self._write_to_disk(status)
        logger.info(f"✅ Finding {finding_id}: APPROVED by {approver_id}")
        return True

    async def reject_finding(
        self,
        finding_id: str,
        rejection_reason: str,
    ) -> bool:
        """
        Mark finding as REJECTED.

        Args:
            finding_id: Finding identifier
            rejection_reason: Reason for rejection

        Returns:
            True if successful
        """
        if finding_id not in self._in_memory:
            logger.error(f"Finding not found: {finding_id}")
            return False

        status = self._in_memory[finding_id]
        status.status = FindingStatusEnum.REJECTED
        status.rejection_reason = rejection_reason

        self._write_to_disk(status)
        logger.error(f"❌ Finding {finding_id}: REJECTED ({rejection_reason})")
        return True

    async def mark_submitted(self, finding_id: str) -> bool:
        """
        Mark finding as SUBMITTED to platform.

        Args:
            finding_id: Finding identifier

        Returns:
            True if successful
        """
        if finding_id not in self._in_memory:
            logger.error(f"Finding not found: {finding_id}")
            return False

        status = self._in_memory[finding_id]
        now = datetime.now(timezone.utc).isoformat()

        status.status = FindingStatusEnum.SUBMITTED
        status.submitted_at = now

        self._write_to_disk(status)
        logger.info(f"🚀 Finding {finding_id}: SUBMITTED to platform")
        return True

    async def get_finding(self, finding_id: str) -> Optional[FindingStatus]:
        """Get finding by ID."""
        return self._in_memory.get(finding_id)

    async def get_findings_by_status(self, status: FindingStatusEnum) -> list[FindingStatus]:
        """Get all findings in a specific status."""
        return [f for f in self._in_memory.values() if f.status == status]

    async def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        by_status = {}
        for status_enum in FindingStatusEnum:
            count = len([f for f in self._in_memory.values() if f.status == status_enum])
            by_status[status_enum.value] = count

        return {
            "total_findings": len(self._in_memory),
            "by_status": by_status,
            "in_progress": len([f for f in self._in_memory.values()
                               if f.status in (FindingStatusEnum.EVIDENCE_COLLECTING,
                                             FindingStatusEnum.AWAITING_REVIEW)]),
        }

    async def export_findings(self) -> list[Dict[str, Any]]:
        """Export all findings as list of dicts."""
        return [f.to_dict() for f in self._in_memory.values()]


# Global singleton
_tracker: Optional[FindingStatusTracker] = None


async def get_finding_status_tracker() -> FindingStatusTracker:
    """Get or create global finding status tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = FindingStatusTracker()
    return _tracker
