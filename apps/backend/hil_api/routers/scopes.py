from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List
from ..db import get_db
from ..models_extra import ProgramScope
from ..security import RBAC, Permission

router = APIRouter(prefix="/scopes", tags=["scopes"])

class ScopeUpsert(BaseModel):
    allowed_assets: Optional[List[str]] = None
    excluded_assets: Optional[List[str]] = None
    allowed_domains: Optional[List[str]] = None
    excluded_domains: Optional[List[str]] = None
    min_severity: Optional[str] = Field(default="LOW")
    notes: Optional[str] = None

@router.get("/{program}")
def get_scope(program: str, db: Session = Depends(get_db)):
    s = db.get(ProgramScope, program)
    if not s:
        return {"program": program, "policy": None}
    return {
        "program": program,
        "policy": {
            "allowed_assets": s.allowed_assets,
            "excluded_assets": s.excluded_assets,
            "allowed_domains": s.allowed_domains,
            "excluded_domains": s.excluded_domains,
            "min_severity": s.min_severity,
            "notes": s.notes,
        }
    }

@router.post("/{program}", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
def upsert_scope(program: str, body: ScopeUpsert, db: Session = Depends(get_db)):
    s = db.get(ProgramScope, program)
    if not s:
        s = ProgramScope(program=program)
        db.add(s)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    return {"status": "ok", "program": program}
