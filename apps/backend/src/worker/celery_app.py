"""Celery application for running tool adapters off the API thread."""
from __future__ import annotations

import os
from celery import Celery


CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BACKEND_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "k1_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BACKEND_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 3600},
)


@celery_app.task(name="run_tool")
def run_tool_task(tool_id: str, params: dict) -> dict:
    """Invoke a registered tool adapter by ID."""
    from apps.backend.src.core.tools import get_registry, initialize_default_tools
    from apps.backend.src.core.artifacts import write_json
    import time

    initialize_default_tools()
    registry = get_registry()
    tool = registry.get(tool_id)
    if not tool:
        return {"status": "failed", "error": f"tool not found: {tool_id}"}

    start = time.time()
    result = tool.execute(**params)
    elapsed = (time.time() - start) * 1000
    result.execution_time_ms = result.execution_time_ms or elapsed
    result_dict = result.to_dict()

    # Persist artifact for traceability (best-effort)
    try:
        artifact_id = result_dict.get("execution_id") or result_dict.get("tool_id") or tool_id
        path = write_json(artifact_id, result_dict)
        result_dict["artifact_path"] = path
    except Exception:
        pass

    # Lightweight telemetry
    try:
        from pathlib import Path
        import json

        metrics_dir = Path(__file__).resolve().parents[3] / "artifacts" / "telemetry"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "tool_id": tool_id,
            "status": result.status.value,
            "execution_time_ms": result_dict.get("execution_time_ms"),
            "timestamp": time.time(),
        }
        with open(metrics_dir / "tool_runs.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass

    return result_dict
