"""
Log Watchdog API Router
Provides endpoints for monitoring hunting logs and validating PGP signatures
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any, List
import asyncio
from pathlib import Path

from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.log_watchdog import (
    LogWatchdog,
    initialize_log_watchdog,
    get_log_watchdog,
    AlertSeverity
)
from ..schemas.watchdog import (
    ScanResponse,
    ReportResponse,
    RemediationResponse,
    AlertList,
    StatusResponse,
    ClearAlertResponse,
    InitResponse,
    CryptoSystemResponse
)

router = APIRouter(
    prefix='/logs/watchdog',
    tags=['watchdog'],
    dependencies=[Depends(require_roles(ROLE_OPERATOR))]
)

# Global watchdog instance
_watchdog_instance: Optional[LogWatchdog] = None
_crypto_system = None


async def get_watchdog(
    log_directory: str = Query(default="/var/lib/kai/logs", description="Directory to monitor"),
    force_reinit: bool = Query(default=False, description="Force reinitialization")
) -> LogWatchdog:
    """Get or initialize the log watchdog"""
    global _watchdog_instance

    if force_reinit or _watchdog_instance is None:
        _watchdog_instance = initialize_log_watchdog(
            log_directory=log_directory,
            crypto_system=_crypto_system
        )

    return _watchdog_instance


@router.post('/init', summary="Initialize Log Watchdog", response_model=InitResponse)
async def init_watchdog(
    log_directory: str = Query(default="/var/lib/kai/logs"),
    crypto_system_available: bool = Query(default=True)
) -> InitResponse:
    """
    Initialize the log watchdog system

    This must be called before scanning logs. It sets up the monitoring
    system and configures which operations are considered critical.
    """
    global _watchdog_instance, _crypto_system

    try:
        _watchdog_instance = initialize_log_watchdog(
            log_directory=log_directory,
            crypto_system=_crypto_system if crypto_system_available else None
        )

        return {
            "success": True,
            "message": "Log watchdog initialized",
            "config": {
                "log_directory": str(_watchdog_instance.log_dir),
                "critical_operations": _watchdog_instance.critical_operations,
                "crypto_system_available": crypto_system_available,
                "timestamp": _watchdog_instance.last_scan.isoformat() if _watchdog_instance.last_scan else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Watchdog initialization failed: {str(e)}")


@router.post('/scan', summary="Scan Logs for Unsigned Entries", response_model=ScanResponse)
async def scan_logs(
    watchdog: LogWatchdog = Depends(get_watchdog)
) -> ScanResponse:
    """
    Scan the log directory for unsigned or invalid signature entries

    Returns:
    - total_logs: Total number of log files found
    - signed_logs: Number of logs with valid signatures
    - unsigned_count: Number of unsigned logs
    - alerts: List of new alerts generated
    """
    try:
        total_logs, signed_logs, new_alerts = await watchdog.scan_logs()

        unsigned_count = total_logs - signed_logs

        return {
            "success": True,
            "scan_results": {
                "total_logs": total_logs,
                "signed_logs": signed_logs,
                "unsigned_logs": unsigned_count,
                "signature_coverage": (signed_logs / total_logs * 100) if total_logs > 0 else 0
            },
            "alerts": [
                {
                    "alert_id": alert.alert_id,
                    "log_id": alert.log_id,
                    "operation": alert.operation,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "detected_at": alert.detected_at,
                    "action_required": alert.action_required
                }
                for alert in new_alerts
            ],
            "new_alerts_count": len(new_alerts),
            "timestamp": watchdog.last_scan.isoformat() if watchdog.last_scan else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get('/report', summary="Get Comprehensive Watchdog Report", response_model=ReportResponse)
async def get_report(
    watchdog: LogWatchdog = Depends(get_watchdog)
) -> ReportResponse:
    """
    Get a comprehensive report of all monitored logs and alerts

    Includes:
    - Coverage statistics
    - Alert breakdown by severity
    - Detailed alert list
    - System status
    """
    try:
        report = await watchdog.generate_report()

        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.post('/remediate', summary="Attempt to Sign Unsigned Logs", response_model=RemediationResponse)
async def remediate_unsigned(
    watchdog: LogWatchdog = Depends(get_watchdog)
) -> RemediationResponse:
    """
    Attempt to automatically sign all unsigned critical and high-severity logs

    Returns remediation results:
    - unsigned: Number of unsigned logs found
    - signed: Number of logs successfully signed
    - failed: Number of signing attempts that failed
    """
    try:
        if not watchdog.crypto_system:
            raise HTTPException(
                status_code=400,
                detail="Crypto system not available. Cannot remediate without signature capability."
            )

        results = await watchdog.remediate_unsigned_logs()

        return {
            "success": True,
            "remediation_results": results,
            "timestamp": watchdog.last_scan.isoformat() if watchdog.last_scan else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remediation failed: {str(e)}")


@router.get('/alerts', summary="Get Current Alerts", response_model=AlertList)
async def get_alerts(
    watchdog: LogWatchdog = Depends(get_watchdog),
    severity_filter: Optional[str] = Query(
        default=None,
        description="Filter by severity: critical, high, medium, info"
    ),
    limit: int = Query(default=100, ge=1, le=1000)
) -> AlertList:
    """
    Get current alerts, optionally filtered by severity

    Parameters:
    - severity_filter: Filter by severity level (optional)
    - limit: Maximum number of alerts to return (default: 100)
    """
    try:
        alerts = watchdog.alerts

        if severity_filter:
            try:
                severity = AlertSeverity(severity_filter)
                alerts = [a for a in alerts if a.severity == severity]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid severity filter. Must be one of: critical, high, medium, info"
                )

        alerts = alerts[-limit:]  # Get last N alerts

        return {
            "success": True,
            "total_alerts": len(watchdog.alerts),
            "filtered_alerts": len(alerts),
            "alerts": [
                {
                    "alert_id": alert.alert_id,
                    "log_id": alert.log_id,
                    "operation": alert.operation,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "detected_at": alert.detected_at,
                    "action_required": alert.action_required
                }
                for alert in alerts
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve alerts: {str(e)}")


@router.get('/status', summary="Get Watchdog Status", response_model=StatusResponse)
async def get_status(
    watchdog: LogWatchdog = Depends(get_watchdog)
) -> StatusResponse:
    """
    Get current watchdog system status and statistics
    """
    try:
        total_logs = len(watchdog.monitored_logs)
        signed_logs = len([e for e in watchdog.monitored_logs.values() if e.log_id in watchdog.signature_records])

        critical_alerts = len([a for a in watchdog.alerts if a.severity == AlertSeverity.CRITICAL])
        high_alerts = len([a for a in watchdog.alerts if a.severity == AlertSeverity.HIGH])
        medium_alerts = len([a for a in watchdog.alerts if a.severity == AlertSeverity.MEDIUM])
        info_alerts = len([a for a in watchdog.alerts if a.severity == AlertSeverity.INFO])

        overall_status = "CRITICAL" if critical_alerts > 0 else "WARNING" if (high_alerts + critical_alerts) > 0 else "NORMAL"

        return {
            "success": True,
            "status": {
                "overall_status": overall_status,
                "log_monitoring": {
                    "total_logs": total_logs,
                    "signed_logs": signed_logs,
                    "unsigned_logs": total_logs - signed_logs,
                    "coverage": (signed_logs / total_logs * 100) if total_logs > 0 else 0
                },
                "alerts": {
                    "total": len(watchdog.alerts),
                    "critical": critical_alerts,
                    "high": high_alerts,
                    "medium": medium_alerts,
                    "info": info_alerts
                },
                "last_scan": watchdog.last_scan.isoformat() if watchdog.last_scan else None,
                "crypto_system_available": watchdog.crypto_system is not None,
                "critical_operations": watchdog.critical_operations
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.delete('/alerts/{alert_id}', summary="Clear Specific Alert", response_model=ClearAlertResponse)
async def clear_alert(
    alert_id: str,
    watchdog: LogWatchdog = Depends(get_watchdog)
) -> ClearAlertResponse:
    """
    Remove a specific alert from the watchdog system

    This doesn't resolve the underlying issue, just acknowledges the alert.
    """
    try:
        initial_count = len(watchdog.alerts)
        watchdog.alerts = [a for a in watchdog.alerts if a.alert_id != alert_id]

        if len(watchdog.alerts) == initial_count:
            raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")

        return {
            "success": True,
            "message": f"Alert cleared: {alert_id}",
            "alerts_remaining": len(watchdog.alerts)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear alert: {str(e)}")


@router.post('/set-crypto-system', summary="Set Crypto System for Verification", response_model=CryptoSystemResponse)
async def set_crypto_system(crypto_system: Optional[Any] = None) -> CryptoSystemResponse:
    """
    Set the crypto system instance for signature verification

    This should be called during application startup with the initialized
    CryptoSystem instance from the artifact signing module.
    """
    global _crypto_system

    _crypto_system = crypto_system

    # Reinitialize watchdog with new crypto system
    if _watchdog_instance:
        _watchdog_instance.crypto_system = crypto_system

    return {
        "success": True,
        "message": "Crypto system configured",
        "crypto_system_available": crypto_system is not None
    }
