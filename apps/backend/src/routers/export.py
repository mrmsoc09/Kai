from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.exporters import export_recordings_metadata

router = APIRouter(prefix='/export', tags=['export'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.post('/recordings')
async def export_recordings(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    if not run_id:
        raise HTTPException(400, 'run_id required')
    return export_recordings_metadata(run_id)
