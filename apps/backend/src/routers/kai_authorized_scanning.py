"""
Kai Authorized Scanning Router
Ensures all vulnerability scanning is authorized, logged, and compliant
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Header, Request
from fastapi.responses import JSONResponse
import logging
from datetime import datetime, timedelta

from ..core.kai_security_guardrails import (
    get_guardrail_engine,
    AuthorizationCertificate,
    ScanAuthorization,
    ScanScope,
)
from ..schemas.common import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kai", tags=["Kai Authorized Scanning"])

# Get the guardrail engine
guardrails = get_guardrail_engine()


@router.get("/health", tags=["Health"])
async def kai_health():
    """Health check with security stats"""
    stats = guardrails.get_stats()
    return Response(
        success=True,
        data={
            "status": "healthy",
            "security_stats": stats,
        },
    )


# ============================================================================
# Authorization Management
# ============================================================================


@router.post("/authorize", response_model=Response)
async def register_authorization(
    authorization_type: str = Query(...),
    target: str = Query(...),
    authorized_by: str = Query(...),
    duration_days: int = Query(90),
    scope: Optional[str] = Query("single_domain"),
    methods: Optional[str] = Query("osint,vulnerability_scanning"),
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Register an authorization certificate for scanning

    Args:
        authorization_type: "bug_bounty_platform", "authorized_assessment", etc.
        target: Domain, IP range, or platform ID
        authorized_by: Name/email of who authorized this scan
        duration_days: How long this authorization is valid (default: 90)
        scope: "single_domain", "domain_wildcard", "ip_range", etc.
        methods: Comma-separated methods allowed (osint, vulnerability_scanning, web_testing, etc.)

    Example:
        POST /api/v1/kai/authorize
        ?authorization_type=bug_bounty_platform
        &target=example.com
        &authorized_by=admin@example.com
        &methods=osint,vulnerability_scanning
    """
    try:
        import uuid

        # Parse authorization type
        try:
            auth_type = ScanAuthorization(authorization_type.lower())
        except ValueError:
            return Response(
                success=False,
                data={
                    "error": f"Invalid authorization_type. Must be one of: {[e.value for e in ScanAuthorization]}"
                },
            )

        # Parse scope
        try:
            scan_scope = ScanScope(scope.lower())
        except ValueError:
            return Response(
                success=False,
                data={
                    "error": f"Invalid scope. Must be one of: {[e.value for e in ScanScope]}"
                },
            )

        # Parse methods
        allowed_methods = [m.strip() for m in methods.split(",") if m.strip()]

        # Create certificate
        cert = AuthorizationCertificate(
            certificate_id=str(uuid.uuid4()),
            authorization_type=auth_type,
            target=target,
            scope=scan_scope,
            authorized_by=authorized_by,
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=duration_days),
            allowed_methods=allowed_methods,
            metadata=metadata or {},
        )

        # Register with guardrails
        success = guardrails.register_authorization(cert)

        if not success:
            return Response(
                success=False,
                data={"error": "Failed to register authorization certificate"},
            )

        return Response(
            success=True,
            data={
                "certificate_id": cert.certificate_id,
                "authorization_type": cert.authorization_type.value,
                "target": cert.target,
                "expires_at": cert.expires_at.isoformat(),
                "allowed_methods": cert.allowed_methods,
                "message": f"✅ Authorization registered for {target}",
            },
        )

    except Exception as e:
        logger.error(f"Error registering authorization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/authorizations", response_model=Response)
