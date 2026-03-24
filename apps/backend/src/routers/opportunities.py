"""Opportunity Hub + governed action flow."""

from __future__ import annotations

from fnmatch import fnmatchcase
import re
from uuid import UUID
from typing import Any, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.src.core.opportunity_catalog import (
    CredentialRequirement,
    Opportunity,
    catalog_stats,
    get_opportunity,
    list_filtered,
    rank_opportunities,
)
from apps.backend.src.core.opportunity_scoring import rank_opportunities_v1
from apps.backend.src.core.duplicates import collect_existing_titles
from apps.backend.src.core.auth import (
    ROLE_ADMIN,
    ROLE_ANALYST,
    User,
    get_current_user,
    require_roles,
)
from apps.backend.src.core.hil_db import get_db
from apps.backend.src.auth.models import UserScanQueueSettings
from apps.backend.src.core.opportunity_actions import get_opportunity_action_service
from apps.backend.src.core.opportunity_engine import get_opportunity_engine
from apps.backend.src.core.opportunity_expansion import ExpansionCandidate, OpportunityExpansionResult, TargetBatch
from apps.backend.src.core.intelligence_memory import get_memory_manager

router = APIRouter(
    prefix="/opportunities",
    tags=["opportunities"],
    dependencies=[Depends(get_current_user)],  # any authenticated user
)

SCAN_QUEUE_MIN_CONCURRENCY = 1
SCAN_QUEUE_MAX_CONCURRENCY = 20
SCAN_QUEUE_DEFAULT_MIN = 1
SCAN_QUEUE_DEFAULT_MAX = 3


# ---------------------------------------------------------------------------
# Pydantic response model
# ---------------------------------------------------------------------------

class CredentialRequirementOut(BaseModel):
    kind: str
    label: str
    signup_url: str
    notes: str
    required: bool


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
    credential_requirements: List[CredentialRequirementOut]
    needs_credentials: bool   # True when at least one required credential exists
    status: str
    approval_state: str
    approval_reason: str | None = None
    rejection_reason: str | None = None
    execution_metadata: dict[str, Any]
    source_memory_id: str | None = None
    source_pattern_id: str | None = None
    source_type: str | None = None
    source_object_id: str | None = None
    candidate_targets: List[str]
    expansion_candidates: List[dict[str, Any]] = []
    approved_targets: List[str] = []
    rejected_targets: List[str] = []
    target_batches: List[dict[str, Any]] = []
    expansion_rationale: str = ""
    expansion_score: float = 0.0
    expected_report_quality: float = 0.0
    recommended_execution_order: List[str] = []
    linked_mission_count: int = 0
    linked_report_count: int = 0
    decision_summary: str | None = None
    chain_summary: dict[str, Any] | None = None
    confidence_score: float
    estimated_yield: float
    expected_yield: float = 0.0
    duplicate_risk: float
    created_at: str
    updated_at: str
    created_by: str | None = None


class OpportunityActionCapabilities(BaseModel):
    approve: bool
    reject: bool
    execute: bool
    reason: str
    requires_role: str


class OpportunityDecisionRequest(BaseModel):
    reason: str | None = None
    approved_targets: list[str] | None = None
    rejected_targets: list[str] | None = None
    batch_ids: list[str] | None = None


class OpportunityExecuteRequest(BaseModel):
    reason: str | None = None
    execution_mode: str = "live"
    max_targets: int | None = None


class OpportunityExpandRequest(BaseModel):
    vuln_type: str | None = None
    candidate_targets: list[str] | None = None


class ScanQueueSettingsResponse(BaseModel):
    min_concurrent: int
    max_concurrent: int


class ScanQueueSettingsUpdateRequest(BaseModel):
    min_concurrent: int = Field(..., ge=SCAN_QUEUE_MIN_CONCURRENCY, le=SCAN_QUEUE_MAX_CONCURRENCY)
    max_concurrent: int = Field(..., ge=SCAN_QUEUE_MIN_CONCURRENCY, le=SCAN_QUEUE_MAX_CONCURRENCY)


def _tenant_context(user: User, *, require_tenant: bool = False) -> str:
    if user.tenant_id:
        return user.tenant_id
    if require_tenant:
        raise HTTPException(status_code=400, detail="tenant_context_required")
    return "__global__"


