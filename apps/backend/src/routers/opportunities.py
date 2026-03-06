"""
Opportunity Hub — read-only catalog endpoints.

Any authenticated user (VIEWER role or higher) may access these endpoints.
Authorization model: public programs (public_bbp / public_vrp / government_cvd) require
no additional permission — the program listing IS the authorization per AGENTS.md §3.2.

GET /opportunities            list + filter
GET /opportunities/ranked     sorted by priority_score desc
GET /opportunities/stats      aggregate catalog statistics
GET /opportunities/{opp_id}   detail
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from apps.backend.src.core.opportunity_catalog import (
    Opportunity,
    catalog_stats,
    get_opportunity,
    list_filtered,
    rank_opportunities,
)
from apps.backend.src.core.opportunity_scoring import rank_opportunities_v1
from apps.backend.src.core.duplicates import _collect_existing_titles
from apps.backend.src.core.auth import get_current_user

router = APIRouter(
    prefix="/opportunities",
    tags=["opportunities"],
    dependencies=[Depends(get_current_user)],  # any authenticated user
)


# ---------------------------------------------------------------------------
# Pydantic response model
# ---------------------------------------------------------------------------

class OpportunityOut(BaseModel):
    id: str
    name: str
    organization: str
    platform: str
    access_type: str
    program_url: str
    scope_url: str
    scope_summary: str
    scope_domains: List[str]
    max_payout_usd: int
    min_payout_usd: int
    vdp_only: bool
    response_sla_days: int
    tags: List[str]
    vuln_types: List[str]
    priority_score: float
    is_public: bool
    payout_label: str
    notes: str


def _out(o: Opportunity) -> OpportunityOut:
    return OpportunityOut(
        id=o.id,
        name=o.name,
        organization=o.organization,
        platform=o.platform,
        access_type=o.access_type,
        program_url=o.program_url,
        scope_url=o.scope_url,
        scope_summary=o.scope_summary,
        scope_domains=o.scope_domains,
        max_payout_usd=o.max_payout_usd,
        min_payout_usd=o.min_payout_usd,
        vdp_only=o.vdp_only,
        response_sla_days=o.response_sla_days,
        tags=o.tags,
        vuln_types=o.vuln_types,
        priority_score=round(o.priority_score, 4),
        is_public=o.is_public(),
        payout_label=o.payout_label(),
        notes=o.notes,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
async def list_opportunities(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    access_type: Optional[str] = Query(None, description="Filter by access_type"),
    min_payout: Optional[int] = Query(None, ge=0),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    public_only: bool = Query(False),
    sort_by: str = Query("score", description="score | payout | name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    tags = [tag] if tag else None
    results = list_filtered(
        platform=platform,
        access_type=access_type,
        min_payout=min_payout,
        tags=tags,
        search=search,
        public_only=public_only,
    )
    # Sort
    if sort_by == "payout":
        results = sorted(results, key=lambda o: o.max_payout_usd, reverse=True)
    elif sort_by == "name":
        results = sorted(results, key=lambda o: o.name.lower())
    else:  # "score" default
        results = sorted(results, key=lambda o: o.priority_score, reverse=True)

    total = len(results)
    page = results[offset: offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "opportunities": [_out(o) for o in page],
    }


@router.get("/ranked", response_model=dict)
async def ranked_opportunities(
    limit: int = Query(50, ge=1, le=500),
    public_only: bool = Query(False),
):
    ranked = rank_opportunities(public_only=public_only)[:limit]
    return {
        "count": len(ranked),
        "opportunities": [_out(o) for o in ranked],
    }


@router.get("/ranked_v1", response_model=dict)
async def ranked_opportunities_v1(
    limit: int = Query(50, ge=1, le=500),
    public_only: bool = Query(False),
    effort_bias: float = Query(0.5, ge=0.0, le=1.0, description="Higher values penalize high-effort programs more"),
):
    opportunities = rank_opportunities(public_only=public_only)
    prior_reports = _collect_existing_titles()
    scored = rank_opportunities_v1(
        opportunities,
        prior_reports=prior_reports,
        effort_bias=effort_bias,
    )[:limit]
    score_lookup = {s.opportunity_id: s for s in scored}
    rows = []
    for opp in opportunities:
        score = score_lookup.get(opp.id)
        if not score:
            continue
        row = _out(opp).model_dump(mode="json")
        row["v1_score"] = round(score.score, 4)
        row["v1_factors"] = {k: round(v, 4) for k, v in score.factors.items()}
        row["v1_reasoning"] = score.reasoning
        rows.append(row)
    return {
        "count": len(rows),
        "effort_bias": effort_bias,
        "opportunities": rows,
    }


@router.get("/stats")
async def get_stats():
    return catalog_stats()


@router.get("/{opp_id}", response_model=OpportunityOut)
async def get_opp(opp_id: str):
    o = get_opportunity(opp_id)
    if o is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opp_id!r} not found")
    return _out(o)
