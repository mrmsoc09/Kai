from __future__ import annotations

from src.core.midnight_orchestrator import (
    MidnightOrchestrator
)


def run_midnight_orchestrator() -> None:
    """Midnight orchestrator task for Celery."""
    orchestrator = MidnightOrchestrator()
    orchestrator.run()
