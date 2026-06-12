"""API router for credential management endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import User, get_current_user
from ..core.credentials_manager import CredentialsManager
from ..core.hunter_account_inventory import load_hunter_account_index
from ..core.hil_db import get_db
from ..core.opportunity_catalog import list_filtered
from ..core.vault_client import SecretNotFoundError, VaultConnectionError
from ..models.campaign import Program
from ..models.credential_schemas import (
    AccessMetadataRequest,
    AccessMetadataResponse,
    CredentialResponse,
    ListCredentialsResponse,
    ScanningModesResponse,
    StoreCredentialRequest,
    ValidateCredentialRequest,
    ValidateCredentialResponse,
)
from ..models.opportunity_credentials import (
    OpportunityAccessMetadata,
    OpportunityCredential,
)


# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter(
    prefix="/api/v1/credentials",
    tags=["credentials"],
    dependencies=[Depends(get_current_user)],
)


class HunterAccountInventoryResponse(BaseModel):
    source_path: str
    record_count: int
    counts: dict[str, int]
    records: list[dict]


class ScanSuggestionResponse(BaseModel):
    opportunity_id: str
    name: str
    organization: str
    platform: str
    score: int
    reasons: list[str]
    matching_accounts: list[str]
    account_ready: bool = True


class ScanSuggestionListResponse(BaseModel):
    items: list[ScanSuggestionResponse]


# ============================================================================
# Helper Functions
# ============================================================================


def _credential_to_response(cred: OpportunityCredential) -> CredentialResponse:
    """Convert ORM model to response schema."""
    return CredentialResponse(
        id=str(cred.id),
        program_id=str(cred.program_id),
        access_type=cred.access_type,
        status=cred.status,
        credential_username=cred.credential_username,
        last_validated=cred.last_validated.isoformat() if cred.last_validated else None,
        validation_method=cred.validation_method,
        created_at=cred.created_at.isoformat(),
        updated_at=cred.updated_at.isoformat(),
        notes=cred.notes,
        access_count=cred.access_count,
        last_accessed_at=cred.last_accessed_at.isoformat() if cred.last_accessed_at else None,
        last_accessed_by=cred.last_accessed_by,
    )


def _metadata_to_response(meta: OpportunityAccessMetadata) -> AccessMetadataResponse:
    """Convert ORM model to response schema."""
    return AccessMetadataResponse(
        id=str(meta.id),
        program_id=str(meta.program_id),
        access_type=meta.access_type,
        enabled=meta.enabled,
        signup_url=meta.signup_url,
        signup_instructions=meta.signup_instructions,
        requires_email=meta.requires_email,
        requires_payment=meta.requires_payment,
        rate_limits=meta.rate_limits,
        available_endpoints=meta.available_endpoints,
        testing_account_available=meta.testing_account_available,
        testing_account_url=meta.testing_account_url,
        testing_instructions=meta.testing_instructions,
        created_at=meta.created_at.isoformat(),
        updated_at=meta.updated_at.isoformat(),
    )


# ============================================================================
# Endpoints: Credentials CRUD
# ============================================================================


@router.post("/{program_id}/{access_type}")
async def store_credential(
    program_id: UUID,
    access_type: str,
    body: StoreCredentialRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CredentialResponse:
    """Store a credential for a program."""
    # Verify program exists
    stmt = select(Program).where(Program.id == program_id)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_id} not found",
        )

    mgr = CredentialsManager(db)
    try:
        cred = await mgr.store_credential(
            program_id,
            access_type,
            body.credentials,
            username=body.username,
            notes=body.notes,
            user_id=user.user_id,
        )
        return _credential_to_response(cred)
    except VaultConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vault unavailable: {str(e)}",
        )


@router.get("/{program_id}")
async def list_credentials(
    program_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ListCredentialsResponse:
    """List all stored credentials for a program."""
    # Verify program exists
    stmt = select(Program).where(Program.id == program_id)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_id} not found",
        )

    mgr = CredentialsManager(db)
    credentials = await mgr.list_credentials_for_program(program_id)
    return ListCredentialsResponse(
        program_id=str(program_id),
        credentials=[_credential_to_response(c) for c in credentials],
    )


@router.put("/{program_id}/{access_type}")
async def update_credential(
    program_id: UUID,
    access_type: str,
    body: StoreCredentialRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CredentialResponse:
    """Update an existing credential."""
    # Verify program exists
    stmt = select(Program).where(Program.id == program_id)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_id} not found",
        )

    mgr = CredentialsManager(db)
    try:
        cred = await mgr.store_credential(
            program_id,
            access_type,
            body.credentials,
            username=body.username,
            notes=body.notes,
            user_id=user.user_id,
        )
        return _credential_to_response(cred)
    except VaultConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vault unavailable: {str(e)}",
        )


@router.delete("/{program_id}/{access_type}")
async def delete_credential(
    program_id: UUID,
    access_type: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Delete a credential."""
    mgr = CredentialsManager(db)
    try:
        await mgr.delete_credential(program_id, access_type, user_id=user.user_id)
        return {"ok": True, "message": f"Deleted {access_type} credential"}
    except SecretNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )
    except VaultConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vault unavailable: {str(e)}",
        )


