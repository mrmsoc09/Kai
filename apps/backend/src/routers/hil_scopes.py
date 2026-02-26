from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.hil_db import get_db
from ..core.hil_security import Permission, RBAC
from ..models.enums import SeverityEnum
from ..models.hil_extra import ProgramScope
from ..schemas.hil import ScopeUpsert


router = APIRouter(prefix="/scopes", tags=["hil-scopes"])


@router.get("/{program}")
async def get_scope(program: str, db: AsyncSession = Depends(get_db)):
    program = program.strip()
    result = await db.execute(
        select(ProgramScope).where(
            ProgramScope.program == program,
            ProgramScope.is_deleted.is_(False),
        )
    )
    scope = result.scalar_one_or_none()
    if not scope:
        return {"program": program, "policy": None}

    return {
        "program": scope.program,
        "policy": {
            "id": str(scope.id),
            "allowed_assets": scope.allowed_assets,
            "excluded_assets": scope.excluded_assets,
            "allowed_domains": scope.allowed_domains,
            "excluded_domains": scope.excluded_domains,
            "min_severity": scope.min_severity.value if scope.min_severity is not None else None,
            "notes": scope.notes,
        },
    }


@router.post("/{program}", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
async def upsert_scope(program: str, body: ScopeUpsert, db: AsyncSession = Depends(get_db)):
    program = program.strip()
    result = await db.execute(
        select(ProgramScope).where(
            ProgramScope.program == program,
            ProgramScope.is_deleted.is_(False),
        )
    )
    scope = result.scalar_one_or_none()
    if not scope:
        scope = ProgramScope(program=program)
        db.add(scope)

    payload = body.model_dump(exclude_unset=True)
    if "min_severity" in payload and payload["min_severity"] is not None:
        payload["min_severity"] = SeverityEnum(payload["min_severity"])

    for key, value in payload.items():
        setattr(scope, key, value)

    await db.flush()
    return {"status": "ok", "program": scope.program, "id": str(scope.id)}
