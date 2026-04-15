"""DB-backed emergency kill switch for scans.

Allows analysts to request scan abort anytime. Uses database persistence
so abort requests survive process restarts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.findings import ScanExecution

logger = logging.getLogger(__name__)


class ScanKillSwitch:
    """DB-backed emergency abort mechanism.

    Analysts can request scan abort anytime. Abort flags are persisted
    in database, so state survives restarts and is accessible to any
    process that can query the DB.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def request_scan_abort(
        self, scan_id: str | UUID, reason: str, requested_by: str
    ) -> dict[str, Any]:
        """Compatibility alias for directive wording."""
        return await self.request_abort(scan_id=scan_id, reason=reason, requested_by=requested_by)

    async def request_abort(
        self, scan_id: str | UUID, reason: str, requested_by: str
    ) -> dict[str, Any]:
        """Analyst requests scan abort.

        Args:
            scan_id: Scan ID to abort
            reason: Human-readable reason for abort
            requested_by: User ID who requested the abort

        Returns:
            Dict with status and details
        """
        scan_id_str = str(scan_id) if isinstance(scan_id, UUID) else scan_id

        try:
            # Load scan (convert string to UUID if needed)
            scan_uuid = UUID(scan_id_str) if isinstance(scan_id_str, str) else scan_id_str
            stmt = select(ScanExecution).where(ScanExecution.id == scan_uuid)
            result = await self.db.execute(stmt)
            scan = result.scalars().first()

            if not scan:
                return {"error": "Scan not found", "scan_id": scan_id_str}

            # Set abort flags
            scan.abort_requested = True
            scan.abort_requested_by = requested_by
            scan.abort_requested_at = datetime.now(timezone.utc)
            scan.abort_reason = reason

            await self.db.commit()

            logger.warning(
                f"KILL SWITCH REQUESTED for scan {scan_id_str} by {requested_by}: {reason}"
            )

            return {
                "status": "kill_switch_activated",
                "scan_id": scan_id_str,
                "message": "Scan will be aborted at next safe checkpoint",
                "requested_by": requested_by,
                "requested_at": scan.abort_requested_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to request abort for scan {scan_id_str}: {e}")
            return {"error": str(e), "scan_id": scan_id_str}

    async def is_abort_requested(self, scan_id: str | UUID) -> bool:
        """Check if kill switch was activated for this scan.

        Fast read - called frequently during scans.

        Args:
            scan_id: Scan ID to check

        Returns:
            True if abort has been requested, False otherwise
        """
        scan_id_str = str(scan_id) if isinstance(scan_id, UUID) else scan_id

        try:
            # Fast read of abort_requested flag
            scan_uuid = UUID(scan_id_str) if isinstance(scan_id_str, str) else scan_id_str
            stmt = select(ScanExecution.abort_requested).where(
                ScanExecution.id == scan_uuid
            )
            result = await self.db.execute(stmt)
            abort_requested = result.scalars().first()

            return abort_requested or False

        except Exception as e:
            logger.error(f"Failed to check abort status for scan {scan_id_str}: {e}")
            return False

    async def check_kill_switch(self, scan_id: str | UUID) -> bool:
        """Compatibility alias for directive wording."""
        return await self.is_abort_requested(scan_id)

    async def complete_abort(self, scan_id: str | UUID) -> dict[str, Any]:
        """Complete the abort - mark scan as aborted.

        Called after the scan has actually stopped running.

        Args:
            scan_id: Scan ID to mark as aborted

        Returns:
            Dict with abort status and details
        """
        scan_id_str = str(scan_id) if isinstance(scan_id, UUID) else scan_id

        try:
            # Load scan (convert string to UUID if needed)
            scan_uuid = UUID(scan_id_str) if isinstance(scan_id_str, str) else scan_id_str
            stmt = select(ScanExecution).where(ScanExecution.id == scan_uuid)
            result = await self.db.execute(stmt)
            scan = result.scalars().first()

            if not scan:
                return {"error": "Scan not found", "scan_id": scan_id_str}

            # Mark as aborted
            scan.status = "cancelled"  # Use existing "cancelled" status
            scan.completion_status = "kill_switch_activated"
            scan.completed_at = datetime.now(timezone.utc)

            await self.db.commit()

            logger.info(f"Scan {scan_id_str} aborted via kill switch")

            return {
                "status": "aborted",
                "scan_id": scan_id_str,
                "reason": scan.abort_reason,
                "completed_at": scan.completed_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to complete abort for scan {scan_id_str}: {e}")
            return {"error": str(e), "scan_id": scan_id_str}

    async def abort_scan_safely(self, scan_id: str | UUID) -> dict[str, Any]:
        """Compatibility alias for directive wording."""
        return await self.complete_abort(scan_id)

    async def get_abort_info(self, scan_id: str | UUID) -> Optional[dict[str, Any]]:
        """Get details about an abort request (if any).

        Args:
            scan_id: Scan ID to query

        Returns:
            Dict with abort details, or None if no abort requested
        """
        scan_id_str = str(scan_id) if isinstance(scan_id, UUID) else scan_id

        try:
            # Load scan (convert string to UUID if needed)
            scan_uuid = UUID(scan_id_str) if isinstance(scan_id_str, str) else scan_id_str
            stmt = select(ScanExecution).where(ScanExecution.id == scan_uuid)
            result = await self.db.execute(stmt)
            scan = result.scalars().first()

            if not scan or not scan.abort_requested:
                return None

            return {
                "abort_requested": True,
                "requested_by": scan.abort_requested_by,
                "requested_at": scan.abort_requested_at.isoformat() if scan.abort_requested_at else None,
                "reason": scan.abort_reason,
            }

        except Exception as e:
            logger.error(f"Failed to get abort info for scan {scan_id_str}: {e}")
            return None
