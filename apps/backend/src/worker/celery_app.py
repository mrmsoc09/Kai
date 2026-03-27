"""Celery application for running tool adapters off the API thread."""
from __future__ import annotations

import logging
import os
from celery import Celery

logger = logging.getLogger(__name__)


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


K1_TASK_MAX_RETRIES = int(os.getenv("K1_TASK_MAX_RETRIES", "3"))


@celery_app.task(
    name="run_tool",
    bind=True,
    max_retries=K1_TASK_MAX_RETRIES,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def run_tool_task(
    self,
    tool_id: str,
    params: dict,
    *,
    user_id: str = "",
    program_id: str = "",
    certificate_id: str = "",
    workflow_id: str = "",
    scope_policy_hash: str = "",
) -> dict:
    """Invoke a registered tool adapter by ID.

    Auth context (user_id, program_id, certificate_id, workflow_id) should be
    provided by the enqueuing endpoint so the authorization gate has real
    credentials rather than falling back to params dict lookups.
    """
    from apps.backend.src.core.tools import get_registry, initialize_default_tools
    from apps.backend.src.core.artifacts import write_json
    from apps.backend.src.core.toolpacks import get_toolpack_manager
    from apps.backend.src.core.authorization_gate import enforce_authorization_gates, AuthorizationGateError
    from apps.backend.src.core.opsec_policy import get_opsec_policy_engine, OPSECPolicyError
    from apps.backend.src.core.execution_result_service import (
        ingest_worker_result_sync,
        mark_worker_execution_running_sync,
    )
    from apps.backend.src.core.hook_registry import get_hook_registry
    from apps.backend.src.models.enums import ToolExecutionStatusEnum
    from apps.backend.src.core.scope_guardrails import default_scope_policy_path
    import time
    import hashlib

    import re as _re

    # Validate tool_id before any path construction to prevent path injection.
    if not _re.match(r'^[a-zA-Z0-9_-]{1,64}$', tool_id):
        raise ValueError(f"Invalid tool_id format: {tool_id!r}")

    task_id = getattr(self.request, "id", "")
    retry_attempt = int(getattr(self.request, "retries", 0) or 0)
    max_retries = int(getattr(self, "max_retries", 0) or 0)

    # Calculate current policy hash for drift detection
    current_hash = "none"
    p_path = default_scope_policy_path()
    if p_path.exists():
        try:
            current_hash = hashlib.sha256(p_path.read_bytes()).hexdigest()
        except Exception:
            current_hash = "error"
    if task_id:
        mark_worker_execution_running_sync(
            worker_task_id=task_id,
            actor="worker.celery.run_tool",
        )

    def _ingest(
        *,
        status: ToolExecutionStatusEnum,
        payload: dict,
        error: str | None = None,
    ) -> None:
        if not task_id:
            return
        payload = dict(payload)
        payload.setdefault(
            "worker_diagnostics",
            {
                "worker_task_id": task_id,
                "retry_attempt": retry_attempt,
                "max_retries": max_retries,
                "tool_id": tool_id,
            },
        )
        ingest_worker_result_sync(
            worker_task_id=task_id,
            tool_status=status,
            result_payload_json=payload,
            error_message=error,
            stdout_ref=payload.get("stdout_ref"),
            stderr_ref=payload.get("stderr_ref"),
            actor="worker.celery.run_tool",
        )

    initialize_default_tools()
    hooks = get_hook_registry()
    registry = get_registry()
    manager = get_toolpack_manager()
    if manager.config is None:
        manager.load()
        manager.resolve_mappings(registry.get_all_schemas().keys())
    tool = registry.get(tool_id)
    if not tool:
        result_payload = {
            "status": "failed",
            "error": f"tool not found: {tool_id}",
            "retry_attempt": retry_attempt,
            "max_retries": max_retries,
        }
        _ingest(status=ToolExecutionStatusEnum.FAILED, payload=result_payload, error=result_payload["error"])
        return result_payload
    if not manager.is_adapter_enabled(tool_id):
        result_payload = {
            "status": "failed",
            "error": f"tool disabled by toolpack policy: {tool_id}",
            "retry_attempt": retry_attempt,
            "max_retries": max_retries,
        }
        _ingest(status=ToolExecutionStatusEnum.FAILED, payload=result_payload, error=result_payload["error"])
        return result_payload

    # Task 40: Fetch credentials from Vault at execution time using tool_id as key
    try:
        from apps.backend.src.core.hil_vault_client import VaultClient
        from apps.backend.src.core.tool_registry_catalog import get_catalog_entry as _get_cat

        vc = VaultClient()
        # Vault path is constructed exclusively from the validated tool_id.
        # Caller-supplied vault_path params are never accepted (path injection prevention).
        vault_secret_path = f"secret/tools/{tool_id}"
        creds = vc.read_secret(vault_secret_path)

        if creds:
            params = {**params, "_credentials": creds}
        else:
            cat = _get_cat(tool_id)
            if cat and cat.api_keys_required:
                err = f"Vault returned no credentials for tool='{tool_id}'"
                logger.error(err)
                result_payload = {"status": "failed", "error": err, "retry_attempt": retry_attempt, "max_retries": max_retries}
                _ingest(status=ToolExecutionStatusEnum.FAILED, payload=result_payload, error=err)
                return result_payload
    except Exception as exc:
        cat = None
        try:
            from apps.backend.src.core.tool_registry_catalog import get_catalog_entry as _get_cat
            cat = _get_cat(tool_id)
        except Exception: pass
        if cat and cat.api_keys_required:
            err = f"Vault unavailable and tool '{tool_id}' requires credentials: {exc}"
            logger.error(err)
            result_payload = {"status": "failed", "error": err, "retry_attempt": retry_attempt, "max_retries": max_retries}
            _ingest(status=ToolExecutionStatusEnum.FAILED, payload=result_payload, error=err)
            return result_payload
        logger.warning("Vault unavailable for tool=%s; proceeding without credentials: %s", tool_id, exc)

    try:
        # Re-enforce authorization gates (reads LIVE policy from disk via load_scope_policy)
        enforce_authorization_gates(
            tool_id,
            params,
            user_id=user_id or None,
            program_id=program_id or None,
            certificate_id=certificate_id or None,
            workflow_id=workflow_id or None,
        )
    except AuthorizationGateError as exc:
        logger.error(f"WORKER SAFETY BLOCK: Tool {tool_id} blocked at execution time: {exc}")
        hooks.run(
            "safety_gate",
            {
                "hook_type": "safety_gate",
                "tool_id": tool_id,
                "run_id": params.get("run_id"),
                "status": "blocked",
                "reason": str(exc),
                "policy_drift": scope_policy_hash != current_hash
            },
        )
        result_payload = {
            "status": "failed",
            "error": f"authorization gate blocked execution: {exc}",
            "retry_attempt": retry_attempt,
            "max_retries": max_retries,
            "blocked": True,
            "policy_drift": scope_policy_hash != current_hash
        }
        _ingest(status=ToolExecutionStatusEnum.FAILED, payload=result_payload, error=result_payload["error"])
        return result_payload
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
        result_payload = {
            "status": "failed",
            "error": f"opsec policy blocked execution: {exc}",
            "opsec_method": opsec_method,
            "retry_attempt": retry_attempt,
            "max_retries": max_retries,
        }
        _ingest(status=ToolExecutionStatusEnum.FAILED, payload=result_payload, error=result_payload["error"])
        return result_payload

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
        allowed_param_names = {param.name for param in getattr(tool, "parameters", [])}
        if allowed_param_names:
            filtered_params = {k: v for k, v in params.items() if k in allowed_param_names}
        else:
            # Fix: When allowed_param_names is empty, filtered_params must be empty
            filtered_params = {}

        # Unconditionally strip sensitive and internal keys regardless of schema
        keys_to_strip = {"_credentials", "vault_path", "_vault_path"}
        filtered_params = {
            k: v for k, v in filtered_params.items() 
            if k not in keys_to_strip and not k.startswith("_")
        }
        
        dropped_params = sorted(set(params.keys()) - set(filtered_params.keys()))

        # Preserve run correlation metadata when wrappers accept a metadata-like field.
        if "run_id" in allowed_param_names and "run_id" not in filtered_params:
            filtered_params["run_id"] = params.get("run_id") or workflow_id or task_id

        result = tool.execute(headers=extra_headers, **filtered_params)
        elapsed = (time.time() - start) * 1000
        result.execution_time_ms = result.execution_time_ms or elapsed
        result_dict = result.to_dict()
        result_dict.setdefault("retry_attempt", retry_attempt)
        result_dict.setdefault("max_retries", max_retries)
        if dropped_params:
            result_dict.setdefault("metadata", {})
            if isinstance(result_dict["metadata"], dict):
                result_dict["metadata"]["dropped_unmapped_params"] = dropped_params
    except Exception as exc:
        result_dict = {
            "status": "failed",
            "error": str(exc),
            "tool_id": tool_id,
            "opsec_method": opsec_method,
            "retry_attempt": retry_attempt,
            "max_retries": max_retries,
        }
        _ingest(status=ToolExecutionStatusEnum.FAILED, payload=result_dict, error=str(exc))
        raise
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

        env_artifacts = os.getenv("K1_ARTIFACTS_ROOT")
        artifacts_root = Path(env_artifacts) if env_artifacts else (Path(__file__).resolve().parents[3] / "artifacts")
        metrics_dir = artifacts_root / "telemetry"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "tool_id": tool_id,
            "status": result.status.value,
            "execution_time_ms": result_dict.get("execution_time_ms"),
            "opsec_method": opsec_method,
            "user_id": user_id or None,
            "workflow_id": workflow_id or None,
            "timestamp": time.time(),
        }
        with open(metrics_dir / "tool_runs.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass

    normalized_status = str(result_dict.get("status", "")).strip().lower()
    if normalized_status in {"completed", "success", "ok"}:
        ingest_status = ToolExecutionStatusEnum.COMPLETED
    elif normalized_status in {"canceled", "cancelled"}:
        ingest_status = ToolExecutionStatusEnum.CANCELED
    else:
        ingest_status = ToolExecutionStatusEnum.FAILED
        # Handle retries manually if within limits
        if retry_attempt < max_retries:
            logger.warning(
                f"Task {task_id} ({tool_id}) failed, retrying ({retry_attempt + 1}/{max_retries})..."
            )
            raise self.retry(exc=RuntimeError(result_dict.get("error", "Tool execution failed")))
        else:
            logger.error(
                f"MONITORING_ALERT: Task {task_id} ({tool_id}) exhausted all {max_retries} retries. "
                f"Final error: {result_dict.get('error')}"
            )

    _ingest(
        status=ingest_status,
        payload=result_dict,
        error=result_dict.get("error"),
    )

    return result_dict


# Register additional campaign tasks on worker startup.
try:
    from apps.backend.src.worker import campaign_tasks as _campaign_tasks  # noqa: F401
except Exception:
    _campaign_tasks = None

# Register scan pool tasks on worker startup.
try:
    from apps.backend.src.worker import scan_pool_tasks as _scan_pool_tasks  # noqa: F401
except Exception:
    _scan_pool_tasks = None

# ---------------------------------------------------------------------------
# Celery Beat schedule
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule = {
    "advance-scan-queues": {
        "task": "scan_queue_advance_all",
        "schedule": 120.0,  # every 2 minutes
        "options": {"queue": "tools"},
    },
}
celery_app.conf.timezone = "UTC"
