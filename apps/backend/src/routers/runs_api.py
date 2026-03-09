from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from ..core.run_store import load_all_runs

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("")
@router.get("/")
def list_runs(limit: int = 50) -> Dict[str, Any]:
    runs = load_all_runs()
    runs_sorted = sorted(runs, key=lambda r: r.get("timestamp", ""), reverse=True)
    return {"runs": runs_sorted[: max(1, min(limit, 200))]}


@router.get("/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    for r in load_all_runs():
        if r.get("run_id") == run_id:
            return r
    raise HTTPException(status_code=404, detail="run_not_found")
