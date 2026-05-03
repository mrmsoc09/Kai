"""
Celery Application Configuration — Distributed Task Queue for K1 Platform.

Handles async tool execution, workflow processing, and scheduled tasks
with Redis as broker/backend.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from celery import Celery
from celery.signals import task_failure, task_success, task_prerun
from celery.exceptions import MaxRetriesExceededError

# Configure logging
logger = logging.getLogger(__name__)

# Redis configuration from environment
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Build Redis URL
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Celery configuration
celery_app = Celery(
    "k1_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "apps.backend.src.core.tool_tasks",
        "apps.backend.src.core.workflow_tasks",
        "apps.backend.src.core.notification_tasks",
        "apps.backend.src.worker.campaign_tasks",
        "apps.backend.src.worker.scan_pool_tasks",
    ],
)

# Celery settings
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "4")),
    
    # Result backend
    result_backend=REDIS_URL,
    result_expires=86400,  # 24 hours
    result_extended=True,
    
    # Task routing
    task_routes={
        "apps.backend.src.core.tool_tasks.*": {"queue": "tools"},
        "apps.backend.src.core.workflow_tasks.*": {"queue": "workflows"},
        "apps.backend.src.core.notification_tasks.*": {"queue": "notifications"},
        "apps.backend.src.worker.campaign_tasks.*": {"queue": "campaigns"},
        "apps.backend.src.worker.scan_pool_tasks.*": {"queue": "scan_pool"},
    },
    
    # Default queue
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    
    # Redis specific
    broker_transport_options={
        "visibility_timeout": 43200,  # 12 hours
        "queue_order_strategy": "priority",
    },
    redis_max_connections=20,
    
    # Task annotations
    task_annotations={
        "*": {
            "rate_limit": "10/m",
        }
    },
    
    # Beat schedule (periodic tasks)
    beat_schedule={
        "cleanup-old-results": {
            "task": "apps.backend.src.core.maintenance_tasks.cleanup_old_results",
            "schedule": 3600.0,  # Every hour
        },
        "sync-external-intel": {
            "task": "apps.backend.src.core.intel_tasks.sync_external_sources",
            "schedule": 1800.0,  # Every 30 minutes
        },
        "health-check-workers": {
            "task": "apps.backend.src.core.monitoring_tasks.worker_health_check",
            "schedule": 60.0,  # Every minute
        },
    },
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
)


@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **extras):
    """Log task start."""
    logger.info(f"Task {task.name}[{task_id}] started with args: {args}, kwargs: {kwargs}")


@task_success.connect
def task_success_handler(sender, result, **kwargs):
    """Log task success."""
    logger.info(f"Task {sender.name}[{sender.request.id}] completed successfully")


@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **extras):
    """Log task failure and send alerts."""
    logger.error(
        f"Task failed: {task_id}",
        extra={
            "exception": str(exception),
            "args": args,
            "kwargs": kwargs,
            "traceback": traceback,
        }
    )
    
    # TODO: Send alert to monitoring system
    # TODO: Store failure in database for analysis


class BaseTask(celery_app.Task):
    """Base task class with error handling and retry logic."""
    
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    max_retries = 3
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.exception(f"Task {task_id} failed: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying due to: {exc}")
        super().on_retry(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")
        super().on_success(retval, task_id, args, kwargs)


def get_celery_app() -> Celery:
    """Get configured Celery application."""
    return celery_app


if __name__ == "__main__":
    celery_app.start()
