from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import ROLE_OPERATOR, require_roles
from ..core.logs import log_decision
from ..core.payout_ledger import list_payout_records, summarize_month, upsert_payout_record


router = APIRouter(
    prefix="/payouts",
    tags=["payouts"],
    dependencies=[Depends(require_roles(ROLE_OPERATOR))],
)


@router.post("/record")
async def record(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        rec = upsert_payout_record(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        log_decision(
            rec["run_id"],
            "payout_record_upsert",
            {
                "finding_id": rec["finding_id"],
                "status": rec["status"],
                "net_amount": rec["net_amount"],
            },
        )
    except Exception:
        pass
    return {"ok": True, "record": rec}


@router.get("/records")
async def records() -> Dict[str, Any]:
    return {"records": list_payout_records()}


@router.get("/reconcile/monthly")
async def reconcile_monthly(year: int | None = None, month: int | None = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    use_year = int(year or now.year)
    use_month = int(month or now.month)
    if use_month < 1 or use_month > 12:
        raise HTTPException(400, "month must be between 1 and 12")
    summary = summarize_month(use_year, use_month)
    return {"ok": True, "summary": summary}
