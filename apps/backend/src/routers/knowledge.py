
from fastapi import APIRouter, Depends
from typing import Dict, Any
from ..core.obsidian import ObsidianConnector
from ..core.hybrid_retriever import hybrid_retrieve
from ..core.auth import require_roles, ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN

router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))],
)

@router.get('/status')
def status() -> Dict[str, Any]:
    return ObsidianConnector().status()

@router.post('/refresh', dependencies=[Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN))])
def refresh() -> Dict[str, Any]:
    return ObsidianConnector().refresh()

@router.get('/notes')
def notes() -> Dict[str, Any]:
    return ObsidianConnector().list_notes()


@router.post('/retrieve')
def retrieve(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = (payload.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "query_required"}
    top_k = int(payload.get("top_k") or 10)
    min_score = float(payload.get("min_score") or 0.2)
    return {"ok": True, **hybrid_retrieve(query=query, top_k=top_k, min_score=min_score)}
