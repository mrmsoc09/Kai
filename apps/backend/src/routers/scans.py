from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..core.scope import require_scope_accept
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.jobs import enqueue
from ..core.logs import log_decision
import re, time

router = APIRouter(
    prefix="/scans",
    tags=["scans"],
    dependencies=[Depends(require_scope_accept), Depends(require_roles(ROLE_OPERATOR))],
)


def _safe_id(s: str) -> str:
    s = (s or '').lower().strip()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "target"


@router.post("/start")
async def start(payload: Dict[str, Any]) -> Dict[str, Any]:
    target = (payload.get("target") or "").strip()
    workflow = (payload.get("workflow") or "osint_recon").strip()
    schedule = payload.get("schedule")  # optional: cron-like or immediate
    policy = payload.get("policy") or {}

    if not target:
        raise HTTPException(400, "target required")

    # Construct stable run identifier
    ts = int(time.time())
    run_id = f"run-{_safe_id(workflow)}-{_safe_id(target)}-{ts}"

    # Enqueue job with explicit payload for orchestrator/worker
    job_payload: Dict[str, Any] = {
        "run_id": run_id,
        "workflow": workflow,
        "target": target,
        "policy": policy,
        "schedule": schedule,
        "requested_at": ts,
    }
    job = enqueue("scan", job_payload)

    try:
        log_decision(run_id, "scan_enqueued", {"workflow": workflow, "target": target, "job_id": job.get("id")})
    except Exception:
        # Non-fatal logging failure
        pass

    return {
        "run_id": run_id,
        "job": {"id": job.get("id"), "state": job.get("state", "queued"), "ts": job.get("ts")},
        "status": "queued",
        "workflow": workflow,
        "target": target,
    }
