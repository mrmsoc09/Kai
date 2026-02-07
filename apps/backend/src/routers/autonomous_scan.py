"""
Autonomous Scanning API Router
Endpoints for autonomous BBP selection and full scanning workflows
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
import logging

from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.autonomous_bbp_selector import get_bbp_selector, SelectionCriteria
from ..core.full_scan_orchestrator import get_scan_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/autonomous", tags=["Autonomous Scanning"])


# ============================================================================
# AUTONOMOUS BBP SELECTION
# ============================================================================

@router.post("/bbp/analyze-and-select")
async def analyze_and_select_programs(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Analyze available BBP programs and select optimal targets

    Payload:
        programs: List of programs to analyze
        max_programs: Maximum programs to select (default: 5)
        budget_cents: Available budget (default: 10000 = $100)
        criteria: Selection criteria (default: ["roi", "match_capability", "payout"])

    Returns:
        Selection result with scored and ranked programs
    """

    try:
        selector = get_bbp_selector()

        available_programs = payload.get("programs", [])
        max_programs = payload.get("max_programs", 5)
        budget_cents = payload.get("budget_cents", 10000)
        criteria_str = payload.get("criteria", ["roi", "match_capability", "payout"])

        # Convert string criteria to enum
        criteria = [SelectionCriteria(c) for c in criteria_str]

        if not available_programs:
            raise HTTPException(400, "No programs provided for analysis")

        # Execute selection
        result = await selector.analyze_and_select(
            available_programs=available_programs,
            max_programs=max_programs,
            budget_cents=budget_cents,
            criteria=criteria
        )

        # Format response
        selected = [
            {
                "program_id": score.program_id,
                "program_name": score.program_name,
                "platform": score.platform,
                "total_score": score.total_score,
                "recommendation": score.recommendation,
                "reasoning": score.reasoning,
                "estimated_cost_cents": score.estimated_cost_cents,
                "estimated_findings": score.estimated_findings,
                "estimated_payout_range": score.estimated_payout_range,
                "breakdown": {
                    "payout_score": score.payout_score,
                    "scope_score": score.scope_score,
                    "capability_match": score.capability_match_score,
                    "difficulty_score": score.difficulty_score,
                    "roi_score": score.roi_score,
                    "time_to_value": score.time_to_value_score
                }
            }
            for score in result.selected_programs
        ]

        return {
            "ok": True,
            "selected_programs": selected,
            "total_analyzed": result.total_analyzed,
            "selection_timestamp": result.selection_timestamp.isoformat(),
            "budget_allocated_cents": result.budget_allocated_cents,
            "budget_allocated_usd": result.budget_allocated_cents / 100,
            "estimated_total_payout": result.estimated_total_payout,
            "estimated_total_payout_usd": result.estimated_total_payout / 100,
            "selection_reasoning": result.reasoning
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error in BBP selection: {str(e)}")
        raise HTTPException(500, f"Selection failed: {str(e)}")


@router.get("/bbp/capabilities")
async def get_platform_capabilities(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get platform capabilities for vulnerability testing

    Returns:
        Capability scores (0.0-1.0) for different vulnerability types
    """

    try:
        selector = get_bbp_selector()
        capabilities = selector.platform_capabilities

        return {
            "ok": True,
            "capabilities": capabilities,
            "summary": {
                "total_capabilities": len(capabilities),
                "high_capability": sum(1 for v in capabilities.values() if v >= 0.8),
                "medium_capability": sum(1 for v in capabilities.values() if 0.5 <= v < 0.8),
                "low_capability": sum(1 for v in capabilities.values() if v < 0.5)
            }
        }

    except Exception as e:
        logger.error(f"Error getting capabilities: {str(e)}")
        raise HTTPException(500, str(e))


# ============================================================================
# FULL SCAN ORCHESTRATION
# ============================================================================

@router.post("/scan/initiate")
async def initiate_autonomous_scan(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Initiate autonomous full scan workflow

    User initiates, platform:
    1. Selects optimal BBP programs
    2. Executes full scan on each
    3. Generates reports
    4. Notifies stakeholders (optional)

    Payload:
        user_id: User initiating scan
        budget_cents: Budget allocation (default: 10000 = $100)
        max_programs: Maximum programs to scan (default: 3)
        notify_stakeholders: Email findings to programs (default: true)

    Returns:
        Scan result with findings and reports
    """

    try:
        orchestrator = get_scan_orchestrator()

        user_id = payload.get("user_id", "anonymous")
        budget_cents = payload.get("budget_cents", 10000)
        max_programs = payload.get("max_programs", 3)
        notify_stakeholders = payload.get("notify_stakeholders", True)

        logger.info(f"Initiating autonomous scan for user {user_id}")

        # Execute autonomous scan
        result = await orchestrator.initiate_autonomous_scan(
            user_id=user_id,
            budget_cents=budget_cents,
            max_programs=max_programs,
            notify_stakeholders=notify_stakeholders
        )

        if not result:
            raise HTTPException(500, "Scan failed - no results returned")

        return {
            "ok": True,
            "scan_id": result.scan_id,
            "program_id": result.program_id,
            "program_name": result.program_name,
            "target": result.target,
            "status": result.status,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "findings_summary": {
                "total": result.total_findings,
                "critical": result.critical_findings,
                "high": result.high_findings,
                "medium": result.medium_findings,
                "low": result.low_findings
            },
            "cost": {
                "total_cents": result.total_cost_cents,
                "total_usd": result.total_cost_cents / 100
            },
            "stakeholder_notified": result.stakeholder_notified,
            "final_report_path": result.final_report_path,
            "phases_completed": len(result.phases)
        }

    except Exception as e:
        logger.error(f"Error initiating autonomous scan: {str(e)}")
        raise HTTPException(500, f"Scan initiation failed: {str(e)}")


@router.post("/scan/execute")
async def execute_full_scan(
    payload: Dict[str, Any],
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Execute full scan on a specific BBP program

    Payload:
        program_id: BBP program ID
        program_name: BBP program name
        user_id: User initiating scan
        budget_cents: Budget for scan (default: 10000 = $100)
        notify_stakeholders: Email findings (default: true)

    Returns:
        Full scan result with all phases
    """

    try:
        orchestrator = get_scan_orchestrator()

        program_id = payload.get("program_id")
        program_name = payload.get("program_name")
        user_id = payload.get("user_id", "anonymous")
        budget_cents = payload.get("budget_cents", 10000)
        notify_stakeholders = payload.get("notify_stakeholders", True)

        if not program_id or not program_name:
            raise HTTPException(400, "program_id and program_name required")

        logger.info(f"Executing full scan for program {program_name}")

        # Execute scan
        result = await orchestrator.execute_full_scan(
            program_id=program_id,
            program_name=program_name,
            user_id=user_id,
            budget_cents=budget_cents,
            notify_stakeholders=notify_stakeholders
        )

        # Format phases
        phases = [
            {
                "phase": phase.phase,
                "status": phase.status,
                "started_at": phase.started_at.isoformat(),
                "completed_at": phase.completed_at.isoformat() if phase.completed_at else None,
                "duration_seconds": phase.duration_seconds,
                "findings_count": phase.findings_count,
                "cost_cents": phase.cost_cents,
                "errors": phase.errors
            }
            for phase in result.phases
        ]

        return {
            "ok": True,
            "scan_id": result.scan_id,
            "program_id": result.program_id,
            "program_name": result.program_name,
            "target": result.target,
            "status": result.status,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "findings_summary": {
                "total": result.total_findings,
                "critical": result.critical_findings,
                "high": result.high_findings,
                "medium": result.medium_findings,
                "low": result.low_findings
            },
            "cost": {
                "total_cents": result.total_cost_cents,
                "total_usd": result.total_cost_cents / 100
            },
            "stakeholder_notified": result.stakeholder_notified,
            "final_report_path": result.final_report_path,
            "phases": phases
        }

    except Exception as e:
        logger.error(f"Error executing full scan: {str(e)}")
        raise HTTPException(500, f"Scan execution failed: {str(e)}")


@router.get("/scan/status/{scan_id}")
async def get_scan_status(
    scan_id: str,
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Get status of active scan

    Returns:
        Current scan status and progress
    """

    try:
        orchestrator = get_scan_orchestrator()
        result = orchestrator.get_scan_status(scan_id)

        if not result:
            raise HTTPException(404, f"Scan {scan_id} not found")

        return {
            "ok": True,
            "scan_id": result.scan_id,
            "status": result.status,
            "progress": {
                "phases_completed": len(result.phases),
                "current_phase": result.phases[-1].phase if result.phases else None
            },
            "findings_summary": {
                "total": result.total_findings,
                "critical": result.critical_findings,
                "high": result.high_findings,
                "medium": result.medium_findings,
                "low": result.low_findings
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scan status: {str(e)}")
        raise HTTPException(500, str(e))


@router.get("/scan/list")
async def list_active_scans(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    List all active scans

    Returns:
        List of active scans with status
    """

    try:
        orchestrator = get_scan_orchestrator()
        scans = orchestrator.list_active_scans()

        formatted_scans = [
            {
                "scan_id": scan.scan_id,
                "program_name": scan.program_name,
                "target": scan.target,
                "status": scan.status,
                "started_at": scan.started_at.isoformat(),
                "total_findings": scan.total_findings,
                "phases_completed": len(scan.phases)
            }
            for scan in scans
        ]

        return {
            "ok": True,
            "active_scans": formatted_scans,
            "count": len(formatted_scans)
        }

    except Exception as e:
        logger.error(f"Error listing scans: {str(e)}")
        raise HTTPException(500, str(e))


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@router.get("/health")
async def autonomous_scan_health(
    _=Depends(require_roles(ROLE_OPERATOR))
) -> Dict[str, Any]:
    """
    Health check for autonomous scanning system

    Returns:
        System health and component status
    """

    try:
        # Check selector
        selector = get_bbp_selector()
        selector_healthy = selector is not None

        # Check orchestrator
        orchestrator = get_scan_orchestrator()
        orchestrator_healthy = orchestrator is not None

        # Check dependencies
        try:
            from ..core.repair_pipeline import get_repair_pipeline
            repair_available = True
        except:
            repair_available = False

        try:
            from ..integrations.notification_service import get_notification_service
            notifications_available = True
        except:
            notifications_available = False

        all_healthy = all([
            selector_healthy,
            orchestrator_healthy,
            repair_available,
            notifications_available
        ])

        return {
            "ok": all_healthy,
            "status": "healthy" if all_healthy else "degraded",
            "components": {
                "bbp_selector": selector_healthy,
                "scan_orchestrator": orchestrator_healthy,
                "repair_pipeline": repair_available,
                "notifications": notifications_available
            },
            "active_scans": len(orchestrator.list_active_scans()) if orchestrator_healthy else 0
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "ok": False,
            "status": "unhealthy",
            "error": str(e)
        }
