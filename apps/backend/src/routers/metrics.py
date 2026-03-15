
from fastapi import APIRouter, Depends
from typing import Dict, Any
from fastapi.responses import PlainTextResponse
from ..core.run_store import aggregate_all
from ..core.kpi_metrics import build_kpi_snapshot, kpi_snapshot_csv
from ..core.auth import require_roles, ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN

router = APIRouter(
    prefix="/metrics", 
    tags=["metrics"], 
    dependencies=[Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))]
)

@router.get('/aggregate')
def aggregate() -> Dict[str, Any]:
    return aggregate_all()


@router.get('/kpi')
def kpi_snapshot() -> Dict[str, Any]:
    return build_kpi_snapshot()


@router.get('/kpi/export.csv', response_class=PlainTextResponse)
def kpi_export_csv() -> str:
    return kpi_snapshot_csv(build_kpi_snapshot())
