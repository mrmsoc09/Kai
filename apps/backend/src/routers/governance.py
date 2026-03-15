from __future__ import annotations

from fastapi import APIRouter, Depends
from typing import Any, Dict

from ..core.governance_readiness import build_governance_readiness_report
from ..core.auth import require_roles, ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN

router = APIRouter(
    prefix="/governance", 
    tags=["governance"],
    dependencies=[Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))]
)


@router.get("/readiness")
async def governance_readiness() -> Dict[str, Any]:
    return build_governance_readiness_report()