async def list_authorizations():
    """List all active authorizations"""
    try:
        active_certs = [
            cert.to_dict()
            for cert in guardrails.authorized_certificates.values()
            if cert.is_valid()
        ]

        return Response(
            success=True,
            data={
                "authorizations": active_certs,
                "total": len(active_certs),
            },
        )

    except Exception as e:
        logger.error(f"Error listing authorizations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Authorized Scanning Operations
# ============================================================================


@router.post("/scan/osint", response_model=Response)
async def start_osint_scan(
    user_id: str = Query(...),
    target: str = Query(...),
    request: Request = None,
):
    """
    Start an authorized OSINT reconnaissance
    Requires valid authorization certificate
    """
    try:
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
            return Response(
                success=False,
                data={
                    "error": f"Scan not authorized: {reason}",
                    "status": "denied",
                    "audit_logged": True,
                },
                status_code=403,
            )

        # Log the operation
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

        logger.info(f"✅ OSINT scan authorized for {target} by {user_id}")

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
    user_id: str = Query(...),
    target: str = Query(...),
    scan_type: str = Query("comprehensive"),
    request: Request = None,
):
    """
    Start an authorized vulnerability scan
    Requires explicit authorization certificate
    """
    try:
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
            guardrails.log_scan_operation(
                user_id=user_id,
                certificate_id="unauthorized",
                target=target,
                scan_type="vulnerability_scan",
                scan_method="vulnerability_scanning",
                status="denied",
                error_message=reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return Response(
                success=False,
                data={
                    "error": f"Scan not authorized: {reason}",
                    "status": "denied",
                    "audit_logged": True,
                },
                status_code=403,
            )

        # Log the operation
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

        logger.info(
            f"✅ Vulnerability scan authorized for {target} by {user_id} (type: {scan_type})"
        )

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


# ============================================================================
# Audit and Compliance
# ============================================================================


@router.get("/audit-logs", response_model=Response)
async def get_audit_logs(
    user_id: Optional[str] = Query(None),
    days: int = Query(30),
):
    """
    Retrieve audit logs for compliance review
    Shows all scanning operations, authorizations, and denials
    """
    try:
        logs = guardrails.get_audit_logs(user_id=user_id, days=days)

        return Response(
            success=True,
            data={
                "logs": [log.to_dict() for log in logs],
                "total": len(logs),
                "period_days": days,
                "filtered_by_user": user_id,
            },
        )

    except Exception as e:
        logger.error(f"Error retrieving audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security-alerts", response_model=Response)
async def get_security_alerts():
    """
    Get security alerts for suspicious activities
    - Repeated authorization failures
    - Rapid-fire scanning attempts
    - Potential misuse patterns
    """
    try:
        suspicious_activities = guardrails.detect_suspicious_activity()

        return Response(
            success=True,
            data={
                "alerts": suspicious_activities,
                "alert_count": len(suspicious_activities),
                "severity_levels": {
                    "high": len([a for a in suspicious_activities if a.get("severity") == "high"]),
                    "medium": len([a for a in suspicious_activities if a.get("severity") == "medium"]),
                    "low": len([a for a in suspicious_activities if a.get("severity") == "low"]),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error getting security alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance-report", response_model=Response)
async def generate_compliance_report(
    days: int = Query(30),
):
    """
    Generate a compliance report for security audits
    """
    try:
        logs = guardrails.get_audit_logs(days=days)
        alerts = guardrails.detect_suspicious_activity()
        stats = guardrails.get_stats()

        # Calculate statistics
        total_scans = len(logs)
        completed_scans = len([log for log in logs if log.status == "completed"])
        failed_scans = len([log for log in logs if log.status == "failed"])
        denied_scans = len([log for log in logs if log.status == "denied"])

        return Response(
            success=True,
            data={
                "report_period_days": days,
                "generated_at": datetime.utcnow().isoformat(),
                "summary": {
                    "total_scans": total_scans,
                    "completed_scans": completed_scans,
                    "failed_scans": failed_scans,
                    "denied_scans": denied_scans,
                    "success_rate": (completed_scans / total_scans * 100) if total_scans > 0 else 0,
                },
                "security": {
                    "active_authorizations": stats["active_authorizations"],
                    "suspicious_activities_detected": len(alerts),
                    "blocked_operations": stats["blocked_operations"],
                },
                "alerts": alerts,
                "recommendations": [
                    "Review high-severity alerts",
                    "Ensure all scans have valid authorizations",
                    "Monitor for unauthorized access attempts",
                ],
            },
        )

    except Exception as e:
        logger.error(f"Error generating compliance report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Admin Operations
# ============================================================================


@router.post("/admin/revoke-authorization", response_model=Response)
async def revoke_authorization(
    certificate_id: str = Query(...),
    revoked_by: str = Query(...),
    reason: str = Query(...),
):
    """
    Revoke an authorization certificate
    Admin operation only - should be protected by authentication
    """
    try:
        if certificate_id not in guardrails.authorized_certificates:
            return Response(
                success=False,
                data={"error": f"Certificate not found: {certificate_id}"},
            )

        # Remove the certificate
        del guardrails.authorized_certificates[certificate_id]

        logger.warning(
            f"🚨 Authorization revoked: {certificate_id} by {revoked_by} - Reason: {reason}"
        )

        return Response(
            success=True,
            data={
                "certificate_id": certificate_id,
                "status": "revoked",
                "revoked_by": revoked_by,
                "reason": reason,
            },
        )

    except Exception as e:
        logger.error(f"Error revoking authorization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/security-stats", response_model=Response)
async def get_security_stats():
    """Get comprehensive security statistics"""
    try:
        stats = guardrails.get_stats()
        alerts = guardrails.detect_suspicious_activity()

        return Response(
            success=True,
            data={
                "stats": stats,
                "alerts": alerts,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error getting security stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
