"""Visualization API endpoints for the Global Heat Map and Analytics Dashboard.

Provides:
  GET /api/v1/analytics/opportunities-map    — opportunity markers for world map
  GET /api/v1/analytics/dashboard-metrics    — aggregated data for 4-chart analytics view
"""
from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import get_current_user
from ..core.hil_db import get_db
from ..models.findings import ScanFinding

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics-viz"],
    dependencies=[Depends(get_current_user)],
)

# ── Deterministic geo-placement helpers ─────────────────────────────────────
# Bug bounty programs don't have real lat/lng — we synthesize stable positions
# from the program name so markers stay put across refreshes.

_REGION_SEEDS: list[tuple[float, float, float]] = [
    # (lat_center, lng_center, spread_deg)
    (37.7, -96.0, 22.0),   # North America
    (52.0,  10.0, 14.0),   # Europe
    (35.0, 105.0, 16.0),   # East Asia
    (-14.0, -51.0, 18.0),  # South America
    (20.0,  78.0, 14.0),   # South Asia
    (-25.0, 134.0, 14.0),  # Australia/Pacific
    (15.0,  20.0, 16.0),   # Africa / Middle East
]


def _stable_latlng(name: str, index: int) -> tuple[float, float]:
    """Return a deterministic lat/lng for a program name."""
    seed = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    region = _REGION_SEEDS[(seed + index) % len(_REGION_SEEDS)]
    lat_c, lng_c, spread = region
    # Two independent sub-hashes for lat/lng offsets
    h1 = int(hashlib.md5((name + "lat").encode()).hexdigest()[:6], 16)
    h2 = int(hashlib.md5((name + "lng").encode()).hexdigest()[:6], 16)
    lat = lat_c + (h1 / 0xFFFFFF - 0.5) * spread
    lng = lng_c + (h2 / 0xFFFFFF - 0.5) * spread * 1.5
    return round(lat, 4), round(lng, 4)


# ── Map endpoint ─────────────────────────────────────────────────────────────

@router.get("/opportunities-map")
async def get_opportunities_map(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return opportunity markers for the world map visualization.

    Each marker includes a stable lat/lng synthesized from the program name,
    plus aggregated findings and payout data.
    """
    try:
        # Aggregate per program_id from scan findings
        stmt = (
            select(
                ScanFinding.program_id,
                func.count(ScanFinding.id).label("total_findings"),
                func.count(ScanFinding.id)
                .filter(ScanFinding.finding_state == "valid")
                .label("valid_findings"),
                func.sum(ScanFinding.actual_payout).label("total_payout"),
                func.max(ScanFinding.cvss_score).label("max_cvss"),
                func.max(ScanFinding.discovered_at).label("last_activity"),
            )
            .where(ScanFinding.program_id.isnot(None))
            .group_by(ScanFinding.program_id)
            .limit(200)
        )
        result = await db.execute(stmt)
        rows = result.all()

        markers: list[dict[str, Any]] = []
        for i, row in enumerate(rows):
            program_name = str(row.program_id)[:8]  # Short display name from UUID prefix
            payout = float(row.total_payout or 0)
            findings = int(row.total_findings or 0)
            valid = int(row.valid_findings or 0)
            cvss = float(row.max_cvss or 0)

            # Determine status from findings state
            if valid > 0 and payout > 0:
                status = "active"
            elif valid > 0:
                status = "pending"
            elif findings > 0:
                status = "scanning"
            else:
                status = "queued"

            lat, lng = _stable_latlng(program_name, i)
            markers.append({
                "id": str(row.program_id),
                "name": f"Program {program_name.upper()}",
                "lat": lat,
                "lng": lng,
                "status": status,
                "findings": findings,
                "payout": payout,
                "max_cvss": cvss,
                "last_activity": row.last_activity.isoformat() if row.last_activity else None,
            })

        return {
            "markers": markers,
            "total": len(markers),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.warning("opportunities-map query failed, returning empty: %s", exc)
        return {"markers": [], "total": 0, "generated_at": datetime.now(timezone.utc).isoformat()}


# ── Dashboard metrics endpoint ────────────────────────────────────────────────

@router.get("/dashboard-metrics")
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return aggregated data for the four-chart analytics dashboard.

    Returns:
        top_programs:               list of {name, payout, findings}
        vulnerability_distribution: list of {type, count, payout}
        playbook_performance:       list of {playbook_id, name, findings, acceptance_rate, roi}
        monthly_trends:             list of {month, findings, payout, acceptance_rate}
    """
    try:
        top_programs = await _top_programs(db)
    except Exception as exc:
        logger.warning("top_programs query failed: %s", exc)
        top_programs = []

    try:
        vuln_dist = await _vulnerability_distribution(db)
    except Exception as exc:
        logger.warning("vuln_dist query failed: %s", exc)
        vuln_dist = []

    try:
        playbook_perf = await _playbook_performance(db)
    except Exception as exc:
        logger.warning("playbook_perf query failed: %s", exc)
        playbook_perf = []

    try:
        monthly = await _monthly_trends(db)
    except Exception as exc:
        logger.warning("monthly_trends query failed: %s", exc)
        monthly = []

    return {
        "top_programs":               top_programs,
        "vulnerability_distribution": vuln_dist,
        "playbook_performance":       playbook_perf,
        "monthly_trends":             monthly,
        "generated_at":               datetime.now(timezone.utc).isoformat(),
    }


# ── Private aggregation helpers ───────────────────────────────────────────────

async def _top_programs(db: AsyncSession, limit: int = 10) -> list[dict[str, Any]]:
    stmt = (
        select(
            ScanFinding.program_id,
            func.count(ScanFinding.id).label("findings"),
            func.sum(ScanFinding.actual_payout).label("payout"),
        )
        .where(ScanFinding.program_id.isnot(None))
        .group_by(ScanFinding.program_id)
        .order_by(func.sum(ScanFinding.actual_payout).desc().nulls_last())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "name": str(row.program_id)[:8].upper(),
            "payout": float(row.payout or 0),
            "findings": int(row.findings or 0),
        }
        for row in result.all()
    ]


