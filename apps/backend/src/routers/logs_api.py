import re
from fastapi import APIRouter, Depends, HTTPException
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.logs import list_recent_logs, read_decision_trace, read_summary, write_summary, _logs_root

router = APIRouter(prefix="/api/v1/logs", tags=["logs"], dependencies=[Depends(require_roles(ROLE_OPERATOR))])


@router.get("")
@router.get("/")
async def list_logs(limit: int = 200):
    return {"logs": list_recent_logs(limit=limit)}


@router.get("/{run_id}/decision_trace")
async def get_decision_trace(run_id: str):
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', run_id):
        raise HTTPException(status_code=400, detail=f"Invalid run_id format: {run_id}")
    return {"run_id": run_id, "decision_trace": read_decision_trace(run_id)}


@router.get("/{run_id}/summary")
async def get_summary(run_id: str):
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', run_id):
        raise HTTPException(status_code=400, detail=f"Invalid run_id format: {run_id}")
    return {"run_id": run_id, "summary": read_summary(run_id)}


@router.post("/{run_id}/summary")
async def post_summary(run_id: str, payload: dict):
    # Validate run_id against strict allowlist to prevent path traversal
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', run_id):
        raise HTTPException(status_code=400, detail=f"Invalid run_id format: {run_id}")
    
    text = payload.get("text") or ""
    try:
        p = write_summary(run_id, text)
        
        # Assert the resolved output path remains within the designated logs directory
        logs_base = _logs_root().resolve()
        if not str(p.resolve()).startswith(str(logs_base)):
             raise HTTPException(status_code=400, detail="Invalid run_id: path traversal detected")
             
        return {"ok": True, "path": str(p)}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
