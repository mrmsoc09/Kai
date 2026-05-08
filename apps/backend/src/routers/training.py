"""Training data management API endpoints."""

from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..core.persistence import get_db
from ..core.training_tasks import update_real_training_data_task, generate_synthetic_data_task
from ..services.report_intelligence_engine import ReportIntelligenceEngine

router = APIRouter(prefix="/training", tags=["training"])


@router.post("/update-real-data")
async def update_real_training_data(
    background_tasks: BackgroundTasks,
    data_dir: Optional[str] = "/home/k1-admin/Kai/real_scan_data"
) -> Dict[str, Any]:
    """Trigger update of training data from real scan data."""
    if not Path(data_dir).exists():
        raise HTTPException(status_code=404, detail=f"Data directory not found: {data_dir}")

    # Run as background task
    task = update_real_training_data_task.delay(data_dir)
    return {
        "message": "Training data update started",
        "task_id": task.id,
        "status": "running"
    }


@router.post("/generate-synthetic")
async def generate_synthetic_data(
    background_tasks: BackgroundTasks,
    output_dir: Optional[str] = "/home/k1-admin/Kai/synthetic_data",
    chains: int = 10,
    zero_days: int = 5
) -> Dict[str, Any]:
    """Generate advanced synthetic training data."""
    # Run as background task
    task = generate_synthetic_data_task.delay(output_dir, chains, zero_days)
    return {
        "message": "Synthetic data generation started",
        "task_id": task.id,
        "status": "running"
    }


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a training task."""
    from ..celery_app import celery_app
    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    elif result.state == "PROGRESS":
        return {"task_id": task_id, "status": "running", "info": result.info}
    elif result.state == "SUCCESS":
        return {"task_id": task_id, "status": "completed", "result": result.result}
    else:
        return {"task_id": task_id, "status": "failed", "error": str(result.info)}


@router.post("/schedule-daily")
async def schedule_daily_updates() -> Dict[str, str]:
    """Set up daily scheduled updates (requires Celery Beat)."""
    # This would typically be configured in celery beat schedule
    # For now, return instructions
    return {
        "message": "Daily updates should be configured in Celery Beat schedule",
        "instructions": "Add 'training.update_real_training_data' task to CELERY_BEAT_SCHEDULE in settings"
    }