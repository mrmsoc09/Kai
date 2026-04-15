"""Analytics API endpoints for accessing findings metrics and insights.

This router provides REST endpoints for querying:
- Program metrics (findings, submissions, payouts, ROI)
- Playbook performance analysis
- Vulnerability distribution
- Scan effectiveness metrics
- Monthly trends
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import get_current_user
from ..core.hil_db import get_db
from ..models.findings import ScanFinding, FindingSubmission
from ..services.finding_collector import FindingCollector
from ..services.metrics_calculator import MetricsCalculator
from ..services.submission_tracker import SubmissionTracker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/program/{program_id}")
async def get_program_metrics(
    program_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get comprehensive metrics for a specific program.

    Args:
        program_id: Program UUID

    Returns:
        Dictionary with program metrics including:
        - Total findings, unique findings, duplicates
        - Acceptance rate, payout accuracy
        - ROI analysis
    """
    try:
        program_uuid = UUID(program_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid program_id format")

    calculator = MetricsCalculator(db)
    metrics = await calculator.calculate_program_metrics(program_uuid)
    return metrics


@router.get("/playbooks")
async def get_playbook_performance(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get performance metrics for all playbooks.

    Returns:
        Dictionary with list of playbook performance metrics including:
        - Total findings and unique findings per playbook
        - Acceptance rates and payout
        - ROI per playbook
    """
    calculator = MetricsCalculator(db)
    playbook_stats = await calculator.calculate_playbook_performance()
    return {
        "playbooks": playbook_stats,
        "total_playbooks": len(playbook_stats),
        "total_payout": sum(p["total_payout"] for p in playbook_stats),
    }


@router.get("/vulnerabilities")
async def get_vulnerability_distribution(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get distribution of vulnerability types found.

    Returns:
        Dictionary with vulnerability type distribution including:
        - Count of each type
        - Average CVSS scores
        - Payout information per type
        - Acceptance rates
    """
    calculator = MetricsCalculator(db)
    distribution = await calculator.calculate_vulnerability_distribution()
    return distribution


@router.get("/scan/{scan_id}")
async def get_scan_effectiveness(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get effectiveness metrics for a specific scan.

    Args:
        scan_id: Scan UUID

    Returns:
        Dictionary with scan effectiveness metrics including:
        - Total and unique findings
        - Valid findings and false positives
        - Payout per second (efficiency metric)
        - Scan duration and effectiveness percentage
    """
    try:
        scan_uuid = UUID(scan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scan_id format")

    calculator = MetricsCalculator(db)
    effectiveness = await calculator.calculate_scan_effectiveness(scan_uuid)
    return effectiveness


@router.get("/monthly-summary")
async def get_monthly_summary(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get month-over-month trends for all findings.

    Returns:
        Dictionary with monthly summary including:
        - Findings discovered per month
        - Paid findings per month
        - Total payout per month
        - Discovery rates
    """
    calculator = MetricsCalculator(db)
    summary = await calculator.calculate_monthly_summary()
    return summary


@router.get("/top-programs")
async def get_top_programs(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get top programs by total payout received.

    Args:
        limit: Number of top programs to return (1-100, default 10)

    Returns:
        List of top programs with metrics
    """
    calculator = MetricsCalculator(db)
    top_programs = await calculator.get_top_programs_by_payout(limit)
    return {
        "top_programs": top_programs,
        "limit": limit,
        "count": len(top_programs),
    }


@router.get("/findings/{program_id}")
async def query_findings(
    program_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    vulnerability_type: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Query findings for a program with optional filters.

    Args:
        program_id: Program UUID
        limit: Maximum number of findings to return (1-1000, default 100)
        offset: Number of findings to skip (default 0)
        vulnerability_type: Filter by vulnerability type (XSS, SQLi, etc.)
        status: Filter by status (discovered, submitted, accepted, paid, etc.)
        severity: Filter by severity (critical, high, medium, low)

    Returns:
        Dictionary with findings and pagination info
    """
    from sqlalchemy import select

    try:
        program_uuid = UUID(program_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid program_id format")

    # Build query
    query = select(ScanFinding).where(ScanFinding.program_id == program_uuid)

    if vulnerability_type:
        query = query.where(ScanFinding.vulnerability_type == vulnerability_type)
    if status:
        query = query.where(ScanFinding.status == status)
    if severity:
        query = query.where(ScanFinding.severity == severity)

    # Get total count
    count_query = select(func.count(ScanFinding.id)).where(
        ScanFinding.program_id == program_uuid
    )
    if vulnerability_type:
        count_query = count_query.where(
            ScanFinding.vulnerability_type == vulnerability_type
        )
    if status:
        count_query = count_query.where(ScanFinding.status == status)
    if severity:
        count_query = count_query.where(ScanFinding.severity == severity)

    total = await db.scalar(count_query)

    # Get paginated results
    query = query.offset(offset).limit(limit)
    result = await db.scalars(query)
    findings = list(result.all())

    # Format findings
    formatted_findings = [
        {
            "id": str(f.id),
            "finding_identifier": f.finding_identifier,
            "vulnerability_type": f.vulnerability_type,
            "severity": f.severity,
            "cvss_score": float(f.cvss_score) if f.cvss_score else None,
            "endpoint": f.endpoint,
            "parameter_name": f.parameter_name,
            "http_method": f.http_method,
            "description": f.description,
            "status": f.status,
            "finding_state": f.finding_state,
            "ai_confidence_score": float(f.ai_confidence_score)
            if f.ai_confidence_score
            else None,
            "estimated_payout": float(f.estimated_payout)
            if f.estimated_payout
            else None,
            "actual_payout": float(f.actual_payout) if f.actual_payout else None,
            "payout_accuracy_percentage": float(f.payout_accuracy_percentage)
            if f.payout_accuracy_percentage
            else None,
            "is_duplicate": f.is_duplicate,
            "playbook_id": f.playbook_id,
            "playbook_name": f.playbook_name,
            "discovered_at": f.discovered_at.isoformat() if f.discovered_at else None,
            "payout_received_at": f.payout_received_at.isoformat()
            if f.payout_received_at
            else None,
        }
        for f in findings
    ]

    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "count": len(formatted_findings),
        "findings": formatted_findings,
    }


@router.get("/finding/{finding_id}/submissions")
async def get_finding_submissions(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get all submissions for a finding.

    Args:
        finding_id: Finding UUID

    Returns:
        Dictionary with list of submissions and their statuses
    """
    from sqlalchemy import select

    try:
        finding_uuid = UUID(finding_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid finding_id format")

    # Get submissions
    stmt = select(FindingSubmission).where(
        FindingSubmission.finding_id == finding_uuid
    )
    result = await db.scalars(stmt)
    submissions = list(result.all())

    formatted = [
        {
            "id": str(s.id),
            "platform": s.submitted_to_platform,
            "status": s.current_status,
            "submission_url": s.submission_url,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            "payout_amount": float(s.payout_amount) if s.payout_amount else None,
            "payout_currency": s.payout_currency,
            "payout_received_at": s.payout_received_at.isoformat()
            if s.payout_received_at
            else None,
            "report_quality_score": float(s.report_quality_score)
            if s.report_quality_score
            else None,
            "status_history": s.status_history or [],
        }
        for s in submissions
    ]

    return {
        "finding_id": str(finding_uuid),
        "total_submissions": len(formatted),
        "submissions": formatted,
    }


# Import func for count queries
from sqlalchemy import func
