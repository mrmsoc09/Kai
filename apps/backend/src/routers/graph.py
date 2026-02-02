
from fastapi import APIRouter
from typing import Dict, Any
from ..core.graph import build_graph

router = APIRouter(prefix="/graph", tags=["graph"])

@router.get('')
@router.get('/')
def graph() -> Dict[str, Any]:
    return build_graph()
