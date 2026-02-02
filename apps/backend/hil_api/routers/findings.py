from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Finding, Evidence
from ..security import RBAC, Permission
import binascii

router = APIRouter(prefix="/findings", tags=["findings"])

class FindingCreate(BaseModel):
    program: str
    asset: str
    title: str
    description: str
    severity: str

@router.post("/", dependencies=[Depends(RBAC(Permission.INITIATE_SCAN))])
def create_finding(body: FindingCreate, db: Session = Depends(get_db)):
    f = Finding(program=body.program, asset=body.asset, title=body.title, description=body.description, severity=body.severity)
    db.add(f)
    db.flush()
    return {"id": str(f.id)}

class EvidenceCreate(BaseModel):
    kind: str
    uri: str
    sha256_hex: str
    meta: dict = {}

@router.post("/{finding_id}/evidence", dependencies=[Depends(RBAC(Permission.SUBMIT_FINDINGS))])
def add_evidence(finding_id: str, body: EvidenceCreate, db: Session = Depends(get_db)):
    f = db.get(Finding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    try:
        digest = binascii.unhexlify(body.sha256_hex)
    except Exception:
        raise HTTPException(422, "Invalid sha256 hex")
    ev = Evidence(finding_id=f.id, kind=body.kind, uri=body.uri, sha256=digest, meta=body.meta)
    db.add(ev)
    return {"evidence_id": str(ev.id)}

@router.get("/{finding_id}/evidence", dependencies=[Depends(RBAC(Permission.VIEW_FINDINGS))])
def list_evidence(finding_id: str, db: Session = Depends(get_db)):
    f = db.get(Finding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    return [{"id": str(e.id), "kind": e.kind, "uri": e.uri, "sha256": e.sha256.hex(), "meta": e.meta} for e in f.evidences]
