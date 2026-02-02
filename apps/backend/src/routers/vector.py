from __future__ import annotations
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.vector_store import VectorStore

router = APIRouter(prefix='/vector', tags=['vector'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.get('/info')
async def info() -> Dict[str, Any]:
    vs = VectorStore()
    return vs.info()

@router.post('/upsert')
async def upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = payload.get('items') or []
    if not isinstance(items, list) or not items:
        raise HTTPException(400, 'items list required')
    vs = VectorStore()
    n = vs.upsert(items)
    return {'ok': True, 'count': n}

@router.post('/search')
async def search(payload: Dict[str, Any]) -> Dict[str, Any]:
    q = (payload.get('query') or '').strip()
    if not q:
        raise HTTPException(400, 'query required')
    top_k = int(payload.get('top_k') or 5)
    min_score = float(payload.get('min_score') or 0.2)
    vs = VectorStore()
    res = vs.search(q, top_k=top_k, min_score=min_score)
    return {'results': res}
