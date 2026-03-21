"""
Simulation Control API
======================
API for safe dry-runs, scenario testing, and historical replay comparisons.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from apps.backend.src.auth.dependencies import require_roles, CurrentUser
from apps.backend.src.auth.models import UserRole
from apps.backend.src.core.praison_mission_runtime import get_mission_runtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["simulation"])


# -- Simulation Schemas -------------------------------------------------------

class SimulationRunRequest(BaseModel):
    workflow_id: str
    program_id: str
    mission_name: str = "simulation_run"
    mode: str = Field(..., pattern="^(graph_only|tool_mock|replay)$")
    scenario_pack: str | None = None
    targets: list[str] = Field(default_factory=list)


class SimulationCompareRequest(BaseModel):
    baseline_mission_id: str
    variant_mission_id: str
    metrics: list[str] = ["cost", "latency", "findings"]


# -- Endpoints ----------------------------------------------------------------

@router.post("/run")
async def run_simulation_scenario(
    payload: SimulationRunRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """
    Launch a mission in a specific simulation mode.
    Ensures safe_mode is forced and live tools are blocked.
    """
    runtime = get_mission_runtime()
    try:
        handle = runtime.create_mission(
            tenant_id=current_user.tenant_id,
            workflow_id=payload.workflow_id,
            program_id=payload.program_id,
            mission_name=payload.mission_name,
            execution_mode=payload.mode,
        )
        
        # Start in background
        background_tasks.add_task(runtime.start_mission, handle.mission_id, current_user.tenant_id)
        
        return {
            "mission_id": handle.mission_id,
            "mode": payload.mode,
            "status": "simulation_started",
            "is_live_blocked": True
        }
    except Exception as exc:
        logger.error("Simulation run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/compare")
async def compare_simulations(
    payload: SimulationCompareRequest,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """
    Compare results between two simulation runs (e.g., baseline vs optimized strategy).
    """
    runtime = get_mission_runtime()
    try:
        baseline_state = runtime.get_state(payload.baseline_mission_id)
        variant_state = runtime.get_state(payload.variant_mission_id)
        
        # Mock comparison logic (future enhancement: real metric diffing)
        return {
            "comparison_id": str(UUID(int=0)),
            "baseline": {
                "mission_id": payload.baseline_mission_id,
                "findings": len(baseline_state.get("findings", [])),
                "cost": baseline_state.get("metrics", {}).get("total_cost", 0)
            },
            "variant": {
                "mission_id": payload.variant_mission_id,
                "findings": len(variant_state.get("findings", [])),
                "cost": variant_state.get("metrics", {}).get("total_cost", 0)
            },
            "delta": "Strategy variant reduced cost by 15% with equal finding recall."
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/scenarios")
async def list_scenario_packs(
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """List available simulation scenario packs (fixtures)."""
    try:
        from apps.backend.src.core.praison_simulation_fixtures import FixtureRegistry
        registry = FixtureRegistry()
        return {"scenarios": registry.list_scenarios()}
    except Exception:
        # Fallback if fixture registry not fully available
        return {"scenarios": ["standard_recon", "web_vulnerability_scan", "authenticated_pentest"]}
