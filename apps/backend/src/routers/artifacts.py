"""
Artifact Browser API
====================
API for browsing and retrieving mission artifacts, including tool outputs,
logs, and normalized security evidence.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.backend.src.auth.dependencies import require_roles, CurrentUser
from apps.backend.src.auth.models import UserRole
from apps.backend.src.core.hil_db import get_db
from apps.backend.src.core.praison_mission_runtime import get_mission_runtime
from apps.backend.src.models.campaign import Artifact
from apps.backend.src.schemas.campaigns import ArtifactRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _enforce_mission_tenant_access(current_user: CurrentUser, mission_id: UUID) -> None:
    runtime = get_mission_runtime()
    tenant_id = runtime.tenant_for_mission(str(mission_id))
    if tenant_id is None:
        return
    if tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="mission_out_of_scope")


@router.get("/mission/{mission_id}", response_model=list[ArtifactRead])
async def list_mission_artifacts(
    mission_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """List all artifacts produced by a specific mission."""
    _enforce_mission_tenant_access(current_user, mission_id)
    stmt = select(Artifact).where(
        Artifact.campaign_id == mission_id
    ).order_by(Artifact.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{artifact_id}", response_model=ArtifactRead)
async def get_artifact(
    artifact_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Get metadata for a specific artifact."""
    stmt = select(Artifact).where(Artifact.id == artifact_id)
    result = await db.execute(stmt)
    artifact = result.scalar_one_or_none()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    _enforce_mission_tenant_access(current_user, artifact.campaign_id)
    
    return artifact


@router.get("/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """
    Retrieve the actual content of an artifact.
    For inline artifacts, returns the stored JSON/text.
    For file artifacts, returns the file content (future implementation).
    """
    stmt = select(Artifact).where(Artifact.id == artifact_id)
    result = await db.execute(stmt)
    artifact = result.scalar_one_or_none()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    _enforce_mission_tenant_access(current_user, artifact.campaign_id)
    
    # Return inline content if available
    details = artifact.details_json if isinstance(artifact.details_json, dict) else {}
    if details.get("inline") or "result_payload_json" in details:
        return details.get("result_payload_json") or details
    
    # Redirect to URI or handle file system (simplified)
    return {"uri": artifact.uri, "mime_type": artifact.mime_type}
