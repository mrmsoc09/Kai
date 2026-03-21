from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.auth import (
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    User,
    get_current_user,
    require_roles,
)
from ..core.intelligence_graph import get_intelligence_graph
from ..core.intelligence_memory import MemoryEntry, MemoryScope, MemoryType, ValidationStatus, get_memory_manager
from ..schemas.intel import Finding

router = APIRouter(prefix="/intel", tags=["intelligence"])

_SAMPLE: List[Finding] = [
    Finding(
        id="f-001",
        title="Missing security headers",
        severity="low",
        type="Web/Headers",
        target_asset="app.example.com",
        chain_value=20,
        chain_potential="low",
        stage="discovered",
        status="open",
        evidence_completeness=40,
    ),
    Finding(
        id="f-002",
        title="Weak JWT validation",
        severity="medium",
        type="Auth/JWT",
        target_asset="api.example.com",
        chain_value=55,
        chain_potential="medium",
        stage="validated",
        status="in_progress",
        evidence_completeness=70,
    ),
    Finding(
        id="f-003",
        title="IDOR read on test tenant",
        severity="high",
        type="Access Control/IDOR",
        target_asset="api.example.com",
        chain_value=80,
        chain_potential="high",
        stage="validated",
        status="open",
        evidence_completeness=85,
    ),
    Finding(
        id="f-004",
        title="Public S3 bucket",
        severity="critical",
        type="Cloud/S3",
        target_asset="assets.example.com",
        chain_value=90,
        chain_potential="high",
        stage="exploited",
        status="in_progress",
        evidence_completeness=95,
    ),
    Finding(
        id="f-005",
        title="Outdated dependency",
        severity="medium",
        type="Supply/Dependency",
        target_asset="worker.example.com",
        chain_value=35,
        chain_potential="medium",
        stage="mitigated",
        status="closed",
        evidence_completeness=100,
    ),
]


class MemoryRecord(BaseModel):
    memory_id: str
    memory_type: str
    scope: str
    domain: str
    ip: str | None = None
    tech_stack: list[str]
    services: list[str]
    tags: list[str]
    confidence_score: float
    validation_status: str
    source_mission_id: str
    mission_phase: str | None = None
    created_at: str
    relationships: list[str]


class MemoryListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[MemoryRecord]


def _is_admin(user: User) -> bool:
    return ROLE_ADMIN in user.roles


def _memory_visible_to_user(entry: MemoryEntry, user: User) -> bool:
    if _is_admin(user):
        return True
    if not user.tenant_id:
        return True
    return bool(entry.tenant_id) and entry.tenant_id == user.tenant_id


def _to_memory_record(entry: MemoryEntry) -> MemoryRecord:
    return MemoryRecord(
        memory_id=entry.memory_id,
        memory_type=entry.memory_type.value,
        scope=entry.scope.value,
        domain=entry.target_fingerprint.domain,
        ip=entry.target_fingerprint.ip,
        tech_stack=entry.target_fingerprint.tech_stack,
        services=entry.target_fingerprint.services,
        tags=entry.tags,
        confidence_score=round(entry.confidence_score, 4),
        validation_status=entry.validation_status.value,
        source_mission_id=entry.source_mission_id,
        mission_phase=entry.mission_phase,
        created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc).isoformat(),
        relationships=entry.relationships,
    )


