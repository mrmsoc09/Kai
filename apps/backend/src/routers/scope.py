from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.scope import is_in_scope, reload_policies

router = APIRouter(prefix='/scope', tags=['scope'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.get('/check')
async def check(url: str) -> Dict[str, Any]:
    return {'url': url, 'in_scope': is_in_scope(url)}

@router.post('/reload')
async def reload() -> Dict[str, Any]:
    return {'ok': True, 'policies': reload_policies()}