async def _vulnerability_distribution(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(
            ScanFinding.vulnerability_type,
            func.count(ScanFinding.id).label("count"),
            func.sum(ScanFinding.actual_payout).label("payout"),
        )
        .where(ScanFinding.vulnerability_type.isnot(None))
        .group_by(ScanFinding.vulnerability_type)
        .order_by(func.count(ScanFinding.id).desc())
        .limit(12)
    )
    result = await db.execute(stmt)
    return [
        {
            "type": row.vulnerability_type or "Unknown",
            "count": int(row.count or 0),
            "payout": float(row.payout or 0),
        }
        for row in result.all()
    ]


async def _playbook_performance(db: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
    stmt = (
        select(
            ScanFinding.playbook_id,
            ScanFinding.playbook_name,
            func.count(ScanFinding.id).label("findings"),
            func.count(ScanFinding.id)
            .filter(ScanFinding.validation_status == "approved_for_submission")
            .label("approved"),
            func.sum(ScanFinding.actual_payout).label("roi"),
        )
        .where(ScanFinding.playbook_id.isnot(None))
        .group_by(ScanFinding.playbook_id, ScanFinding.playbook_name)
        .order_by(func.sum(ScanFinding.actual_payout).desc().nulls_last())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    out = []
    for row in rows:
        findings = int(row.findings or 0)
        approved = int(row.approved or 0)
        acceptance_rate = (approved / findings) if findings > 0 else 0.0
        out.append({
            "playbook_id":     str(row.playbook_id),
            "name":            row.playbook_name or str(row.playbook_id)[:8].upper(),
            "findings":        findings,
            "acceptance_rate": round(acceptance_rate, 3),
            "roi":             float(row.roi or 0),
        })
    return out


async def _monthly_trends(db: AsyncSession, months: int = 12) -> list[dict[str, Any]]:
    """Aggregate findings by calendar month (last N months)."""
    # Use strftime for SQLite compatibility; PostgreSQL understands it too via cast
    try:
        stmt = text("""
            SELECT
                strftime('%Y-%m', discovered_at) AS month,
                COUNT(*)                         AS findings,
                SUM(COALESCE(actual_payout, 0))  AS payout,
                SUM(CASE WHEN validation_status = 'approved_for_submission' THEN 1 ELSE 0 END) AS approved
            FROM scan_findings
            WHERE discovered_at IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT :months
        """)
        result = await db.execute(stmt, {"months": months})
        rows = list(reversed(result.all()))
        out = []
        for row in rows:
            f = int(row.findings or 0)
            a = int(row.approved or 0)
            out.append({
                "month":           row.month,
                "findings":        f,
                "payout":          float(row.payout or 0),
                "acceptance_rate": round(a / f, 3) if f > 0 else 0.0,
            })
        return out
    except Exception:
        # Fallback: PostgreSQL date_trunc syntax
        stmt_pg = text("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', discovered_at), 'YYYY-MM') AS month,
                COUNT(*)                                                 AS findings,
                SUM(COALESCE(actual_payout, 0))                         AS payout,
                SUM(CASE WHEN validation_status = 'approved_for_submission' THEN 1 ELSE 0 END) AS approved
            FROM scan_findings
            WHERE discovered_at IS NOT NULL
            GROUP BY DATE_TRUNC('month', discovered_at)
            ORDER BY DATE_TRUNC('month', discovered_at) DESC
            LIMIT :months
        """)
        result = await db.execute(stmt_pg, {"months": months})
        rows = list(reversed(result.all()))
        out = []
        for row in rows:
            f = int(row.findings or 0)
            a = int(row.approved or 0)
            out.append({
                "month":           row.month,
                "findings":        f,
                "payout":          float(row.payout or 0),
                "acceptance_rate": round(a / f, 3) if f > 0 else 0.0,
            })
        return out
