from __future__ import annotations

import binascii
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.execution_context import ExecutionContext
from ..core.reproducibility_scorer import calculate_reproducibility, generate_feedback
from ..core.hil_db import get_db
from ..core.hil_security import Permission, RBAC
from ..models.enums import SeverityEnum
from ..models.hil import Evidence, Finding
from ..schemas.hil import EvidenceCreate, FindingCreate


router = APIRouter(prefix="/findings", tags=["hil-findings"])


def _parse_uuid(raw: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(422, f"{field_name} must be a UUID") from exc


@router.post("/", dependencies=[Depends(RBAC(Permission.INITIATE_SCAN))])
async def create_finding(
    body: FindingCreate,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    try:
        ctx = ExecutionContext(
            db=db,
            operation="hil.finding.create",
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    cached = await ctx.begin()
    if cached is not None:
        return {**cached, "transaction_id": str(ctx.transaction_id), "idempotent_replay": True}

    finding = Finding(
        program=body.program.strip(),
        asset=body.asset.strip(),
        title=body.title.strip(),
        description=body.description.strip(),
        severity=SeverityEnum(body.severity),
    )
    db.add(finding)
    await db.flush()

    response = {"id": str(finding.id)}
    ctx.complete(response)
    return {**response, "transaction_id": str(ctx.transaction_id)}


@router.post("/{finding_id}/evidence", dependencies=[Depends(RBAC(Permission.SUBMIT_FINDINGS))])
async def add_evidence(
    finding_id: str,
    body: EvidenceCreate,
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
):
    finding_uuid = _parse_uuid(finding_id, "finding_id")
    finding_result = await db.execute(
        select(Finding).where(Finding.id == finding_uuid, Finding.is_deleted.is_(False))
    )
    finding = finding_result.scalar_one_or_none()
    if not finding:
        raise HTTPException(404, "Finding not found")

    try:
        ctx = ExecutionContext(
            db=db,
            operation="hil.finding.add_evidence",
            resource_id=finding_uuid,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    cached = await ctx.begin()
    if cached is not None:
        return {**cached, "transaction_id": str(ctx.transaction_id), "idempotent_replay": True}

    try:
        digest = binascii.unhexlify(body.sha256_hex)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "Invalid sha256 hex") from exc

    evidence = Evidence(
        finding_id=finding.id,
        kind=body.kind.strip(),
        uri=body.uri.strip(),
        sha256=digest,
        meta=body.meta,
    )
    db.add(evidence)
    await db.flush()

    # Auto-update reproducibility score after new evidence.
    all_evidence = await db.execute(
        select(Evidence).where(Evidence.finding_id == finding.id, Evidence.is_deleted.is_(False))
    )
    evidence_rows = all_evidence.scalars().all()
    score = calculate_reproducibility(
        [
            {"kind": ev.kind, "uri": ev.uri, "created_at": ev.created_at}
            for ev in evidence_rows
        ]
    )
    finding.reproducibility_score = score

    response = {"evidence_id": str(evidence.id), "reproducibility_score": score}
    ctx.complete(response)
    return {**response, "transaction_id": str(ctx.transaction_id)}


@router.get("/{finding_id}/evidence", dependencies=[Depends(RBAC(Permission.VIEW_FINDINGS))])
async def list_evidence(finding_id: str, db: AsyncSession = Depends(get_db)):
    finding_uuid = _parse_uuid(finding_id, "finding_id")
    finding_result = await db.execute(
        select(Finding).where(Finding.id == finding_uuid, Finding.is_deleted.is_(False))
    )
    finding = finding_result.scalar_one_or_none()
    if not finding:
        raise HTTPException(404, "Finding not found")

    evidence_result = await db.execute(
        select(Evidence).where(Evidence.finding_id == finding_uuid, Evidence.is_deleted.is_(False))
    )
    evidences = evidence_result.scalars().all()

    return [
        {
            "id": str(evidence.id),
            "kind": evidence.kind,
            "uri": evidence.uri,
            "sha256": evidence.sha256.hex(),
            "meta": evidence.meta,
            "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
        }
        for evidence in evidences
    ]


@router.post("/{finding_id}/reproducibility-score", dependencies=[Depends(RBAC(Permission.VIEW_FINDINGS))])
async def compute_reproducibility_score(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
):
    finding_uuid = _parse_uuid(finding_id, "finding_id")
    finding_result = await db.execute(
        select(Finding).where(Finding.id == finding_uuid, Finding.is_deleted.is_(False))
    )
    finding = finding_result.scalar_one_or_none()
    if not finding:
        raise HTTPException(404, "Finding not found")

    evidence_result = await db.execute(
        select(Evidence).where(Evidence.finding_id == finding.id, Evidence.is_deleted.is_(False))
    )
    evidences = evidence_result.scalars().all()
    score = calculate_reproducibility(
        [
            {
                "kind": ev.kind,
                "uri": ev.uri,
                "created_at": ev.created_at,
            }
            for ev in evidences
        ]
    )
    finding.reproducibility_score = score
    feedback = generate_feedback(score)
    return {"score": score, "feedback": feedback}