def _scan_queue_owner_ids(user: User) -> tuple[UUID, UUID]:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="tenant_context_required")
    try:
        return UUID(str(user.id)), UUID(str(user.tenant_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_auth_identity") from exc


def _validated_scan_queue_bounds(payload: ScanQueueSettingsUpdateRequest) -> tuple[int, int]:
    min_concurrent = int(payload.min_concurrent)
    max_concurrent = int(payload.max_concurrent)
    if min_concurrent > max_concurrent:
        raise HTTPException(status_code=400, detail="scan_queue_min_exceeds_max")
    return min_concurrent, max_concurrent


def _normalize_target(value: str) -> str:
    row = str(value or "").strip().lower()
    if not row:
        return ""
    if "://" in row:
        parsed = urlparse(row)
        row = parsed.hostname or parsed.path or row
    if ":" in row:
        row = row.split(":", 1)[0]
    return row.strip(".")


def _matches_scope(target: str, pattern: str) -> bool:
    normalized_target = _normalize_target(target)
    normalized_pattern = _normalize_target(pattern)
    if not normalized_target or not normalized_pattern:
        return False
    if any(ch in normalized_pattern for ch in "*?[]"):
        return fnmatchcase(normalized_target, normalized_pattern)
    return normalized_target == normalized_pattern or normalized_target.endswith(f".{normalized_pattern}")


def _discover_scope_targets(opportunity: Opportunity, *, limit: int = 300) -> list[str]:
    manager = get_memory_manager()
    entries = manager.query(min_confidence=0.3, limit=max(limit * 8, 500))
    discovered: set[str] = set()
    for entry in entries:
        domain = _normalize_target(entry.target_fingerprint.domain)
        if not domain:
            continue
        if any(_matches_scope(domain, pattern) for pattern in opportunity.scope_domains):
            discovered.add(domain)

    for scope_target in opportunity.scope_domains:
        normalized = _normalize_target(scope_target)
        if normalized and "*" not in normalized:
            discovered.add(normalized)
    return sorted(discovered)[:limit]


def _expansion_from_inference(payload: dict[str, Any], *, vuln_type: str) -> OpportunityExpansionResult:
    candidates = [
        ExpansionCandidate(
            target=str(row.get("target", "")),
            similarity_score=float(row.get("similarity_score", 0.0)),
            confidence=float(row.get("confidence", 0.0)),
            memory_match_strength=float(row.get("memory_match_strength", 0.0)),
            duplicate_risk=float(row.get("duplicate_risk", 0.0)),
            target_importance=float(row.get("target_importance", 0.0)),
            expected_report_quality=float(row.get("expected_report_quality", 0.0)),
            expansion_score=float(row.get("expansion_score", 0.0)),
            estimated_yield=float(row.get("estimated_yield", 0.0)),
            risk_band=str(row.get("risk_band", "medium")),
            matching_factors=[str(value) for value in row.get("matching_factors", []) if str(value)],
            rationale=str(row.get("rationale", "")),
        )
        for row in payload.get("expansion_candidates", [])
        if isinstance(row, dict)
    ]
    batches = [
        TargetBatch(
            batch_id=str(row.get("batch_id", "")),
            targets=[str(value) for value in row.get("targets", []) if str(value)],
            expected_yield=float(row.get("expected_yield", 0.0)),
            risk_band=str(row.get("risk_band", "medium")),
            rationale=str(row.get("rationale", "")),
        )
        for row in payload.get("target_batches", [])
        if isinstance(row, dict)
    ]
    blocked_targets = [dict(row) for row in payload.get("blocked_targets", []) if isinstance(row, dict)]
    return OpportunityExpansionResult(
        source_type=str(payload.get("source_type", "validated_finding")),
        source_object_id=str(payload.get("source_object_id") or payload.get("source_memory_id") or ""),
        source_vuln_type=vuln_type,
        source_target="",
        expansion_candidates=candidates,
        target_batches=batches,
        blocked_targets=blocked_targets,
        expansion_score=float(payload.get("expansion_score", 0.0)),
        expected_yield=float(payload.get("estimated_yield", payload.get("expected_yield", 0.0))),
        duplicate_risk=float(payload.get("duplicate_risk", 0.0)),
        confidence=float(payload.get("confidence_score", 0.0)),
        expected_report_quality=float(payload.get("expected_report_quality", 0.0)),
        recommended_execution_order=[str(value) for value in payload.get("recommended_execution_order", []) if str(value)],
        expansion_rationale=str(payload.get("expansion_rationale", "")),
    )


def _parse_chain_summary_from_notes(notes: str) -> dict[str, Any] | None:
    text = str(notes or "").strip()
    if not text:
        return None
    match_count = re.search(r"chain_count=(\d+)", text)
    match_bonus = re.search(r"chain_bonus=([0-9.]+)", text)
    match_ids = re.search(r"chain_ids=([^;]+)", text)
    chain_count = int(match_count.group(1)) if match_count else 0
    chain_bonus = float(match_bonus.group(1)) if match_bonus else 0.0
    chain_ids = [row.strip() for row in match_ids.group(1).split(",")] if match_ids and match_ids.group(1).strip() else []
    if chain_count <= 0 and chain_bonus <= 0 and not chain_ids:
        return None
    return {
        "chain_count": chain_count,
        "chain_bonus": chain_bonus,
        "chain_ids": chain_ids,
        "has_chain": chain_count > 0 or bool(chain_ids),
    }


def _out(o: Opportunity, state: dict[str, Any]) -> OpportunityOut:
    execution_metadata = dict(state.get("execution_metadata", {}))
    mission_ids = [str(value) for value in execution_metadata.get("mission_ids", []) if str(value)]
    report_ids = [str(value) for value in execution_metadata.get("report_ids", []) if str(value)]
    source_context = execution_metadata.get("source_context", {}) if isinstance(execution_metadata.get("source_context"), dict) else {}
    cred_outs = [
        CredentialRequirementOut(
            kind=cr.kind,
            label=cr.label,
            signup_url=cr.signup_url,
            notes=cr.notes,
            required=cr.required,
        )
        for cr in o.credential_requirements
    ]
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
        credential_requirements=cred_outs,
        needs_credentials=any(cr.required for cr in o.credential_requirements),
        status=str(state.get("status", "proposed")),
        approval_state=str(state.get("approval_state", "pending")),
        approval_reason=state.get("approval_reason"),
        rejection_reason=state.get("rejection_reason"),
        execution_metadata=execution_metadata,
        source_memory_id=state.get("source_memory_id"),
        source_pattern_id=state.get("source_pattern_id"),
        source_type=state.get("source_type"),
        source_object_id=state.get("source_object_id"),
        candidate_targets=[str(value) for value in state.get("candidate_targets", o.scope_domains)],
        expansion_candidates=[dict(row) for row in state.get("expansion_candidates", []) if isinstance(row, dict)],
        approved_targets=[str(value) for value in state.get("approved_targets", [])],
        rejected_targets=[str(value) for value in state.get("rejected_targets", [])],
        target_batches=[dict(row) for row in state.get("target_batches", []) if isinstance(row, dict)],
        expansion_rationale=str(state.get("expansion_rationale", "")),
        expansion_score=float(state.get("expansion_score", 0.0)),
        expected_report_quality=float(state.get("expected_report_quality", 0.0)),
        recommended_execution_order=[str(value) for value in state.get("recommended_execution_order", [])],
        linked_mission_count=len(mission_ids),
        linked_report_count=len(report_ids),
        decision_summary=(str(source_context.get("decision_summary")) if source_context.get("decision_summary") else None),
        chain_summary=(dict(source_context.get("chain_summary")) if isinstance(source_context.get("chain_summary"), dict) else None),
        confidence_score=float(state.get("confidence_score", o.priority_score)),
        estimated_yield=float(state.get("estimated_yield", round(float(o.priority_score) * max(1, len(o.scope_domains)) * 0.6, 2))),
        expected_yield=float(state.get("expected_yield", state.get("estimated_yield", round(float(o.priority_score) * max(1, len(o.scope_domains)) * 0.6, 2)))),
        duplicate_risk=float(state.get("duplicate_risk", 0.0)),
        created_at=str(state.get("created_at", "")),
        updated_at=str(state.get("updated_at", "")),
        created_by=state.get("created_by"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/actions/capabilities", response_model=OpportunityActionCapabilities)
async def opportunity_action_capabilities(current_user: User = Depends(get_current_user)):
    can_decide = any(role in {ROLE_ANALYST, ROLE_ADMIN} for role in current_user.roles)
    if not can_decide:
        return OpportunityActionCapabilities(
            approve=False,
            reject=False,
            execute=False,
            reason="Opportunity actions require analyst or admin role.",
            requires_role="analyst",
        )

    if not current_user.tenant_id:
        return OpportunityActionCapabilities(
            approve=True,
            reject=True,
            execute=False,
            reason="Tenant context is required for execution.",
            requires_role="analyst",
        )

    return OpportunityActionCapabilities(
        approve=True,
        reject=True,
        execute=True,
        reason="enabled",
        requires_role="analyst",
    )


@router.get("/scan-queue/settings", response_model=ScanQueueSettingsResponse)
async def get_scan_queue_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id, tenant_id = _scan_queue_owner_ids(current_user)
    result = await db.execute(
        select(UserScanQueueSettings).where(
            UserScanQueueSettings.user_id == user_id,
            UserScanQueueSettings.tenant_id == tenant_id,
        )
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        return ScanQueueSettingsResponse(
            min_concurrent=SCAN_QUEUE_DEFAULT_MIN,
            max_concurrent=SCAN_QUEUE_DEFAULT_MAX,
        )
    return ScanQueueSettingsResponse(
        min_concurrent=int(settings.min_concurrent),
        max_concurrent=int(settings.max_concurrent),
    )


@router.put("/scan-queue/settings", response_model=ScanQueueSettingsResponse)
async def update_scan_queue_settings(
    payload: ScanQueueSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id, tenant_id = _scan_queue_owner_ids(current_user)
    min_concurrent, max_concurrent = _validated_scan_queue_bounds(payload)

    result = await db.execute(
        select(UserScanQueueSettings).where(
            UserScanQueueSettings.user_id == user_id,
            UserScanQueueSettings.tenant_id == tenant_id,
        )
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserScanQueueSettings(
            user_id=user_id,
            tenant_id=tenant_id,
            min_concurrent=min_concurrent,
            max_concurrent=max_concurrent,
        )
        db.add(settings)
    else:
        settings.min_concurrent = min_concurrent
        settings.max_concurrent = max_concurrent

    await db.commit()
    await db.refresh(settings)
    return ScanQueueSettingsResponse(
        min_concurrent=int(settings.min_concurrent),
        max_concurrent=int(settings.max_concurrent),
    )

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
    current_user: User = Depends(get_current_user),
):
    tenant_id = _tenant_context(current_user)
    service = get_opportunity_action_service()
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
        "opportunities": [
            _out(o, service.merge_opportunity_view(o, tenant_id=tenant_id, created_by=current_user.id))
            for o in page
        ],
    }


@router.get("/ranked", response_model=dict)
async def ranked_opportunities(
    limit: int = Query(50, ge=1, le=500),
    public_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    tenant_id = _tenant_context(current_user)
    service = get_opportunity_action_service()
    ranked = rank_opportunities(public_only=public_only)[:limit]
    return {
        "count": len(ranked),
        "opportunities": [
            _out(o, service.merge_opportunity_view(o, tenant_id=tenant_id, created_by=current_user.id))
            for o in ranked
        ],
    }


@router.get("/ranked_v1", response_model=dict)
async def ranked_opportunities_v1(
    limit: int = Query(50, ge=1, le=500),
    public_only: bool = Query(False),
    effort_bias: float = Query(0.5, ge=0.0, le=1.0, description="Higher values penalize high-effort programs more"),
    current_user: User = Depends(get_current_user),
):
    tenant_id = _tenant_context(current_user)
    service = get_opportunity_action_service()
    opportunities = rank_opportunities(public_only=public_only)
    prior_reports = collect_existing_titles()
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
        row = _out(
            opp,
            service.merge_opportunity_view(opp, tenant_id=tenant_id, created_by=current_user.id),
        ).model_dump(mode="json")
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
async def get_opp(opp_id: str, current_user: User = Depends(get_current_user)):
    o = get_opportunity(opp_id)
    if o is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opp_id!r} not found")
    tenant_id = _tenant_context(current_user)
    service = get_opportunity_action_service()
    return _out(o, service.merge_opportunity_view(o, tenant_id=tenant_id, created_by=current_user.id))


@router.post(
    "/{opp_id}/expand",
    response_model=OpportunityOut,
    dependencies=[Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))],
)
async def expand_opp(
    opp_id: str,
    body: OpportunityExpandRequest,
    current_user: User = Depends(get_current_user),
):
    opp = get_opportunity(opp_id)
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opp_id!r} not found")

    tenant_id = _tenant_context(current_user)
    vuln_type = (body.vuln_type or (opp.vuln_types[0] if opp.vuln_types else "")).strip().lower()
    if not vuln_type:
        raise HTTPException(status_code=400, detail="vuln_type_required")

    candidate_targets = [
        _normalize_target(value)
        for value in (body.candidate_targets or _discover_scope_targets(opp))
        if _normalize_target(value)
    ]
    if not candidate_targets:
        raise HTTPException(status_code=404, detail="no_candidate_targets_for_expansion")

    engine = get_opportunity_engine()
    detections = engine.detect_for_vuln_type(
        vuln_type=vuln_type,
        allowed_domains=candidate_targets,
        min_confidence=0.55,
    )
    if not detections:
        raise HTTPException(status_code=404, detail="no_validated_source_for_expansion")

    ranked = sorted(
        detections,
        key=lambda row: (float(row.expansion_score), float(row.estimated_yield), float(row.confidence_score)),
        reverse=True,
    )
    selected = ranked[0]
    payload = selected.to_dict()
    expansion = _expansion_from_inference(payload, vuln_type=vuln_type)
    decision_summary = str(payload.get("notes", "")).strip() or None
    chain_summary = _parse_chain_summary_from_notes(str(payload.get("notes", "")))
    recommended_tools = [str(value) for value in payload.get("recommended_tools", []) if str(value)]
    service = get_opportunity_action_service()
    state = service.apply_expansion(
        opp,
        tenant_id=tenant_id,
        actor=current_user.id,
        source_type=str(payload.get("source_type", "validated_finding")),
        source_object_id=str(payload.get("source_object_id") or payload.get("source_memory_id") or ""),
        source_memory_id=(str(payload.get("source_memory_id")) if payload.get("source_memory_id") else None),
        source_pattern_id=(str(payload.get("pattern_signature_id")) if payload.get("pattern_signature_id") else None),
        expansion=expansion,
        source_context={
            "decision_summary": decision_summary,
            "chain_summary": chain_summary,
            "recommended_tools": recommended_tools,
            "source_vuln_type": vuln_type,
        },
    )
    return _out(opp, state.to_dict())


@router.post("/{opp_id}/approve", response_model=OpportunityOut, dependencies=[Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))])
async def approve_opp(
    opp_id: str,
    body: OpportunityDecisionRequest,
    current_user: User = Depends(get_current_user),
):
    opp = get_opportunity(opp_id)
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opp_id!r} not found")
    service = get_opportunity_action_service()
    tenant_id = _tenant_context(current_user)
    try:
        state = service.approve(
            opp,
            tenant_id=tenant_id,
            actor=current_user.id,
            reason=body.reason,
            approved_targets=body.approved_targets,
            rejected_targets=body.rejected_targets,
            batch_ids=body.batch_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _out(opp, state.to_dict())


@router.post("/{opp_id}/reject", response_model=OpportunityOut, dependencies=[Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))])
async def reject_opp(
    opp_id: str,
    body: OpportunityDecisionRequest,
    current_user: User = Depends(get_current_user),
):
    opp = get_opportunity(opp_id)
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opp_id!r} not found")
    service = get_opportunity_action_service()
    tenant_id = _tenant_context(current_user)
    try:
        state = service.reject(
            opp,
            tenant_id=tenant_id,
            actor=current_user.id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _out(opp, state.to_dict())


@router.post("/{opp_id}/execute", response_model=OpportunityOut, dependencies=[Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))])
async def execute_opp(
    opp_id: str,
    body: OpportunityExecuteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    opp = get_opportunity(opp_id)
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity {opp_id!r} not found")
    service = get_opportunity_action_service()
    tenant_id = _tenant_context(current_user, require_tenant=True)
    try:
        state = service.execute(
            opp,
            tenant_id=tenant_id,
            actor=current_user.id,
            reason=body.reason,
            execution_mode=body.execution_mode,
            max_targets=body.max_targets,
        )
    except ValueError as exc:
        detail = str(exc)
        status = 400 if detail in {"approval_required", "tenant_context_invalid"} else 409
        raise HTTPException(status_code=status, detail=detail)

    if state.status == "executing":
        background_tasks.add_task(service.start_execution_missions, state)

    return _out(opp, state.to_dict())
