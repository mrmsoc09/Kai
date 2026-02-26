from fastapi import APIRouter

from .tools import router as tools

try:
    from .tasks import router as tasks
except Exception:
    # Keep API bootable when optional worker deps (e.g., Celery) are unavailable.
    tasks = APIRouter()

__all__ = [
    "tools",
    "tasks",
]
