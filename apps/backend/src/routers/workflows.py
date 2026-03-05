"""
Hunt Workflow CRUD + State Transition endpoints.

Read access: any authenticated user.
Write access (create, transition, link-run, delete): OPERATOR or ADMIN role.

GET    /workflows                     list (filterable)
POST   /workflows                     create (requires auth)
GET    /workflows/{wf_id}             detail
PATCH  /workflows/{wf_id}             update notes (OPERATOR)
POST   /workflows/{wf_id}/transition  advance state (OPERATOR)
POST   /workflows/{wf_id}/link-run    associate run_id (OPERATOR)
DELETE /workflows/{wf_id}             close + remove (OPERATOR)
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from apps.backend.src.core.opportunity_catalog import get_opportunity
from apps.backend.src.core.workflow_store import (
    HuntWorkflow,
    STATES,
    create_workflow,
    delete_workflow,
    get_workflow,
    link_run,
    list_workflows,
    transition_workflow,
    update_notes,
)
from apps.backend.src.core.auth import (
    get_current_user,
    require_roles,
    ROLE_OPERATOR,
    ROLE_ADMIN,
    User,
)

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    dependencies=[Depends(get_current_user)],  # read access: any authenticated user
)

_require_operator = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN))


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class WorkflowOut(BaseModel):
    id: str
    opportunity_id: str
    program_name: str
    platform: str
    access_type: str
    status: str
    scope_accepted: bool
    scope_domains: List[str]
    findings_count: int
    created_at: str
    updated_at: str
    transitioned_at: dict
    run_ids: List[str]
    notes: str
    created_by: str
    allowed_transitions: List[str]
    is_terminal: bool


def _out(wf: HuntWorkflow) -> WorkflowOut:
    return WorkflowOut(
        id=wf.id,
        opportunity_id=wf.opportunity_id,
        program_name=wf.program_name,
        platform=wf.platform,
        access_type=wf.access_type,
        status=wf.status,
        scope_accepted=wf.scope_accepted,
        scope_domains=wf.scope_domains,
        findings_count=wf.findings_count,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
        transitioned_at=wf.transitioned_at,
        run_ids=wf.run_ids,
        notes=wf.notes,
        created_by=wf.created_by,
        allowed_transitions=wf.allowed_transitions(),
        is_terminal=wf.is_terminal(),
    )


class CreateWorkflowRequest(BaseModel):
    opportunity_id: str = Field(..., min_length=1, max_length=200)
    notes: str = Field("", max_length=2000)


class UpdateWorkflowRequest(BaseModel):
    notes: str = Field(..., max_length=2000)


class TransitionRequest(BaseModel):
    to_state: str = Field(..., description=f"One of: {STATES}")
    notes: str = Field("", max_length=2000)


class LinkRunRequest(BaseModel):
    run_id: str = Field(..., min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
async def list_wf(
    status: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    opportunity_id: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    results = list_workflows(
        status=status,
        platform=platform,
        created_by=created_by,
    )
    # Client-side filter for opportunity_id (cheap since file count is small)
    if opportunity_id:
        results = [w for w in results if w.opportunity_id == opportunity_id]
    total = len(results)
    # Sort: active workflows first (by created_at desc), terminal last
    results = sorted(results, key=lambda w: (w.is_terminal(), w.created_at), reverse=True)
    page = results[offset: offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "workflows": [_out(w) for w in page],
    }


@router.post("", response_model=WorkflowOut, dependencies=[_require_operator])
async def create_wf(
    body: CreateWorkflowRequest,
    current_user: User = Depends(get_current_user),
):
    opp = get_opportunity(body.opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {body.opportunity_id!r} not found")

    # Guard: prevent duplicate active workflows for the same opportunity per user
    existing = [
        w for w in list_workflows(created_by=current_user.id)
        if w.opportunity_id == opp.id and not w.is_terminal()
    ]
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "active_workflow_exists",
                "message": f"An active workflow already exists for {opp.name!r}.",
                "workflow_id": existing[0].id,
            },
        )

    wf = create_workflow(
        opportunity_id=opp.id,
        program_name=opp.name,
        platform=opp.platform,
        access_type=opp.access_type,
        scope_domains=opp.scope_domains,
        notes=body.notes,
        created_by=current_user.id,
    )
    return _out(wf)


@router.get("/{wf_id}", response_model=WorkflowOut)
async def get_wf(wf_id: str):
    wf = get_workflow(wf_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id!r} not found")
    return _out(wf)


@router.patch("/{wf_id}", response_model=WorkflowOut, dependencies=[_require_operator])
async def update_wf(wf_id: str, body: UpdateWorkflowRequest):
    """Update workflow notes without a state transition."""
    wf = update_notes(wf_id, body.notes)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id!r} not found")
    return _out(wf)


@router.post("/{wf_id}/transition", response_model=WorkflowOut, dependencies=[_require_operator])
async def transition_wf(wf_id: str, body: TransitionRequest):
    if body.to_state not in STATES:
        raise HTTPException(status_code=422, detail=f"Unknown state {body.to_state!r}")
    try:
        wf = transition_workflow(wf_id, body.to_state, notes=body.notes)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _out(wf)


@router.post("/{wf_id}/link-run", response_model=WorkflowOut, dependencies=[_require_operator])
async def link_wf_run(wf_id: str, body: LinkRunRequest):
    try:
        wf = link_run(wf_id, body.run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _out(wf)


@router.get("/{wf_id}/scope")
async def get_scope(wf_id: str):
    """
    Export the scope for this workflow in a format ready for dork/scan tool consumption.

    Returns the scope_domains list plus metadata for handoff to recon tools.
    Requires the workflow to be in RECON, SCANNING, TRIAGE, or HIL_REVIEW state
    (scope must have been accepted).
    """
    wf = get_workflow(wf_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id!r} not found")
    if not wf.scope_accepted:
        raise HTTPException(
            status_code=400,
            detail="Scope has not been accepted for this workflow yet. Advance to SCOPING first.",
        )
    # Separate wildcard domains from explicit hosts
    wildcards = [d for d in wf.scope_domains if d.startswith("*.")]
    explicit = [d for d in wf.scope_domains if not d.startswith("*.") and "." in d]
    apps = [d for d in wf.scope_domains if "." not in d]  # mobile/desktop targets like "ios", "android"
    return {
        "workflow_id": wf.id,
        "program_name": wf.program_name,
        "platform": wf.platform,
        "access_type": wf.access_type,
        "status": wf.status,
        "scope_domains": wf.scope_domains,
        "wildcards": wildcards,
        "explicit_hosts": explicit,
        "app_targets": apps,
        # Convenience: root domains extracted from wildcards for certificate/subdomain enum
        "root_domains": list({d.lstrip("*.").split("/")[0] for d in wildcards}),
        "notes": wf.notes,
    }


@router.delete("/{wf_id}", dependencies=[_require_operator])
async def close_wf(wf_id: str):
    ok = delete_workflow(wf_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id!r} not found")
    return {"deleted": wf_id}
