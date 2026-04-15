"""Finding collection service for real-time capture of vulnerabilities from scans.

This module captures vulnerability findings as they are discovered and stores them
in the findings database for analytics and tracking.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.findings import ScanFinding, ScanExecution
from ..models.campaign import Program

logger = logging.getLogger(__name__)


class FindingCollector:
    """Captures vulnerability findings from scans and stores them in database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def collect_finding_from_playbook(
        self,
        program_id: UUID,
        scan_id: UUID,
        playbook_result: dict[str, Any],
    ) -> ScanFinding:
        """Capture a vulnerability finding from a playbook execution.

        Args:
            program_id: ID of program being scanned
            scan_id: ID of scan this finding is from
            playbook_result: Dictionary containing:
                - playbook_id: Playbook identifier
                - playbook_name: Human-readable playbook name
                - vulnerability_type: Type (XSS, SQLi, CSRF, etc.)
                - endpoint: Vulnerable endpoint
                - parameter_name: Vulnerable parameter
                - http_method: HTTP method (GET, POST, etc.)
                - payload_used: Exploit payload
                - severity: Assessed severity (critical, high, medium, low)
                - cvss_score: CVSS score (0.0-10.0)
                - description: Finding description
                - proof_of_concept: PoC steps
                - impact: Impact description
                - remediation: Remediation guidance
                - ai_confidence: Confidence score (0.0-1.0)
                - scanning_mode: Mode used (unauthenticated, user_account, api_key, etc.)

        Returns:
            Created ScanFinding object
        """
        # Generate unique identifier for this finding
        finding_id = self._generate_finding_id(program_id, playbook_result)

        # Extract and validate data
        severity = playbook_result.get("severity", "medium")
        cvss_score = playbook_result.get("cvss_score")
        if cvss_score:
            cvss_score = Decimal(str(cvss_score))

        ai_confidence = playbook_result.get("ai_confidence", 0.0)
        if ai_confidence:
            ai_confidence = Decimal(str(ai_confidence))

        # Estimate payout
        estimated_payout = await self._estimate_payout(severity, program_id)

        # Create finding record
        finding = ScanFinding(
            id=uuid4(),
            finding_identifier=finding_id,
            program_id=program_id,
            scan_id=scan_id,
            vulnerability_type=playbook_result["vulnerability_type"],
            severity=severity,
            cvss_score=cvss_score,
            endpoint=playbook_result.get("endpoint"),
            parameter_name=playbook_result.get("parameter_name"),
            http_method=playbook_result.get("http_method"),
            payload_used=playbook_result.get("payload_used"),
            description=playbook_result.get("description", ""),
            proof_of_concept=playbook_result.get("proof_of_concept"),
            impact_description=playbook_result.get("impact"),
            remediation_guidance=playbook_result.get("remediation"),
            estimated_severity=severity,
            estimated_payout=estimated_payout,
            scanning_modes_used=[playbook_result.get("scanning_mode")],
            playbook_id=playbook_result["playbook_id"],
            playbook_name=playbook_result["playbook_name"],
            ai_confidence_score=ai_confidence,
            status="discovered",
            finding_state="valid",
            validation_status="pending_analyst_review",
            discovered_at=datetime.now(timezone.utc),
            created_by="scanner_service",
        )

        self.db.add(finding)
        await self.db.flush()
        await self.db.refresh(finding)

        logger.info(
            f"Finding collected: {finding_id} ({playbook_result['vulnerability_type']}) "
            f"on {program_id}"
        )

        return finding

    def _generate_finding_id(
        self, program_id: UUID, playbook_result: dict[str, Any]
    ) -> str:
        """Generate unique finding identifier."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        vuln_type = playbook_result["vulnerability_type"].lower()[:3]
        endpoint = playbook_result.get("endpoint", "")
        payload = playbook_result.get("payload_used", "")
        hash_val = hashlib.md5(f"{endpoint}{payload}".encode()).hexdigest()[:6]

        return f"{str(program_id)[:8]}-{vuln_type}-{hash_val}-{timestamp}"

    async def _estimate_payout(
        self, severity: str, program_id: UUID
    ) -> Decimal:
        """Estimate payout based on severity and historical data for this program."""
        severity_base = {
            "critical": Decimal("1000.00"),
            "high": Decimal("500.00"),
            "medium": Decimal("200.00"),
            "low": Decimal("100.00"),
        }

        base = severity_base.get(severity, Decimal("100.00"))

        # Adjust based on historical payouts for this program
        program_avg = await self._get_average_payout_for_program(program_id)
        if program_avg and program_avg > 0:
            adjustment = program_avg / Decimal("500.00")
            return base * adjustment

        return base

    async def _get_average_payout_for_program(self, program_id: UUID) -> Optional[Decimal]:
        """Query historical average payout for program."""
        stmt = select(func.avg(ScanFinding.actual_payout)).where(
            (ScanFinding.program_id == program_id)
            & (ScanFinding.actual_payout.isnot(None))
        )
        result = await self.db.scalar(stmt)
        return Decimal(str(result)) if result else None

    async def bulk_collect_findings(
        self,
        program_id: UUID,
        scan_id: UUID,
        playbook_results: list[dict[str, Any]],
    ) -> list[ScanFinding]:
        """Collect multiple findings from a scan in bulk.

        Args:
            program_id: Program ID
            scan_id: Scan ID
            playbook_results: List of playbook result dictionaries

        Returns:
            List of created ScanFinding objects
        """
        findings = []
        for result in playbook_results:
            finding = await self.collect_finding_from_playbook(
                program_id, scan_id, result
            )
            findings.append(finding)

        await self.db.commit()
        return findings

    async def update_scan_finding_counts(self, scan_id: UUID) -> None:
        """Update the scan's finding count aggregates."""
        # Count total findings
        total_stmt = select(func.count(ScanFinding.id)).where(
            ScanFinding.scan_id == scan_id
        )
        total = await self.db.scalar(total_stmt)

        # Count unique (non-duplicate) findings
        unique_stmt = select(func.count(ScanFinding.id)).where(
            (ScanFinding.scan_id == scan_id) & (ScanFinding.is_duplicate == False)
        )
        unique = await self.db.scalar(unique_stmt)

        # Count accepted findings
        accepted_stmt = select(func.count(ScanFinding.id)).where(
            (ScanFinding.scan_id == scan_id) & (ScanFinding.status == "accepted")
        )
        accepted = await self.db.scalar(accepted_stmt)

        # Update scan record
        scan_stmt = select(ScanExecution).where(ScanExecution.id == scan_id)
        scan = await self.db.scalar(scan_stmt)
        if scan:
            scan.total_findings_discovered = total or 0
            await self.db.flush()

        logger.info(
            f"Scan {scan_id}: {total} total, {unique} unique, {accepted} accepted"
        )
