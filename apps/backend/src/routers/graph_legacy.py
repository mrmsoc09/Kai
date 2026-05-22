
from fastapi import APIRouter, Depends
from typing import Dict, Any
from ..core.graph import build_graph
from ..core.auth import require_roles, ROLE_ANALYST

router = APIRouter(
    prefix="/graph",
    tags=["graph"],
    dependencies=[Depends(require_roles(ROLE_ANALYST))],
)

@router.get('')
@router.get('/')
def graph() -> Dict[str, Any]:
    return build_graph()
