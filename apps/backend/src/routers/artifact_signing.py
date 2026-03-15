"""
Artifact Signing & Chain of Custody API Router
Exposes endpoints for signing vulnerability reports and verifying signatures
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import asyncio

router = APIRouter(prefix="/api/artifacts", tags=["artifact-signing"])

# Module-level cache for systems
_kai_crypto = None


def set_kai_crypto(crypto_system):
    """Set crypto system reference from main.py"""
    global _kai_crypto
    _kai_crypto = crypto_system


def get_kai_crypto():
    """Get crypto system with fallback import"""
    global _kai_crypto

    if _kai_crypto is None:
        try:
            from apps.backend.src.core.crypto_artifact_signing import get_kai_crypto as get_crypto
            _kai_crypto = get_crypto()
        except Exception:
            raise HTTPException(status_code=500, detail="Crypto system not initialized")

    return _kai_crypto


# ==================== Request/Response Models ====================

class SignArtifactRequest(BaseModel):
    """Request to sign an artifact"""
    artifact_path: str
    output_path: Optional[str] = None
    passphrase: str = ""


class VerifyArtifactRequest(BaseModel):
    """Request to verify an artifact signature"""
    artifact_path: str
    signature_path: str


class SignatureRecordResponse(BaseModel):
    """Response containing signature record"""
    artifact_path: str
    signature_path: str
    signer_identity: str
    signer_fingerprint: str
    signed_at: str
    artifact_hash: str
    algorithm: str


class VerificationRecordResponse(BaseModel):
    """Response containing verification record"""
    artifact_path: str
    signature_path: str
    verified_at: str
    status: str
    signer_identity: str
    signer_fingerprint: str
    tamper_detected: bool


# ==================== Initialization ====================

@router.post("/init", response_model=Dict[str, Any])
async def initialize_crypto_system(
    gpg_home: Optional[str] = None,
    key_source_dir: Optional[str] = None
):
    """Initialize the crypto system and import all Kaisonai keys"""
    try:
        from apps.backend.src.core.crypto_artifact_signing import initialize_kai_crypto

        crypto = initialize_kai_crypto(
            gpg_home=gpg_home,
            key_source_dir=key_source_dir
        )

        # Set in router
        set_kai_crypto(crypto)

        # Initialize keys
        success, message, import_results = await crypto.initialize_keys()

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "import_results": import_results,
            "system_status": crypto.get_system_status()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


# ==================== Artifact Signing ====================

@router.post("/sign", response_model=Dict[str, Any])
async def sign_artifact(request: SignArtifactRequest):
    """Sign a vulnerability report or scan log with machine identity"""
    crypto = get_kai_crypto()

    try:
        success, message, record = await crypto.sign_artifact(
            artifact_path=request.artifact_path,
            passphrase=request.passphrase,
            output_path=request.output_path
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "signature": {
                "artifact_path": record.artifact_path,
                "signature_path": record.signature_path,
                "signer_identity": record.signer_identity,
                "signer_fingerprint": record.signer_fingerprint,
                "signed_at": record.signed_at.isoformat(),
                "artifact_hash": record.artifact_hash,
                "algorithm": record.algorithm
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signing failed: {str(e)}")


# ==================== Artifact Verification ====================

@router.post("/verify", response_model=Dict[str, Any])
async def verify_artifact(request: VerifyArtifactRequest):
    """Verify a signed artifact - detects tampering"""
    crypto = get_kai_crypto()

    try:
        success, message, record = await crypto.verify_artifact(
            artifact_path=request.artifact_path,
            signature_path=request.signature_path
        )

        response = {
            "message": message,
            "artifact_path": record.artifact_path,
            "signature_path": record.signature_path,
            "status": record.status.value,
            "signer_identity": record.signer_identity,
            "signer_fingerprint": record.signer_fingerprint,
            "tamper_detected": record.tamper_detected,
            "verified_at": record.verified_at.isoformat()
        }

        if record.tamper_detected:
            # TAMPER ALERT - escalate
            response["alert"] = "TAMPER DETECTION: Artifact signature verification failed"
            response["action"] = "EXECUTION HALTED"
            return {
                "success": False,
                **response
            }
        elif success:
            return {
                "success": True,
                **response
            }
        else:
            return {
                "success": False,
                **response
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


# ==================== Chain of Custody ====================

@router.get("/chain-of-custody/{artifact_path}", response_model=Dict[str, Any])
async def get_chain_of_custody(artifact_path: str):
    """Get complete chain of custody for an artifact"""
    crypto = get_kai_crypto()

    try:
        chain = crypto.get_chain_of_custody(artifact_path)
        return {
            "success": True,
            "artifact": artifact_path,
            "chain": chain,
            "chain_intact": chain.get("chain_intact", False)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chain retrieval failed: {str(e)}")


# ==================== Key Management ====================

@router.get("/keys", response_model=Dict[str, Any])
async def list_available_keys():
    """List all available PGP keys in the crypto system"""
    crypto = get_kai_crypto()

    try:
        keys = crypto.list_available_keys()
        return {
            "success": True,
            "total_keys": len(keys),
            "keys": keys
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Key listing failed: {str(e)}")


# ==================== Audit & Diagnostics ====================

@router.get("/status", response_model=Dict[str, Any])
async def get_crypto_system_status():
    """Get crypto system status and diagnostics"""
    crypto = get_kai_crypto()

    try:
        status = crypto.get_system_status()
        return {
            "success": True,
            "status": status
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


@router.get("/audit-trail", response_model=Dict[str, Any])
async def get_audit_trail(limit: int = 100):
    """Get complete audit trail of crypto operations"""
    crypto = get_kai_crypto()

    try:
        audit = crypto.get_audit_trail()
        return {
            "success": True,
            "total_operations": len(audit),
            "recent_operations": audit[-limit:],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit retrieval failed: {str(e)}")


@router.get("/signatures", response_model=Dict[str, Any])
async def get_signature_log(limit: int = 100):
    """Get recent signing operations"""
    crypto = get_kai_crypto()

    try:
        sigs = [
            {
                "artifact": s.artifact_path,
                "signed_at": s.signed_at.isoformat(),
                "signer": s.signer_identity,
                "hash": s.artifact_hash
            }
            for s in crypto.signature_log[-limit:]
        ]
        return {
            "success": True,
            "total_signatures": len(crypto.signature_log),
            "recent_signatures": sigs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log retrieval failed: {str(e)}")


@router.get("/verifications", response_model=Dict[str, Any])
async def get_verification_log(limit: int = 100):
    """Get recent verification operations"""
    crypto = get_kai_crypto()

    try:
        verifs = [
            {
                "artifact": v.artifact_path,
                "verified_at": v.verified_at.isoformat(),
                "status": v.status.value,
                "tamper_detected": v.tamper_detected,
                "signer": v.signer_identity
            }
            for v in crypto.verification_log[-limit:]
        ]
        return {
            "success": True,
            "total_verifications": len(crypto.verification_log),
            "recent_verifications": verifs,
            "tamper_alerts": sum(1 for v in crypto.verification_log if v.tamper_detected)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log retrieval failed: {str(e)}")


# ==================== Dashboard ====================

@router.get("/dashboard/summary", response_model=Dict[str, Any])
async def get_crypto_dashboard():
    """Get crypto system dashboard summary"""
    crypto = get_kai_crypto()

    try:
        total_sigs = len(crypto.signature_log)
        total_verifs = len(crypto.verification_log)
        tamper_alerts = sum(1 for v in crypto.verification_log if v.tamper_detected)

        # Calculate verification success rate
        if total_verifs > 0:
            successful_verifs = sum(
                1 for v in crypto.verification_log
                if v.status.value == "valid" and not v.tamper_detected
            )
            success_rate = (successful_verifs / total_verifs) * 100
        else:
            success_rate = 0

        return {
            "success": True,
            "summary": {
                "total_signatures": total_sigs,
                "total_verifications": total_verifs,
                "verification_success_rate": success_rate,
                "tamper_alerts": tamper_alerts,
                "alert_status": "NORMAL" if tamper_alerts == 0 else "WARNING"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard failed: {str(e)}")
