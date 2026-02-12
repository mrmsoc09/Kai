"""
Key Management API Router
Exposes key import, rotation, and verification endpoints
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio

router = APIRouter(prefix="/api/keys", tags=["key-management"])

# Module-level cache for systems
_key_management = None


def set_key_management(key_mgmt):
    """Set key management system reference from main.py"""
    global _key_management
    _key_management = key_mgmt


def get_key_management():
    """Get key management system with fallback import"""
    global _key_management

    if _key_management is None:
        try:
            from apps.backend.src.core.key_management import get_key_management_system
            _key_management = get_key_management_system()
        except:
            raise HTTPException(status_code=500, detail="Key management system not initialized")

    return _key_management


# ==================== Request/Response Models ====================

class AdminPGPKeyImportRequest(BaseModel):
    """Import admin PGP key"""
    admin_id: str
    pgp_key_content: str
    is_primary: bool = False
    description: Optional[str] = None


class AdminKeyRotationRequest(BaseModel):
    """Rotate admin PGP key"""
    current_key_id: str
    new_pgp_key_content: str
    reason: Optional[str] = None
    authorized_by: Optional[str] = None


class UserKeysImportRequest(BaseModel):
    """Import user keys"""
    user_id: str
    pgp_public_key: Optional[str] = None
    ssh_public_key: Optional[str] = None
    api_keys: Optional[Dict[str, str]] = None
    description: Optional[str] = None


class KeyRotationPlanRequest(BaseModel):
    """Plan a key rotation"""
    key_id: str
    new_key_content: str
    scheduled_for: Optional[str] = None
    reason: Optional[str] = None
    authorized_by: Optional[str] = None


class KeyRotationExecuteRequest(BaseModel):
    """Execute planned key rotation"""
    rotation_id: str
    new_key_content: str
    authorized_by: Optional[str] = None


class KeyRotationRollbackRequest(BaseModel):
    """Rollback key rotation"""
    rotation_id: str
    reason: Optional[str] = None


class PGPSignatureVerificationRequest(BaseModel):
    """Verify PGP signature"""
    signature: str
    message: str
    expected_key_id: Optional[str] = None


class KeyMetadataResponse(BaseModel):
    """Key metadata response"""
    key_id: str
    key_type: str
    owner_type: str
    owner_id: str
    status: str
    created_at: str
    expires_at: Optional[str]
    last_used_at: Optional[str]
    fingerprint: Optional[str]
    key_strength_bits: Optional[int]
    algorithm: str
    is_primary: bool
    tags: List[str]
    description: str


# ==================== Admin Key Management ====================

@router.post("/admin/import", response_model=Dict[str, Any])
async def import_admin_pgp_key(request: AdminPGPKeyImportRequest):
    """Import PGP key for admin HiL approval signing"""
    key_mgmt = get_key_management()

    try:
        success, message, metadata = await key_mgmt.import_admin_pgp_key(
            pgp_key_content=request.pgp_key_content,
            admin_id=request.admin_id,
            is_primary=request.is_primary,
            description=request.description or ""
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "key_id": metadata.key_id,
            "fingerprint": metadata.fingerprint,
            "created_at": metadata.created_at.isoformat(),
            "is_primary": metadata.is_primary
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/admin/rotate", response_model=Dict[str, Any])
async def rotate_admin_pgp_key(request: AdminKeyRotationRequest):
    """Rotate admin PGP key with rollback capability"""
    key_mgmt = get_key_management()

    try:
        success, message, rotation_plan = await key_mgmt.rotate_admin_pgp_key(
            current_key_id=request.current_key_id,
            new_pgp_key_content=request.new_pgp_key_content,
            reason=request.reason or "Scheduled rotation",
            authorized_by=request.authorized_by or ""
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "rotation_id": rotation_plan.rotation_id,
            "old_key_fingerprint": rotation_plan.old_key_metadata.fingerprint,
            "new_key_fingerprint": rotation_plan.new_key_metadata.fingerprint,
            "completed_at": rotation_plan.completed_at.isoformat() if rotation_plan.completed_at else None,
            "rollback_available": rotation_plan.rollback_available
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rotation failed: {str(e)}")


@router.get("/admin/{admin_id}/primary-key", response_model=Optional[Dict[str, Any]])
async def get_admin_primary_key(admin_id: str):
    """Get the primary admin PGP key (metadata only, not the key itself)"""
    key_mgmt = get_key_management()

    try:
        result = await key_mgmt.get_admin_primary_key(admin_id)

        if not result:
            raise HTTPException(status_code=404, detail="No primary key found for admin")

        metadata, _ = result

        return {
            "key_id": metadata.key_id,
            "fingerprint": metadata.fingerprint,
            "algorithm": metadata.algorithm,
            "created_at": metadata.created_at.isoformat(),
            "status": metadata.status,
            "is_primary": metadata.is_primary
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.get("/admin/{admin_id}/keys", response_model=List[Dict[str, Any]])
async def list_admin_keys(admin_id: str):
    """List all keys for an admin"""
    key_mgmt = get_key_management()

    try:
        keys = []
        for key_id, metadata in key_mgmt.keys_metadata.items():
            if metadata.owner_id == admin_id:
                keys.append({
                    "key_id": key_id,
                    "key_type": metadata.key_type.value,
                    "status": metadata.status.value,
                    "fingerprint": metadata.fingerprint,
                    "algorithm": metadata.algorithm,
                    "created_at": metadata.created_at.isoformat(),
                    "is_primary": metadata.is_primary
                })

        return keys

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")


# ==================== User Key Management ====================

@router.post("/users/import", response_model=Dict[str, Any])
async def import_user_keys(request: UserKeysImportRequest):
    """Import one or multiple keys for a user (PGP, SSH, API keys)"""
    key_mgmt = get_key_management()

    try:
        success, message, imported_keys = await key_mgmt.import_user_keys(
            user_id=request.user_id,
            pgp_public_key=request.pgp_public_key,
            ssh_public_key=request.ssh_public_key,
            api_keys=request.api_keys,
            description=request.description or ""
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "imported_keys": {
                key_type: {
                    "key_id": metadata.key_id,
                    "fingerprint": metadata.fingerprint,
                    "algorithm": metadata.algorithm,
                    "status": metadata.status.value
                }
                for key_type, metadata in imported_keys.items()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/users/{user_id}/keys", response_model=List[Dict[str, Any]])
async def list_user_keys(user_id: str):
    """List all keys for a user"""
    key_mgmt = get_key_management()

    try:
        user_keys = await key_mgmt.list_user_keys(user_id)

        return [
            {
                "key_id": key.key_id,
                "key_type": key.key_type.value,
                "status": key.status.value,
                "fingerprint": key.fingerprint,
                "algorithm": key.algorithm,
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                "tags": key.tags,
                "description": key.description
            }
            for key in user_keys
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")


@router.post("/users/{user_id}/keys/{key_id}/revoke", response_model=Dict[str, Any])
async def revoke_user_key(user_id: str, key_id: str, reason: Optional[str] = None):
    """Revoke a user key"""
    key_mgmt = get_key_management()

    try:
        success, message = await key_mgmt.revoke_user_key(key_id, reason or "User revocation")

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "key_id": key_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revocation failed: {str(e)}")


# ==================== Key Rotation ====================

@router.post("/rotation/plan", response_model=Dict[str, Any])
async def plan_key_rotation(request: KeyRotationPlanRequest):
    """Plan a key rotation with approval workflow"""
    key_mgmt = get_key_management()

    try:
        scheduled_for = None
        if request.scheduled_for:
            scheduled_for = datetime.fromisoformat(request.scheduled_for)

        success, message, rotation_plan = await key_mgmt.plan_key_rotation(
            key_id=request.key_id,
            new_key_content=request.new_key_content,
            scheduled_for=scheduled_for,
            reason=request.reason or "Scheduled rotation",
            authorized_by=request.authorized_by or ""
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "rotation_id": rotation_plan.rotation_id,
            "key_id": rotation_plan.key_id,
            "status": rotation_plan.status.value,
            "scheduled_for": rotation_plan.scheduled_for.isoformat(),
            "reason": rotation_plan.reason,
            "rollback_available": rotation_plan.rollback_available
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")


@router.post("/rotation/{rotation_id}/execute", response_model=Dict[str, Any])
async def execute_key_rotation(rotation_id: str, request: KeyRotationExecuteRequest):
    """Execute a planned key rotation"""
    key_mgmt = get_key_management()

    try:
        success, message = await key_mgmt.execute_key_rotation(
            rotation_id=rotation_id,
            new_key_content=request.new_key_content,
            authorized_by=request.authorized_by or ""
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "rotation_id": rotation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.post("/rotation/{rotation_id}/rollback", response_model=Dict[str, Any])
async def rollback_key_rotation(rotation_id: str, request: KeyRotationRollbackRequest):
    """Rollback a completed key rotation"""
    key_mgmt = get_key_management()

    try:
        success, message = await key_mgmt.rollback_key_rotation(
            rotation_id=rotation_id,
            reason=request.reason or ""
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "rotation_id": rotation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


@router.get("/rotation/{key_id}/history", response_model=List[Dict[str, Any]])
async def get_key_rotation_history(key_id: str):
    """Get rotation history for a key"""
    key_mgmt = get_key_management()

    try:
        history = key_mgmt.get_rotation_history(key_id)

        return [
            {
                "rotation_id": plan.rotation_id,
                "initiated_at": plan.initiated_at.isoformat(),
                "scheduled_for": plan.scheduled_for.isoformat(),
                "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
                "status": plan.status.value,
                "reason": plan.reason,
                "authorized_by": plan.authorized_by
            }
            for plan in history
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History retrieval failed: {str(e)}")


@router.get("/expiring", response_model=List[Dict[str, Any]])
async def get_expiring_keys(days: int = 30):
    """Get keys expiring within specified days"""
    key_mgmt = get_key_management()

    try:
        expiring = key_mgmt.get_expiring_keys(days_until=days)

        return [
            {
                "key_id": key.key_id,
                "owner_id": key.owner_id,
                "owner_type": key.owner_type.value,
                "fingerprint": key.fingerprint,
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "days_until_expiry": (key.expires_at - datetime.utcnow()).days if key.expires_at else None
            }
            for key in expiring
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ==================== Key Verification ====================

@router.post("/verify/pgp-signature", response_model=Dict[str, Any])
async def verify_pgp_signature(request: PGPSignatureVerificationRequest):
    """Verify a PGP signature"""
    key_mgmt = get_key_management()

    try:
        valid, message, signer_key_id = await key_mgmt.verify_pgp_signature(
            signature=request.signature,
            message=request.message,
            expected_key_id=request.expected_key_id
        )

        if not valid:
            raise HTTPException(status_code=400, detail=message)

        return {
            "valid": True,
            "message": message,
            "signer_key_id": signer_key_id,
            "verified_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


# ==================== Audit & Monitoring ====================

@router.get("/keys/{key_id}/audit-trail", response_model=List[Dict[str, Any]])
async def get_key_audit_trail(key_id: str):
    """Get complete audit trail for a key"""
    key_mgmt = get_key_management()

    try:
        audit = key_mgmt.get_key_audit_trail(key_id)

        if not audit:
            raise HTTPException(status_code=404, detail="Key not found or no audit trail")

        return audit

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit retrieval failed: {str(e)}")


@router.get("/usage-logs", response_model=List[Dict[str, Any]])
async def get_key_usage_logs(
    key_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    limit: int = 100
):
    """Get key usage logs with optional filtering"""
    key_mgmt = get_key_management()

    try:
        logs = key_mgmt.get_usage_logs(key_id=key_id, owner_id=owner_id, limit=limit)

        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "key_id": log.key_id,
                "operation": log.operation,
                "success": log.success,
                "user_id": log.user_id,
                "error_message": log.error_message,
                "details": log.details
            }
            for log in logs
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log retrieval failed: {str(e)}")


# ==================== Dashboard ====================

@router.get("/dashboard/summary", response_model=Dict[str, Any])
async def get_key_management_summary():
    """Get summary of key management status"""
    key_mgmt = get_key_management()

    try:
        total_keys = len(key_mgmt.keys_metadata)
        active_keys = len([k for k in key_mgmt.keys_metadata.values() if k.status.value == "active"])
        expiring_soon = key_mgmt.get_expiring_keys(days_until=30)
        pending_rotations = len([
            p for p in key_mgmt.rotation_plans.values()
            if p.status.value == "initiated"
        ])

        # Group by owner type
        by_owner = {}
        for metadata in key_mgmt.keys_metadata.values():
            owner_type = metadata.owner_type.value
            by_owner[owner_type] = by_owner.get(owner_type, 0) + 1

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "by_owner_type": by_owner,
            "keys_expiring_in_30_days": len(expiring_soon),
            "pending_rotations": pending_rotations,
            "recent_usage_count": len(key_mgmt.usage_logs[-100:]),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary failed: {str(e)}")
