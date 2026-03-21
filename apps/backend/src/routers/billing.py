"""
Billing / Usage API Router
"""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query

from apps.backend.src.billing.usage_tracker import summarize_usage, read_usage_records
from apps.backend.src.core.auth import require_roles, ROLE_ADMIN, ROLE_OPERATOR

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage/summary")
async def get_usage_summary(
    tenant_id: str = Query(..., description="Tenant ID to summarize"),
    since: str | None = Query(None, description="ISO 8601 start timestamp (e.g. 2026-01-01T00:00:00Z)"),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
) -> dict:
    """Return usage summary for a tenant."""
    return summarize_usage(tenant_id=tenant_id, since_iso=since)


@router.get("/usage/records")
async def get_usage_records(
    tenant_id: str = Query(...),
    event_type: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    _auth=Depends(require_roles(ROLE_ADMIN)),
) -> dict:
    """Return raw usage records for a tenant (Admin only)."""
    records = read_usage_records(
        tenant_id=tenant_id,
        event_type=event_type,
        since_iso=since,
    )
    return {
        "tenant_id": tenant_id,
        "count": len(records[:limit]),
        "records": records[:limit],
    }
