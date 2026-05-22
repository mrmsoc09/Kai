"""
Budget Management API Router
Provides endpoints for budget monitoring, analytics, and emergency controls
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from ..core.budget_tracker import get_budget_tracker, BudgetStatus
from ..core.cost_controller import get_cost_controller
from ..core.hybrid_model_router import get_hybrid_router
from ..core.auth import require_roles, ROLE_ADMIN

router = APIRouter(
    prefix="/api/v1/budget",
    tags=["budget"],
    dependencies=[Depends(require_roles(ROLE_ADMIN))],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class BudgetIncreaseRequest(BaseModel):
    """Request to increase budget"""
    amount_cents: int
    justification: str
    user_id: str


class BudgetIncreaseResponse(BaseModel):
    """Response for budget increase"""
    success: bool
    message: str
    new_budget_cents: int
    approved_by: str


class SessionBudgetResponse(BaseModel):
    """Session budget information"""
    session_id: str
    budget_cents: int
    spent_cents: float
    remaining_cents: float
    utilization_percent: float
    status: str
    transaction_count: int
    created_at: str


class DailyBudgetResponse(BaseModel):
    """Daily budget information"""
    date: str
    budget_cents: int
    spent_cents: float
    remaining_cents: float
    utilization_percent: float
    status: str
    transaction_count: int
    session_count: int


# ============================================================================
# Budget Endpoints
# ============================================================================

@router.get("/session/{session_id}", response_model=SessionBudgetResponse)
async def get_session_budget(session_id: str):
    """
    Get current session budget and spending.

    Returns detailed budget information including:
    - Total budget allocation
    - Current spending
    - Remaining budget
    - Utilization percentage
    - Status (normal/warning/critical/exhausted)
    """
    try:
        tracker = get_budget_tracker()
        budget = tracker.get_session_budget(session_id)

        return SessionBudgetResponse(
            session_id=budget.session_id,
            budget_cents=budget.initial_budget_cents,
            spent_cents=budget.spent_cents,
            remaining_cents=budget.remaining_cents,
            utilization_percent=budget.utilization_percent,
            status=budget.status.value,
            transaction_count=budget.transaction_count,
            created_at=budget.created_at.isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching session budget: {str(e)}")


@router.get("/daily", response_model=DailyBudgetResponse)
async def get_daily_budget():
    """
    Get current daily budget and spending.

    Returns daily aggregate information across all sessions.
    """
    try:
        tracker = get_budget_tracker()
        budget = tracker.get_daily_budget()

        return DailyBudgetResponse(
            date=budget.date,
            budget_cents=budget.total_budget_cents,
            spent_cents=budget.spent_cents,
            remaining_cents=budget.remaining_cents,
            utilization_percent=budget.utilization_percent,
            status=budget.status.value,
            transaction_count=budget.transaction_count,
            session_count=budget.session_count
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching daily budget: {str(e)}")


@router.post("/session/{session_id}/increase", response_model=BudgetIncreaseResponse)
async def request_budget_increase(session_id: str, request: BudgetIncreaseRequest):
    """
    Request emergency budget increase with approval.

    Small increases (< $5) are auto-approved.
    Larger increases require admin approval.
    """
    try:
        controller = get_cost_controller()

        success, message = await controller.request_emergency_budget(
            session_id=session_id,
            additional_cents=request.amount_cents,
            justification=request.justification,
            user_id=request.user_id
        )

        if not success:
            raise HTTPException(status_code=403, detail=message)

        # Get updated budget
        tracker = get_budget_tracker()
        budget = tracker.get_session_budget(session_id)

        return BudgetIncreaseResponse(
            success=True,
            message=message,
            new_budget_cents=budget.initial_budget_cents,
            approved_by=f"auto_approved_{request.user_id}" if request.amount_cents <= 500 else "pending"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing budget increase: {str(e)}")


@router.get("/analytics")
async def get_budget_analytics():
    """
    Get comprehensive budget analytics.

    Returns:
    - Daily and session summaries
    - Spending breakdown by model
    - Transaction statistics
    - Cost trends
    """
    try:
        tracker = get_budget_tracker()
        analytics = await tracker.get_budget_analytics()

        return analytics

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analytics: {str(e)}")


@router.get("/cost-summary/{session_id}")
async def get_cost_summary(
    session_id: str,
    timeframe: str = Query("session", regex="^(session|daily)$")
):
    """
    Get cost summary for a session or daily.

    Query Parameters:
    - timeframe: "session" or "daily"
    """
    try:
        controller = get_cost_controller()
        summary = await controller.get_cost_summary(
            session_id=session_id if timeframe == "session" else None,
            timeframe=timeframe
        )

        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cost summary: {str(e)}")


@router.get("/routing-analytics")
async def get_routing_analytics(session_id: Optional[str] = None):
    """
    Get routing analytics and model selection statistics.

    Shows how tasks are being routed between local and paid models.
    """
    try:
        router_instance = get_hybrid_router()
        analytics = await router_instance.get_routing_analytics(session_id)

        return analytics

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching routing analytics: {str(e)}")


@router.post("/reset-daily")
async def reset_daily_budget():
    """
    Manually trigger daily budget reset.

    Normally runs automatically at midnight UTC.
    This endpoint allows manual reset for testing or emergency situations.
    """
    try:
        tracker = get_budget_tracker()
        success, message = await tracker.reset_daily_budget()

        if not success:
            raise HTTPException(status_code=500, detail=message)

        return {
            "success": True,
            "message": message,
            "reset_at": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting daily budget: {str(e)}")


@router.get("/health")
async def budget_health_check():
    """
    Health check for budget tracking system.

    Returns status of budget tracker, cost controller, and hybrid router.
    """
    try:
        tracker = get_budget_tracker()
        controller = get_cost_controller()
        router_instance = get_hybrid_router()

        daily = tracker.get_daily_budget()

        return {
            "status": "healthy",
            "components": {
                "budget_tracker": "operational",
                "cost_controller": "operational",
                "hybrid_router": "operational"
            },
            "daily_budget_status": daily.status.value,
            "daily_utilization_percent": daily.utilization_percent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ============================================================================
# Cost Forecasting Endpoints
# ============================================================================

class TaskEstimate(BaseModel):
    """Task for cost estimation"""
    task_id: str
    name: str
    description: str
    complexity_estimate: int
    estimated_tokens_input: Optional[int] = None
    estimated_tokens_output: Optional[int] = None


class ForecastRequest(BaseModel):
    """Request for cost forecast"""
    session_id: str
    pending_tasks: List[TaskEstimate]


@router.post("/forecast")
async def forecast_session_cost(request: ForecastRequest):
    """
    Forecast total cost for pending tasks.

    Provides:
    - Estimated cost per task
    - Total estimated cost
    - Budget sufficiency check
    - Recommendations for optimization
    """
    try:
        from ..core.model_bidding import TaskDefinition

        controller = get_cost_controller()

        # Convert TaskEstimate to TaskDefinition
        tasks = []
        for task_est in request.pending_tasks:
            task_def = TaskDefinition(
                task_id=task_est.task_id,
                name=task_est.name,
                description=task_est.description,
                complexity_estimate=task_est.complexity_estimate,
                required_capabilities=["reasoning"],
                security_sensitive=False,
                estimated_tokens_input=task_est.estimated_tokens_input or 2000,
                estimated_tokens_output=task_est.estimated_tokens_output or 1000
            )
            tasks.append(task_def)

        # Get forecast
        forecast = await controller.forecast_session_cost(
            session_id=request.session_id,
            pending_tasks=tasks
        )

        return forecast

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating forecast: {str(e)}")


# ============================================================================
# Budget Alerts Endpoint
# ============================================================================

@router.get("/alerts/{session_id}")
async def get_budget_alerts(session_id: str):
    """
    Get budget alerts for a session.

    Returns all warning and critical alerts issued.
    """
    try:
        tracker = get_budget_tracker()
        budget = tracker.get_session_budget(session_id)

        alerts = [
            {
                "timestamp": alert.timestamp.isoformat(),
                "alert_type": alert.alert_type,
                "message": alert.message,
                "utilization_percent": alert.utilization_percent,
                "current_spent_cents": alert.current_spent_cents,
                "budget_limit_cents": alert.budget_limit_cents
            }
            for alert in budget.alerts_sent
        ]

        return {
            "session_id": session_id,
            "alert_count": len(alerts),
            "alerts": alerts
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")
