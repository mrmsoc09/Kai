from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from ..db import get_db
from ..models import Finding, HILApproval, Report, AuditMerkleRoot
from ..models_extra import ProgramScope
from ..scope import enforce_scope, ScopeViolation
from ..security import RBAC, Permission, UserRole, get_current_user_role
from ..audit import merkle_root
from ..thehive_client import TheHiveClient
import hashlib

router = APIRouter(prefix="/hil", tags=["hil"])

class Checklist(BaseModel):
    repro_steps: bool
    http_traces_or_logs: bool
    poc_or_screencap: bool
    scope_confirmation: bool
    impact_rationale: bool

class HILRequest(BaseModel):
    notes: str | None = None

@router.post("/findings/{finding_id}/request", dependencies=[Depends(RBAC(Permission.VIEW_FINDINGS))])
def request_hil(finding_id: str, body: HILRequest, db: Session = Depends(get_db)):
    f = db.get(Finding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    existing = db.query(HILApproval).filter(HILApproval.finding_id==f.id).one_or_none()
    if existing:
        existing.status = 'PENDING'
        existing.notes = body.notes
    else:
        db.add(HILApproval(finding_id=f.id, approved_by='', status='PENDING', notes=body.notes))
    f.status = 'IN_REVIEW'
    return {"status": "PENDING"}

class HILApprove(BaseModel):
    checklist: Checklist
    notes: str | None = None

@router.post("/findings/{finding_id}/approve", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
def approve_hil(finding_id: str, body: HILApprove, db: Session = Depends(get_db), role: UserRole = Depends(get_current_user_role)):
    f = db.get(Finding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    hil = db.query(HILApproval).filter(HILApproval.finding_id==f.id).one_or_none()
    if not hil:
        hil = HILApproval(finding_id=f.id, approved_by='')
        db.add(hil)
    ck = body.checklist.model_dump()
    if not all(ck.values()):
        raise HTTPException(422, "Checklist not fully satisfied")
    # Scope enforcement
    policy = db.get(ProgramScope, f.program)
    try:
        enforce_scope(f, policy)
    except ScopeViolation as e:
        raise HTTPException(403, f'Scope violation: {str(e)}')
    hil.checklist = ck
    hil.status = 'APPROVED'
    hil.approved_by = role.value
    hil.approved_at = datetime.now(timezone.utc)
    f.status = 'HIL_APPROVED'
    return {"status": "APPROVED", "approved_at": hil.approved_at.isoformat()}

class SubmitBody(BaseModel):
    report_content_hash_hex: str

@router.post("/findings/{finding_id}/submit", dependencies=[Depends(RBAC(Permission.SUBMIT_FINDINGS))])
def submit_finding(finding_id: str, body: SubmitBody, db: Session = Depends(get_db)):
    f = db.get(Finding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    hil = db.query(HILApproval).filter(HILApproval.finding_id==f.id).one_or_none()
    if not hil or hil.status != 'APPROVED':
        raise HTTPException(403, "HiL approval required before submission")
    # Build manifest merkle from evidence
    if not f.evidences:
        raise HTTPException(422, "Evidence bundle required")
    hashes = [e.sha256 for e in f.evidences]
    root = merkle_root(hashes)
    try:
        report_hash = bytes.fromhex(body.report_content_hash_hex)
    except Exception:
        raise HTTPException(422, "Invalid report_content_hash_hex")
    report = Report(finding_id=f.id, content_hash=report_hash, manifest_hash=root)
    db.add(report)
    db.add(AuditMerkleRoot(run_id=str(f.id), root_hash=root))

    # Create TheHive case (fail closed on error)
    client = TheHiveClient()
    case_id = client.ensure_case(title=f.title, summary=f.description)

    f.status = 'SUBMITTED'
    return {"status": "SUBMITTED", "thehive_case_id": case_id}
