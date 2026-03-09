from __future__ import annotations
from fastapi import APIRouter, Depends
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.logs import read_decision_trace, read_summary, write_summary, list_recent_logs

router = APIRouter(prefix='/logs', tags=['logs'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.get('')
@router.get('/')
async def list_logs(limit: int = 200):
    return {"logs": list_recent_logs(limit=limit)}

@router.get('/{run_id}/decision_trace')
async def get_decision_trace(run_id: str):
    return {'run_id': run_id, 'decision_trace': read_decision_trace(run_id)}

@router.get('/{run_id}/summary')
async def get_summary(run_id: str):
    return {'run_id': run_id, 'summary': read_summary(run_id)}

@router.post('/{run_id}/summary')
async def post_summary(run_id: str, payload: dict):
    text = payload.get('text') or ''
    p = write_summary(run_id, text)
    return {'ok': True, 'path': str(p)}