# ============================================================================
# Endpoints: Credential Validation
# ============================================================================


@router.post("/{program_id}/{access_type}/validate")
async def validate_credential(
    program_id: UUID,
    access_type: str,
    body: ValidateCredentialRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidateCredentialResponse:
    """Validate a stored credential by testing it against the live service."""
    mgr = CredentialsManager(db)
    result = await mgr.validate_credential(program_id, access_type)
    return ValidateCredentialResponse(
        valid=result["valid"],
        reason=result["reason"],
        tested_at=result.get("tested_at"),
    )


# ============================================================================
# Endpoints: Scanning Modes
# ============================================================================


@router.get("/{program_id}/scanning-modes")
async def get_scanning_modes(
    program_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanningModesResponse:
    """Get available scanning modes for a program based on stored credentials."""
    # Verify program exists
    stmt = select(Program).where(Program.id == program_id)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_id} not found",
        )

    mgr = CredentialsManager(db)
    modes = await mgr.get_scanning_modes(program_id)
    return ScanningModesResponse(**modes)


# ============================================================================
# Endpoints: Access Metadata
# ============================================================================


@router.get("/access-metadata/{program_id}")
async def list_access_metadata(
    program_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """List all access metadata for a program."""
    # Verify program exists
    stmt = select(Program).where(Program.id == program_id)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_id} not found",
        )

    stmt = select(OpportunityAccessMetadata).where(
        OpportunityAccessMetadata.program_id == program_id
    )
    result = await db.execute(stmt)
    metadata = result.scalars().all()
    return {
        "program_id": str(program_id),
        "metadata": [_metadata_to_response(m) for m in metadata],
    }


@router.put("/access-metadata/{program_id}/{access_type}")
async def upsert_access_metadata(
    program_id: UUID,
    access_type: str,
    body: AccessMetadataRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AccessMetadataResponse:
    """Create or update access metadata for a program."""
    # Verify program exists
    stmt = select(Program).where(Program.id == program_id)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_id} not found",
        )

    mgr = CredentialsManager(db)
    meta = await mgr.upsert_access_metadata(
        program_id,
        access_type,
        enabled=body.enabled,
        signup_url=body.signup_url,
        signup_instructions=body.signup_instructions,
        requires_email=body.requires_email,
        requires_payment=body.requires_payment,
        rate_limits=body.rate_limits,
        available_endpoints=body.available_endpoints,
        testing_account_available=body.testing_account_available,
        testing_account_url=body.testing_account_url,
        testing_instructions=body.testing_instructions,
    )
    return _metadata_to_response(meta)


def _build_scan_suggestions(limit: int = 10) -> list[dict]:
    inventory = load_hunter_account_index()
    records = inventory.get("records", [])
    opportunities = list_filtered(limit=500)
    suggestions: list[dict] = []

    for opportunity in opportunities:
        reasons: list[str] = []
        matching_accounts: list[str] = []
        score = 0
        platform = str(opportunity.platform or "").strip().lower()
        required_types = {
            str(req.kind or "").strip().lower()
            for req in getattr(opportunity, "credential_requirements", [])
            if getattr(req, "kind", None)
        }

        for record in records:
            display_name = str(record.get("display_name") or record.get("slug") or "").strip()
            if not display_name:
                continue

            record_platform = str(record.get("platform_hint") or "").strip().lower()
            record_kind = str(record.get("credential_kind") or "").strip().lower()
            source_url = str(record.get("source_url") or "").strip().lower()

            if record_platform and platform and record_platform == platform:
                score += 40
                reasons.append(f"platform match via {display_name}")
                matching_accounts.append(display_name)
                continue

            if record_kind in required_types:
                score += 20
                reasons.append(f"required credential type covered by {display_name}")
                matching_accounts.append(display_name)
                continue

            if source_url and any(domain and domain.lower() in source_url for domain in opportunity.scope_domains):
                score += 15
                reasons.append(f"scope host aligns with {display_name}")
                matching_accounts.append(display_name)

        if score <= 0 or not matching_accounts:
            continue

        suggestions.append(
            {
                "opportunity_id": opportunity.id,
                "name": opportunity.name,
                "organization": opportunity.organization,
                "platform": opportunity.platform,
                "score": score,
                "reasons": reasons[:4],
                "matching_accounts": sorted(set(matching_accounts))[:5],
                "account_ready": True,
            }
        )

    suggestions.sort(
        key=lambda item: (len(item["matching_accounts"]), item["score"]),
        reverse=True,
    )
    return suggestions[:limit]


@router.get("/hunter-accounts", response_model=HunterAccountInventoryResponse)
async def list_hunter_accounts() -> HunterAccountInventoryResponse:
    return HunterAccountInventoryResponse(**load_hunter_account_index())


@router.get("/scan-suggestions", response_model=ScanSuggestionListResponse)
async def list_scan_suggestions(
    limit: int = Query(default=50, ge=1, le=50),
) -> ScanSuggestionListResponse:
    return ScanSuggestionListResponse(
        items=[ScanSuggestionResponse(**item) for item in _build_scan_suggestions(limit)]
    )
