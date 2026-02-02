from __future__ import annotations
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from apps.backend.src.core.auth import require_roles, ROLE_OPERATOR
from modules.triage.scoring_service import triage_for_fingerprints

router = APIRouter(
    prefix='/triage',
    tags=['triage'],
    dependencies=[Depends(require_roles(ROLE_OPERATOR))]
)

@router.post('/score')
def score_fingerprints(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Request: { "fingerprints": [{"tech": "kibana", "version": "8.11"}, ...], "topk": 25 }
    Response: { "results": [ {"cve_id": str, "score": float, "sim": float, "epss": float, "kev": bool, ...}, ... ] }
    """
    fps = payload.get('fingerprints') or []
    if not isinstance(fps, list):
        raise HTTPException(status_code=400, detail='fingerprints must be a list')
    topk_raw = payload.get('topk', 25)
    try:
        topk = int(topk_raw)
    except Exception:
        topk = 25
    results = triage_for_fingerprints(fps, topk=topk)
    return {"results": results}
