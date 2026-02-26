from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.execution_context import ExecutionContext
from ..core.hil_audit import merkle_root
from ..core.hil_db import get_db
from ..core.hil_scope import ScopeViolation, enforce_scope
from ..core.hil_security import Permission, RBAC, UserRole, get_current_user_role
from ..core.hil_thehive_client import TheHiveClient
from ..models.enums import FindingStatusEnum, HILApprovalStatusEnum
from ..models.hil import AuditMerkleRoot, Evidence, Finding, HILApproval, Report
from ..models.hil_extra import ProgramScope
from ..schemas.hil import HILApprove, HILRequest, SubmitBody


router = APIRouter(prefix="/hil", tags=["hil"])


def _parse_uuid(raw: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(422, f"{field_name} must be a UUID") from exc


async def _get_finding(db: AsyncSession, finding_id: uuid.UUID) -> Finding:
    result = await db.execute(
        select(Finding).where(Finding.id == finding_id, Finding.is_deleted.is_(False))
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(404, "Finding not found")
    return finding


@router.post("/findings/{finding_id}/request", dependencies=[Depends(RBAC(Permission.VIEW_FINDINGS))])
async def request_hil(
    finding_id: str,
    body: HILRequest,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    finding_uuid = _parse_uuid(finding_id, "finding_id")
    finding = await _get_finding(db, finding_uuid)

    try:
        ctx = ExecutionContext(
            db=db,
            operation="hil.request",
            resource_id=finding_uuid,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    cached = await ctx.begin()
    if cached is not None:
        return {**cached, "transaction_id": str(ctx.transaction_id), "idempotent_replay": True}

    stmt = insert(HILApproval).values(
        finding_id=finding.id,
        approved_by="pending",
        status=HILApprovalStatusEnum.PENDING,
        notes=body.notes,
        checklist={},
        is_deleted=False,
        deleted_at=None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[HILApproval.finding_id],
        set_={
            "status": HILApprovalStatusEnum.PENDING,
            "notes": body.notes,
            "is_deleted": False,
            "deleted_at": None,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)

    finding.status = FindingStatusEnum.IN_REVIEW
    response = {"status": HILApprovalStatusEnum.PENDING.value}
    ctx.complete(response)
    return {**response, "transaction_id": str(ctx.transaction_id)}


@router.post("/findings/{finding_id}/approve", dependencies=[Depends(RBAC(Permission.MANAGE_CONFIG))])
async def approve_hil(
    finding_id: str,
    body: HILApprove,
    db: AsyncSession = Depends(get_db),
    role: UserRole = Depends(get_current_user_role),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    finding_uuid = _parse_uuid(finding_id, "finding_id")
    finding = await _get_finding(db, finding_uuid)

    try:
        ctx = ExecutionContext(
            db=db,
            operation="hil.approve",
            resource_id=finding_uuid,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    cached = await ctx.begin()
    if cached is not None:
        return {**cached, "transaction_id": str(ctx.transaction_id), "idempotent_replay": True}

    checklist = body.checklist.model_dump()
    if not all(checklist.values()):
        raise HTTPException(422, "Checklist not fully satisfied")

    policy_result = await db.execute(
        select(ProgramScope).where(
            ProgramScope.program == finding.program,
            ProgramScope.is_deleted.is_(False),
        )
    )
    policy = policy_result.scalar_one_or_none()
    try:
        enforce_scope(finding, policy)
    except ScopeViolation as exc:
        raise HTTPException(403, f"Scope violation: {str(exc)}") from exc

    approved_at = datetime.now(timezone.utc)
    # Upsert with explicit duplicate handling to avoid double approvals.
    stmt = insert(HILApproval).values(
        finding_id=finding.id,
        approved_by=role.value,
        approved_at=approved_at,
        status=HILApprovalStatusEnum.APPROVED,
        checklist=checklist,
        notes=body.notes,
        is_deleted=False,
        deleted_at=None,
    )
    try:
        result = await db.execute(stmt)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Finding already approved") from None

    if result.rowcount == 0:
        # Insert ignored (should not happen without conflict clause); treat as duplicate.
        raise HTTPException(409, "Finding already approved")

    finding.status = FindingStatusEnum.HIL_APPROVED

    response = {
        "status": HILApprovalStatusEnum.APPROVED.value,
        "approved_at": approved_at.isoformat(),
    }
    ctx.complete(response)
    return {**response, "transaction_id": str(ctx.transaction_id)}


@router.post("/findings/{finding_id}/submit", dependencies=[Depends(RBAC(Permission.SUBMIT_FINDINGS))])
async def submit_finding(
    finding_id: str,
    body: SubmitBody,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    finding_uuid = _parse_uuid(finding_id, "finding_id")
    finding = await _get_finding(db, finding_uuid)

    try:
        ctx = ExecutionContext(
            db=db,
            operation="hil.submit",
            resource_id=finding_uuid,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    cached = await ctx.begin()
    if cached is not None:
        return {**cached, "transaction_id": str(ctx.transaction_id), "idempotent_replay": True}

    approval_result = await db.execute(
        select(HILApproval).where(
            HILApproval.finding_id == finding.id,
            HILApproval.is_deleted.is_(False),
        )
    )
    hil_approval = approval_result.scalar_one_or_none()
    if not hil_approval or hil_approval.status != HILApprovalStatusEnum.APPROVED:
        raise HTTPException(403, "HiL approval required before submission")

    evidence_result = await db.execute(
        select(Evidence).where(Evidence.finding_id == finding.id, Evidence.is_deleted.is_(False))
    )
    evidences = evidence_result.scalars().all()
    if not evidences:
        raise HTTPException(422, "Evidence bundle required")

    hashes = [evidence.sha256 for evidence in evidences]
    root_hash = merkle_root(hashes)

    try:
        report_hash = bytes.fromhex(body.report_content_hash_hex)
    except Exception as exc:
        raise HTTPException(422, "Invalid report_content_hash_hex") from exc

    report = Report(finding_id=finding.id, content_hash=report_hash, manifest_hash=root_hash)
    db.add(report)
    db.add(AuditMerkleRoot(run_id=finding.id, root_hash=root_hash))

    client = TheHiveClient()
    case_id = await asyncio.to_thread(
        client.ensure_case,
        title=finding.title,
        summary=finding.description,
    )

    finding.status = FindingStatusEnum.SUBMITTED
    response = {"status": FindingStatusEnum.SUBMITTED.value, "thehive_case_id": case_id}
    ctx.complete(response)
    return {**response, "transaction_id": str(ctx.transaction_id)}