@router.get("/findings", response_model=List[Finding])
def findings(
    chain_potential: Optional[str] = Query(default=None),
    stage: Optional[str] = Query(default=None),
    user: User = Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    data = _SAMPLE
    if chain_potential:
        data = [f for f in data if f.chain_potential == chain_potential]
    if stage:
        data = [f for f in data if f.stage == stage]
    return data


@router.get("/memory", response_model=MemoryListResponse)
def list_memory(
    scope: str | None = Query(default=None, description="short|mid|long|strategic"),
    memory_type: str | None = Query(default=None),
    validation_status: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    manager = get_memory_manager()
    tenant_filter = None if _is_admin(user) or not user.tenant_id else user.tenant_id

    try:
        parsed_scope = MemoryScope(scope) if scope else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid scope: {scope}") from exc

    try:
        parsed_memory_type = MemoryType(memory_type) if memory_type else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid memory_type: {memory_type}") from exc

    try:
        parsed_validation = ValidationStatus(validation_status) if validation_status else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid validation_status: {validation_status}") from exc

    entries = manager.query(
        scope=parsed_scope,
        memory_type=parsed_memory_type,
        min_confidence=min_confidence,
        validation_status=parsed_validation,
        domain=domain,
        tenant_id=tenant_filter,
        limit=max(limit + offset, 500),
    )

    if search:
        lowered = search.lower()
        entries = [
            entry
            for entry in entries
            if lowered in entry.memory_id.lower()
            or lowered in entry.source_mission_id.lower()
            or lowered in entry.target_fingerprint.domain.lower()
            or any(lowered in tag.lower() for tag in entry.tags)
            or lowered in entry.memory_type.value.lower()
        ]

    sorted_entries = sorted(entries, key=lambda entry: entry.created_at, reverse=True)
    page = sorted_entries[offset : offset + limit]
    items = [_to_memory_record(entry) for entry in page]
    return MemoryListResponse(total=len(sorted_entries), offset=offset, limit=limit, items=items)


@router.get("/memory/{memory_id}", response_model=MemoryRecord)
def get_memory(memory_id: str, user: User = Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))):
    manager = get_memory_manager()
    entry = manager.get(memory_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"memory {memory_id} not found")
    if not _memory_visible_to_user(entry, user):
        raise HTTPException(status_code=404, detail=f"memory {memory_id} not found")
    return _to_memory_record(entry)


@router.get("/memory/{memory_id}/relationships")
def get_memory_relationships(
    memory_id: str,
    user: User = Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    manager = get_memory_manager()
    source_entry = manager.get(memory_id)
    if not source_entry or not _memory_visible_to_user(source_entry, user):
        raise HTTPException(status_code=404, detail=f"memory {memory_id} not found")

    def _allow_edge(node_id: str) -> bool:
        target_entry = manager.get(node_id)
        if target_entry is None:
            return _is_admin(user) or not user.tenant_id
        return _memory_visible_to_user(target_entry, user)

    graph = get_intelligence_graph()
    outbound = [edge.to_dict() for edge in graph.get_neighbors(memory_id, direction="outbound") if _allow_edge(edge.target_id)]
    inbound = [edge.to_dict() for edge in graph.get_neighbors(memory_id, direction="inbound") if _allow_edge(edge.source_id)]
    return {"memory_id": memory_id, "outbound": outbound, "inbound": inbound}


@router.get("/memory/stats")
def get_memory_stats(user: User = Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN))):
    manager = get_memory_manager()
    if _is_admin(user) or not user.tenant_id:
        graph = get_intelligence_graph()
        return {
            "memory": manager.get_metrics(),
            "graph": graph.to_summary(),
        }

    tenant_id = user.tenant_id
    mid_entries = manager.query(scope=MemoryScope.MID_TERM, tenant_id=tenant_id, limit=10000)
    long_entries = manager.query(scope=MemoryScope.LONG_TERM, tenant_id=tenant_id, limit=10000)
    strategic_entries = manager.query(scope=MemoryScope.STRATEGIC, tenant_id=tenant_id, limit=10000)
    total_entries = len(mid_entries) + len(long_entries) + len(strategic_entries)
    graph_edge_count = sum(len(entry.relationships) for entry in [*mid_entries, *long_entries, *strategic_entries])
    return {
        "memory": {
            "short_term_count": 0,
            "mid_term_count": len(mid_entries),
            "long_term_count": len(long_entries),
            "strategic_count": len(strategic_entries),
            "tenant_total_count": total_entries,
        },
        "graph": {
            "node_count": total_entries,
            "edge_count": graph_edge_count,
            "edge_type_breakdown": {},
        },
    }
