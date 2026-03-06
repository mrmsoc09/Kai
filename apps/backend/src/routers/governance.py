from __future__ import annotations

from fastapi import APIRouter
from typing import Any, Dict

from ..core.governance_readiness import build_governance_readiness_report

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/readiness")
async def governance_readiness() -> Dict[str, Any]:
    return build_governance_readiness_report()
