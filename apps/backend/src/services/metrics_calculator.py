"""Metrics calculation service for analytics and insights.

This module calculates all analytics metrics for dashboards including
program performance, playbook effectiveness, vulnerability distribution,
and ROI analysis.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.findings import ScanFinding, FindingSubmission, ScanExecution

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates analytics metrics for dashboards and insights."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_program_metrics(self, program_id: UUID) -> dict[str, Any]:
        """Calculate all metrics for a specific program.

        Args:
            program_id: Program ID

        Returns:
            Dictionary with comprehensive program metrics
        """
        # Get findings
        findings_stmt = select(ScanFinding).where(
            ScanFinding.program_id == program_id
        )
        findings_result = await self.db.scalars(findings_stmt)
        findings = list(findings_result.all())

        total_findings = len(findings)
        unique_findings = sum(1 for f in findings if not f.is_duplicate)
        duplicate_findings = total_findings - unique_findings

        # Get submissions
        submissions_stmt = (
            select(FindingSubmission)
            .join(ScanFinding)
            .where(ScanFinding.program_id == program_id)
        )
        submissions_result = await self.db.scalars(submissions_stmt)
        submissions = list(submissions_result.all())

        accepted_submissions = [s for s in submissions if s.current_status == "accepted"]
        paid_submissions = [s for s in submissions if s.current_status == "paid"]

        total_payout = sum(
            s.payout_amount or Decimal("0") for s in paid_submissions
        )
        total_estimated = sum(
            f.estimated_payout or Decimal("0") for f in findings
        )

        acceptance_rate = (
            (len(accepted_submissions) / len(submissions) * 100)
            if submissions
            else 0
        )

        payout_accuracy = (
            float(total_payout / total_estimated * 100)
            if total_estimated > 0
            else 0
        )

        avg_confidence = (
            sum(
                float(f.ai_confidence_score or 0) for f in findings
            ) / len(findings)
            if findings
            else 0
        )

        return {
            "program_id": str(program_id),
            "metrics": {
                "total_findings": total_findings,
                "unique_findings": unique_findings,
                "duplicate_findings": duplicate_findings,
                "findings_submitted": len(submissions),
                "findings_accepted": len(accepted_submissions),
                "findings_paid": len(paid_submissions),
                "acceptance_rate": round(acceptance_rate, 2),
                "total_payout_received": float(total_payout),
                "total_payout_estimated": float(total_estimated),
                "payout_accuracy_percentage": round(payout_accuracy, 2),
                "average_ai_confidence": round(avg_confidence, 3),
                "roi": {
                    "estimated_roi": float(total_estimated),
                    "actual_roi": float(total_payout),
                    "efficiency_percentage": round(payout_accuracy, 2),
                },
            },
        }

    async def calculate_playbook_performance(self) -> list[dict[str, Any]]:
        """Calculate performance metrics for each playbook.

        Returns:
            List of playbook performance dictionaries
        """
        playbook_stats_stmt = (
            select(
                ScanFinding.playbook_id,
                ScanFinding.playbook_name,
                func.count(ScanFinding.id).label("total_findings"),
                func.sum(
                    case(
                        (ScanFinding.is_duplicate == False, 1),
                        else_=0,
                    )
                ).label("unique_findings"),
                func.avg(ScanFinding.ai_confidence_score).label("avg_confidence"),
                func.sum(ScanFinding.actual_payout).label("total_payout"),
                func.count(
                    func.distinct(
                        case(
                            (FindingSubmission.current_status == "accepted", 1),
                            else_=None,
                        )
                    )
                ).label("accepted_count"),
            )
            .outerjoin(
                FindingSubmission, ScanFinding.id == FindingSubmission.finding_id
            )
            .group_by(ScanFinding.playbook_id, ScanFinding.playbook_name)
            .order_by(func.sum(ScanFinding.actual_payout).desc().nullslast())
        )

        result = await self.db.execute(playbook_stats_stmt)
        stats = result.all()

        playbook_performance = []
        for stat in stats:
            playbook_id, playbook_name, total, unique, avg_conf, total_payout, accepted = stat

            acceptance_rate = (
                (float(accepted) / float(total) * 100) if total else 0
            )

            playbook_performance.append(
                {
                    "playbook_id": playbook_id,
                    "playbook_name": playbook_name,
                    "total_findings": total or 0,
                    "unique_findings": unique or 0,
                    "duplicate_findings": (total or 0) - (unique or 0),
                    "average_confidence": round(float(avg_conf or 0), 3),
                    "total_payout": float(total_payout or 0),
                    "acceptance_rate": round(acceptance_rate, 2),
                    "accepted_findings": accepted or 0,
                    "roi_per_playbook": float(total_payout or 0),
                }
            )

        return playbook_performance

    async def calculate_vulnerability_distribution(self) -> dict[str, Any]:
        """Get distribution of vulnerability types found.

        Returns:
            Dictionary with vulnerability type distribution
        """
        vuln_stmt = (
            select(
                ScanFinding.vulnerability_type,
                func.count(ScanFinding.id).label("count"),
                func.sum(
                    case(
                        (ScanFinding.is_duplicate == False, 1),
                        else_=0,
                    )
                ).label("unique_count"),
                func.avg(ScanFinding.cvss_score).label("avg_cvss"),
                func.max(ScanFinding.cvss_score).label("max_cvss"),
                func.min(ScanFinding.cvss_score).label("min_cvss"),
                func.sum(ScanFinding.actual_payout).label("total_payout"),
                func.count(
                    func.distinct(
                        case(
                            (FindingSubmission.current_status == "accepted", 1),
                            else_=None,
                        )
                    )
                ).label("accepted_count"),
            )
            .outerjoin(
                FindingSubmission, ScanFinding.id == FindingSubmission.finding_id
            )
            .group_by(ScanFinding.vulnerability_type)
            .order_by(func.sum(ScanFinding.actual_payout).desc().nullslast())
        )

        result = await self.db.execute(vuln_stmt)
        stats = result.all()

        distribution = []
        for stat in stats:
            (
                vuln_type,
                count,
                unique,
                avg_cvss,
                max_cvss,
                min_cvss,
                total_payout,
                accepted,
            ) = stat

            acceptance_rate = (
                (float(accepted) / float(count) * 100) if count else 0
            )

            distribution.append(
                {
                    "vulnerability_type": vuln_type,
                    "total_count": count or 0,
                    "unique_count": unique or 0,
                    "average_cvss": round(float(avg_cvss or 0), 1),
                    "max_cvss": round(float(max_cvss or 0), 1),
                    "min_cvss": round(float(min_cvss or 0), 1),
                    "total_payout": float(total_payout or 0),
                    "accepted_findings": accepted or 0,
                    "acceptance_rate": round(acceptance_rate, 2),
                }
            )

        return {
            "vulnerability_distribution": distribution,
            "total_vulnerability_types": len(distribution),
        }

    async def calculate_scan_effectiveness(
        self, scan_id: UUID
    ) -> dict[str, Any]:
        """Calculate effectiveness metrics for a specific scan.

        Args:
            scan_id: Scan ID

        Returns:
            Dictionary with scan effectiveness metrics
        """
        # Get scan
        scan_stmt = select(ScanExecution).where(ScanExecution.id == scan_id)
        scan = await self.db.scalar(scan_stmt)
        if not scan:
            return {"error": f"Scan {scan_id} not found"}

        # Get findings for this scan
        findings_stmt = select(ScanFinding).where(ScanFinding.scan_id == scan_id)
        findings_result = await self.db.scalars(findings_stmt)
        findings = list(findings_result.all())

        total_findings = len(findings)
        unique_findings = sum(1 for f in findings if not f.is_duplicate)
        valid_findings = sum(1 for f in findings if f.finding_state == "valid")
        false_positives = sum(
            1 for f in findings if f.finding_state == "false_positive"
        )

        # Get valuable findings (accepted or paid)
        valuable_findings = sum(
            1 for f in findings if f.status in ["accepted", "paid"]
        )

        total_payout = sum(
            f.actual_payout or Decimal("0") for f in findings
        )
        avg_confidence = (
            sum(float(f.ai_confidence_score or 0) for f in findings) / total_findings
            if findings
            else 0
        )

        # Calculate payout per second (efficiency metric)
        duration = scan.duration_seconds or 1
        payout_per_second = float(total_payout) / duration if duration > 0 else 0

        return {
            "scan_id": str(scan_id),
            "scan_name": scan.scan_name,
            "metrics": {
                "total_findings": total_findings,
                "unique_findings": unique_findings,
                "valid_findings": valid_findings,
                "false_positives": false_positives,
                "valuable_findings": valuable_findings,
                "average_ai_confidence": round(avg_confidence, 3),
                "scan_duration_seconds": duration,
                "total_payout": float(total_payout),
                "payout_per_second": round(payout_per_second, 4),
                "effectiveness_percentage": round(
                    (valuable_findings / total_findings * 100) if total_findings else 0,
                    2,
                ),
                "triggered_at": scan.triggered_at.isoformat() if scan.triggered_at else None,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
            },
        }

    async def calculate_monthly_summary(self) -> dict[str, Any]:
        """Calculate month-over-month trends for all findings.

        Returns:
            Dictionary with monthly summary statistics
        """
        monthly_stmt = (
            select(
                func.strftime("%Y-%m", ScanFinding.discovered_at).label("month"),
                func.count(ScanFinding.id).label("total_findings"),
                func.sum(
                    case(
                        (ScanFinding.is_duplicate == False, 1),
                        else_=0,
                    )
                ).label("unique_findings"),
                func.sum(
                    case(
                        (ScanFinding.status == "paid", 1),
                        else_=0,
                    )
                ).label("paid_findings"),
                func.sum(ScanFinding.actual_payout).label("total_payout"),
            )
            .where(ScanFinding.discovered_at.isnot(None))
            .group_by(func.strftime("%Y-%m", ScanFinding.discovered_at))
            .order_by(func.strftime("%Y-%m", ScanFinding.discovered_at).desc())
        )

        result = await self.db.execute(monthly_stmt)
        monthly_data = result.all()

        summary = []
        for month, total, unique, paid, payout in monthly_data:
            summary.append(
                {
                    "month": month,  # Already formatted as YYYY-MM string
                    "total_findings": total or 0,
                    "unique_findings": unique or 0,
                    "paid_findings": paid or 0,
                    "total_payout": float(payout or 0),
                    "discovery_rate": round(
                        (float(unique or 0) / float(total) * 100)
                        if total
                        else 0,
                        2,
                    ),
                }
            )

        return {
            "monthly_trends": summary,
            "summary_period": f"Last {len(summary)} months",
        }

    async def get_top_programs_by_payout(
        self, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get top programs by total payout received.

        Args:
            limit: Number of top programs to return

        Returns:
            List of program performance dictionaries
        """
        top_stmt = (
            select(
                ScanFinding.program_id,
                func.count(ScanFinding.id).label("total_findings"),
                func.sum(ScanFinding.actual_payout).label("total_payout"),
                func.avg(ScanFinding.ai_confidence_score).label("avg_confidence"),
            )
            .group_by(ScanFinding.program_id)
            .order_by(func.sum(ScanFinding.actual_payout).desc().nullslast())
            .limit(limit)
        )

        result = await self.db.execute(top_stmt)
        programs = result.all()

        top_programs = []
        for program_id, total_findings, total_payout, avg_conf in programs:
            top_programs.append(
                {
                    "program_id": str(program_id),
                    "total_findings": total_findings or 0,
                    "total_payout": float(total_payout or 0),
                    "average_confidence": round(float(avg_conf or 0), 3),
                }
            )

        return top_programs
