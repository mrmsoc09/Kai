"""
Kai Authorized Scanning Router
Ensures all vulnerability scanning is authorized, logged, and compliant
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from datetime import datetime, timezone
import logging

from ..core.kai_security_guardrails import get_guardrail_engine, AuthorizationCertificate, ScanAuditLog
from ..core.auth import get_current_user, User, require_roles, ROLE_ADMIN, ROLE_ANALYST
from ..schemas.common import Response
from ..models.campaign import AuditEvent
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.hil_db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kai", tags=["security-guardrails"])
guardrails = get_guardrail_engine()

@router.post("/scan/osint", response_model=Response)
async def start_osint_scan(
    target: str = Query(...),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start an authorized OSINT reconnaissance
    Requires valid authorization certificate
    """
    try:
        user_id = current_user.id
        ip_address = request.client.host if request else None
        user_agent = request.headers.get("user-agent") if request else None

        # Check authorization
        authorized, reason, cert = guardrails.authorize_scan(
            user_id=user_id,
            target=target,
            scan_type="osint",
            scan_method="osint",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not authorized:
            # Direct DB write for denied operation
            db_event = AuditEvent(
                event_type="scan_denied",
                actor=user_id,
                message=f"OSINT scan denied for {target}: {reason}",
                event_payload_json={
                    "target": target,
                    "reason": reason,
                    "ip": ip_address,
                    "scan_type": "osint"
                }
            )
            db.add(db_event)
            await db.commit()
            
            return Response(
                success=False,
                data={
                    "error": f"Scan not authorized: {reason}",
                    "status": "denied",
                    "audit_logged": True,
                },
                status_code=403,
            )

        # Log the operation in GuardRailEngine
        log_id = guardrails.log_scan_operation(
            user_id=user_id,
            certificate_id=cert.certificate_id,
            target=target,
            scan_type="osint",
            scan_method="osint",
            status="started",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Direct DB write for started operation
        db_event = AuditEvent(
            event_type="scan_started",
            actor=user_id,
            message=f"OSINT scan started for {target}",
            event_payload_json={
                "scan_id": log_id,
                "target": target,
                "certificate_id": cert.certificate_id,
                "ip": ip_address,
                "scan_type": "osint",
                "scan_method": "osint",
                "status": "started"
            }
        )
        db.add(db_event)
        await db.commit()

        return Response(
            success=True,
            data={
                "scan_id": log_id,
                "target": target,
                "status": "started",
                "message": f"OSINT scan started on {target}",
                "certificate_id": cert.certificate_id,
            },
        )

    except Exception as e:
        logger.error(f"Error starting OSINT scan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan/vulnerability", response_model=Response)
async def start_vulnerability_scan(
    target: str = Query(...),
    scan_type: str = Query("comprehensive"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start an authorized vulnerability scan
    Requires explicit authorization certificate
    """
    try:
        user_id = current_user.id
        ip_address = request.client.host if request else None
        user_agent = request.headers.get("user-agent") if request else None

        # Check authorization
        authorized, reason, cert = guardrails.authorize_scan(
            user_id=user_id,
            target=target,
            scan_type="vulnerability_scan",
            scan_method="vulnerability_scanning",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not authorized:
            # Direct DB write for denied operation
            db_event = AuditEvent(
                event_type="scan_denied",
                actor=user_id,
                message=f"Vulnerability scan denied for {target}: {reason}",
                event_payload_json={
                    "target": target,
                    "reason": reason,
                    "ip": ip_address,
                    "scan_type": "vulnerability_scan"
                }
            )
            db.add(db_event)
            await db.commit()
            
            return Response(
                success=False,
                data={
                    "error": f"Scan not authorized: {reason}",
                    "status": "denied",
                    "audit_logged": True,
                },
                status_code=403,
            )

        # Log the operation in GuardRailEngine
        log_id = guardrails.log_scan_operation(
            user_id=user_id,
            certificate_id=cert.certificate_id,
            target=target,
            scan_type="vulnerability_scan",
            scan_method="vulnerability_scanning",
            status="started",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Direct DB write for started operation
        db_event = AuditEvent(
            event_type="scan_started",
            actor=user_id,
            message=f"Vulnerability scan started for {target}",
            event_payload_json={
                "scan_id": log_id,
                "target": target,
                "certificate_id": cert.certificate_id,
                "ip": ip_address,
                "scan_type": "vulnerability_scan",
                "scan_method": "vulnerability_scanning",
                "status": "started"
            }
        )
        db.add(db_event)
        await db.commit()

        return Response(
            success=True,
            data={
                "scan_id": log_id,
                "target": target,
                "scan_type": scan_type,
                "status": "started",
                "message": f"Vulnerability scan started on {target}",
                "certificate_id": cert.certificate_id,
                "authorization_details": {
                    "authorized_by": cert.authorized_by,
                    "expires_at": cert.expires_at.isoformat(),
                    "scope": cert.scope.value,
                },
            },
        )

    except Exception as e:
        logger.error(f"Error starting vulnerability scan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs", response_model=Response)
async def get_audit_logs(
    user_id: Optional[str] = Query(None),
    days: int = Query(30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve audit logs for compliance review
    Shows all scanning operations, authorizations, and denials
    """
    try:
        is_admin = ROLE_ADMIN in current_user.roles
        effective_user_id = user_id if is_admin else current_user.id
        
        # Query from database
        logs = await guardrails.get_audit_logs(db=db, user_id=effective_user_id, days=days)

        return Response(
            success=True,
            data={
                "logs": [log.to_dict() for log in logs],
                "total": len(logs),
                "period_days": days,
                "filtered_by_user": effective_user_id,
            },
        )

    except Exception as e:
        logger.error(f"Error retrieving audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security-stats", response_model=Response)
async def get_security_stats(
    current_user: User = Depends(require_roles(ROLE_ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Get security operations overview
    Restricted to ROLE_ADMIN
    """
    try:
        stats = await guardrails.get_stats(db=db)

        return Response(
            success=True,
            data={
                "stats": stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error getting security stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
