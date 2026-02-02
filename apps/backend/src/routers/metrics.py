
from fastapi import APIRouter
from typing import Dict, Any
from ..core.run_store import aggregate_all

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get('/aggregate')
def aggregate() -> Dict[str, Any]:
    return aggregate_all()
