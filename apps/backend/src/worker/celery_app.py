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
    from apps.backend.src.core.toolpacks import get_toolpack_manager
    from apps.backend.src.core.authorization_gate import enforce_authorization_gates, AuthorizationGateError
    from apps.backend.src.core.opsec_policy import get_opsec_policy_engine, OPSECPolicyError
    from apps.backend.src.core.hook_registry import get_hook_registry
    import time

    initialize_default_tools()
    hooks = get_hook_registry()
    registry = get_registry()
    manager = get_toolpack_manager()
    if manager.config is None:
        manager.load()
        manager.resolve_mappings(registry.get_all_schemas().keys())
    tool = registry.get(tool_id)
    if not tool:
        return {"status": "failed", "error": f"tool not found: {tool_id}"}
    if not manager.is_adapter_enabled(tool_id):
        return {"status": "failed", "error": f"tool disabled by toolpack policy: {tool_id}"}
    try:
        enforce_authorization_gates(tool_id, params)
    except AuthorizationGateError as exc:
        hooks.run(
            "safety_gate",
            {
                "hook_type": "safety_gate",
                "tool_id": tool_id,
                "run_id": params.get("run_id"),
                "status": "blocked",
            },
        )
        return {"status": "failed", "error": f"authorization gate blocked execution: {exc}"}
    hooks.run(
        "safety_gate",
        {
            "hook_type": "safety_gate",
            "tool_id": tool_id,
            "run_id": params.get("run_id"),
            "status": "authorized",
        },
    )

    opsec_method = str(
        params.get("scan_method")
        or params.get("method")
        or params.get("execution_method")
        or "osint"
    )
    opsec_engine = get_opsec_policy_engine()
    try:
        opsec_ticket = opsec_engine.acquire(opsec_method, tool_id)
    except OPSECPolicyError as exc:
        return {
            "status": "failed",
            "error": f"opsec policy blocked execution: {exc}",
            "opsec_method": opsec_method,
        }

    start = time.time()
    try:
        hooks.run(
            "pre_run",
            {
                "hook_type": "pre_run",
                "tool_id": tool_id,
                "run_id": params.get("run_id"),
                "status": "running",
            },
        )
        result = tool.execute(**params)
        elapsed = (time.time() - start) * 1000
        result.execution_time_ms = result.execution_time_ms or elapsed
        result_dict = result.to_dict()
    finally:
        status_value = result.status.value if "result" in locals() else "failed"
        hooks.run(
            "post_run",
            {
                "hook_type": "post_run",
                "tool_id": tool_id,
                "run_id": params.get("run_id"),
                "status": status_value,
            },
        )
        if status_value == "failed":
            hooks.run(
                "retry_gate",
                {
                    "hook_type": "retry_gate",
                    "tool_id": tool_id,
                    "run_id": params.get("run_id"),
                    "status": "candidate",
                },
            )
        opsec_engine.release(opsec_ticket, status_value)

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
            "opsec_method": opsec_method,
            "timestamp": time.time(),
        }
        with open(metrics_dir / "tool_runs.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass

    return result_dict
