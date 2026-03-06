from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.auth import ROLE_OPERATOR, require_roles
from ..core.comms_store import append_message, get_thread, list_threads


router = APIRouter(
    prefix="/comms",
    tags=["comms"],
    dependencies=[Depends(require_roles(ROLE_OPERATOR))],
)


@router.get("/threads")
async def threads(run_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return {"threads": list_threads(run_id=run_id)}


@router.get("/threads/{thread_id}")
async def thread(thread_id: str) -> Dict[str, Any]:
    item = get_thread(thread_id)
    if not item:
        raise HTTPException(404, "thread_not_found")
    return {"thread": item}


@router.post("/messages")
async def message(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get("run_id")
    channel = payload.get("channel")
    direction = payload.get("direction")
    subject = payload.get("subject") or "(no subject)"
    body = payload.get("body") or ""
    if not run_id or not channel or not direction:
        raise HTTPException(400, "run_id, channel, direction required")
    msg = append_message(
        run_id=str(run_id),
        finding_id=payload.get("finding_id"),
        report_id=payload.get("report_id"),
        stakeholder=payload.get("stakeholder"),
        channel=str(channel),
        direction=str(direction),
        subject=str(subject),
        body=str(body),
        artifact_path=payload.get("artifact_path"),
        metadata=dict(payload.get("metadata") or {}),
    )
    return {"ok": True, "message": msg}
