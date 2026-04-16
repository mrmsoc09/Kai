from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, User, require_roles
from ..core.hil_db import get_db
from ..models.attack_path import AttackPathEdge, AttackPathNode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attack-paths", tags=["attack-paths"])

VALID_NODE_TYPES = {"asset", "endpoint", "parameter", "finding", "evidence", "auth_boundary"}
VALID_RELATIONSHIP_TYPES = {"leads_to", "exploits", "bypasses", "discovers"}


class AttackPathNodeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mission_id: UUID | None = None
    node_type: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=1024)
    metadata_json: dict = Field(default_factory=dict)


class AttackPathNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mission_id: UUID | None = None
    node_type: str
    label: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class AttackPathEdgeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_node_id: UUID
    target_node_id: UUID
    relationship_type: str = Field(..., min_length=1, max_length=64)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AttackPathEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    relationship_type: str
    confidence: float
    created_at: datetime


class AttackPathGraphResponse(BaseModel):
    nodes: list[AttackPathNodeRead]
    edges: list[AttackPathEdgeRead]


@router.post("/nodes", response_model=AttackPathNodeRead, status_code=201)
async def create_attack_path_node(
    body: AttackPathNodeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> AttackPathNodeRead:
    if body.node_type not in VALID_NODE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid node_type '{body.node_type}'. Allowed: {sorted(VALID_NODE_TYPES)}",
        )
    node = AttackPathNode(
        mission_id=body.mission_id,
        node_type=body.node_type,
        label=body.label,
        metadata_json=body.metadata_json,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    logger.info(
        "attack_path_node.created id=%s node_type=%s mission_id=%s",
        node.id,
        node.node_type,
        node.mission_id,
    )
    return AttackPathNodeRead.model_validate(node)


@router.post("/edges", response_model=AttackPathEdgeRead, status_code=201)
async def create_attack_path_edge(
    body: AttackPathEdgeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> AttackPathEdgeRead:
    if body.relationship_type not in VALID_RELATIONSHIP_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid relationship_type '{body.relationship_type}'. "
                f"Allowed: {sorted(VALID_RELATIONSHIP_TYPES)}"
            ),
        )
    # Verify source and target nodes exist
    src_result = await db.execute(
        select(AttackPathNode).where(AttackPathNode.id == body.source_node_id)
    )
    if src_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404, detail=f"Source node not found: {body.source_node_id}"
        )
    tgt_result = await db.execute(
        select(AttackPathNode).where(AttackPathNode.id == body.target_node_id)
    )
    if tgt_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404, detail=f"Target node not found: {body.target_node_id}"
        )
    edge = AttackPathEdge(
        source_node_id=body.source_node_id,
        target_node_id=body.target_node_id,
        relationship_type=body.relationship_type,
        confidence=body.confidence,
        created_at=datetime.now(timezone.utc),
    )
    db.add(edge)
    await db.flush()
    await db.refresh(edge)
    logger.info(
        "attack_path_edge.created id=%s %s -[%s]-> %s",
        edge.id,
        body.source_node_id,
        body.relationship_type,
        body.target_node_id,
    )
    return AttackPathEdgeRead.model_validate(edge)


@router.get("/", response_model=AttackPathGraphResponse)
async def get_attack_path_graph(
    mission_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> AttackPathGraphResponse:
    node_stmt = select(AttackPathNode).order_by(AttackPathNode.created_at.asc())
    if mission_id is not None:
        node_stmt = node_stmt.where(AttackPathNode.mission_id == mission_id)
    if current_user.tenant_id:
        node_stmt = node_stmt.where(AttackPathNode.tenant_id == current_user.tenant_id)
    node_result = await db.execute(node_stmt)
    nodes = list(node_result.scalars().all())
    node_ids = [n.id for n in nodes]

    edges: list[AttackPathEdge] = []
    if node_ids:
        edge_stmt = select(AttackPathEdge).where(
            AttackPathEdge.source_node_id.in_(node_ids)
        )
        if current_user.tenant_id:
            edge_stmt = edge_stmt.where(AttackPathEdge.tenant_id == current_user.tenant_id)
        edge_result = await db.execute(edge_stmt)
        edges = list(edge_result.scalars().all())

    return AttackPathGraphResponse(
        nodes=[AttackPathNodeRead.model_validate(n) for n in nodes],
        edges=[AttackPathEdgeRead.model_validate(e) for e in edges],
    )
