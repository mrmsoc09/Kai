from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.planner import mitre_plan, execute_plan

router = APIRouter(prefix='/planner', tags=['planner'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.post('/plan')
async def plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    tid = (payload or {}).get('technique_id')
    if not tid:
        raise HTTPException(400, 'technique_id required')
    out = mitre_plan(tid)
    return {'ok': True, 'plan': out}

@router.post('/execute')
async def execute(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = (payload or {}).get('run_id')
    tid = (payload or {}).get('technique_id')
    hil = bool((payload or {}).get('hil_approved'))
    if not run_id or not tid:
        raise HTTPException(400, 'run_id and technique_id required')
    res = execute_plan(run_id, tid, hil)
    # Normalize response for API
    status = 'denied' if not res.get('ok') else 'executed'
    return {'status': status, 'result': res}
