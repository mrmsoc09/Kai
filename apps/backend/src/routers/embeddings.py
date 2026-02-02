from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.embeddings import upsert_embeddings, search_similar

router = APIRouter(prefix='/embeddings', tags=['embeddings'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

@router.post('/upsert')
async def upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = (payload or {}).get('run_id')
    items: List[Dict[str, Any]] = (payload or {}).get('items') or []
    if not run_id or not items:
        raise HTTPException(400, 'run_id and items required')
    return upsert_embeddings(run_id, items)

@router.post('/search')
async def search(payload: Dict[str, Any]) -> Dict[str, Any]:
    q = (payload or {}).get('q') or ''
    if not q:
        raise HTTPException(400, 'q required')
    top_k = int((payload or {}).get('top_k') or 5)
    min_score = float((payload or {}).get('min_score') or 0.7)
    return search_similar(q, top_k=top_k, min_score=min_score)
