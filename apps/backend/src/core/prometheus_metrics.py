"""
Prometheus Metrics for Kai Platform
=====================================
Provides a /metrics endpoint in Prometheus text format.

Metrics exposed:
  kai_missions_total           — counter: missions created (by tenant, mode)
  kai_missions_active          — gauge: currently running missions
  kai_mission_duration_seconds — histogram: mission durations
  kai_tool_executions_total    — counter: tool executions (by tool, status)
  kai_llm_tokens_total         — counter: LLM tokens consumed (by provider)
  kai_api_requests_total       — counter: HTTP requests (by method, path, status)
  kai_api_duration_seconds     — histogram: HTTP request durations
  kai_worker_queue_depth       — gauge: Celery queue depth (when Redis available)
  kai_errors_total             — counter: errors by type

All metrics are optional and degrade gracefully when prometheus_client is
not installed or when data sources are unavailable.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        CONTENT_TYPE_LATEST,
        generate_latest,
        CollectorRegistry,
        multiprocess,
        REGISTRY,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed — /metrics endpoint will return empty")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

if _PROMETHEUS_AVAILABLE:
    _reg = REGISTRY  # use default global registry

    # Mission counters
    MISSIONS_TOTAL = Counter(
        "kai_missions_total",
        "Total missions created",
        ["tenant_id", "execution_mode"],
        registry=_reg,
    )
    MISSIONS_ACTIVE = Gauge(
        "kai_missions_active",
        "Currently running missions",
        registry=_reg,
    )
    MISSION_DURATION = Histogram(
        "kai_mission_duration_seconds",
        "Mission execution duration in seconds",
        buckets=[30, 60, 120, 300, 600, 1200, 3600],
        registry=_reg,
    )

    # Tool executions
    TOOL_EXECUTIONS_TOTAL = Counter(
        "kai_tool_executions_total",
        "Total tool executions",
        ["tool_name", "status"],
        registry=_reg,
    )

    # LLM tokens
    LLM_TOKENS_TOTAL = Counter(
        "kai_llm_tokens_total",
        "Total LLM tokens consumed",
        ["provider", "token_type"],  # token_type: input | output
        registry=_reg,
    )

    # API requests
    API_REQUESTS_TOTAL = Counter(
        "kai_api_requests_total",
        "Total HTTP API requests",
        ["method", "path_pattern", "status_code"],
        registry=_reg,
    )
    API_DURATION = Histogram(
        "kai_api_duration_seconds",
        "HTTP request processing duration in seconds",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        registry=_reg,
    )

    # Queue depth
    WORKER_QUEUE_DEPTH = Gauge(
        "kai_worker_queue_depth",
        "Celery worker queue depth",
        ["queue_name"],
        registry=_reg,
    )

    # Errors
    ERRORS_TOTAL = Counter(
        "kai_errors_total",
        "Total platform errors",
        ["error_type"],
        registry=_reg,
    )

    # Approvals
    APPROVALS_PENDING = Gauge(
        "kai_approvals_pending",
        "Pending HIL approval gates",
        registry=_reg,
    )

    # Opportunity actions
    OPPORTUNITIES_APPROVED_TOTAL = Counter(
        "kai_opportunities_approved_total",
        "Total opportunities approved",
        registry=_reg,
    )
    OPPORTUNITIES_REJECTED_TOTAL = Counter(
        "kai_opportunities_rejected_total",
        "Total opportunities rejected",
        registry=_reg,
    )
    OPPORTUNITIES_EXECUTED_TOTAL = Counter(
        "kai_opportunities_executed_total",
        "Total opportunities executed",
        registry=_reg,
    )
    OPPORTUNITY_MISSIONS_GENERATED_TOTAL = Counter(
        "kai_missions_generated_from_opportunities_total",
        "Total missions generated from opportunity execution",
        registry=_reg,
    )
    OPPORTUNITY_VALIDATED_FINDINGS_TOTAL = Counter(
        "kai_validated_findings_from_opportunities_total",
        "Total validated findings produced by opportunity-derived missions",
        registry=_reg,
    )
    OPPORTUNITY_EXECUTION_SUCCESS_RATE = Histogram(
        "kai_opportunity_execution_success_rate",
        "Distribution of opportunity execution success rates",
        buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        registry=_reg,
    )
    OPPORTUNITY_YIELD = Histogram(
        "kai_yield_per_opportunity",
        "Distribution of realized yield proxy per executed opportunity",
        buckets=[0, 1, 2, 3, 5, 8, 13, 21],
        registry=_reg,
    )
    OPPORTUNITY_EXPANSIONS_CREATED_TOTAL = Counter(
        "kai_opportunity_expansions_created_total",
        "Total expansion opportunities created",
        registry=_reg,
    )
    OPPORTUNITY_EXPANSIONS_RANKED_TOTAL = Counter(
        "kai_opportunity_expansions_ranked_total",
        "Total expansion opportunities ranked",
        registry=_reg,
    )
    OPPORTUNITY_BATCHES_READY_TOTAL = Counter(
        "kai_opportunity_batches_ready_total",
        "Total opportunity batches prepared for review",
        registry=_reg,
    )
    OPPORTUNITY_EXPANSIONS_APPROVED_TOTAL = Counter(
        "kai_opportunity_expansions_approved_total",
        "Total expansion opportunities approved after target review",
        registry=_reg,
    )
    OPPORTUNITY_EXPANSION_TARGETS_SELECTED_TOTAL = Counter(
        "kai_opportunity_expansion_targets_selected_total",
        "Total reviewed targets selected for expansion execution",
        registry=_reg,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_mission_created(tenant_id: str = "", execution_mode: str = "live") -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        MISSIONS_TOTAL.labels(tenant_id=tenant_id, execution_mode=execution_mode).inc()
    except Exception:
        pass


def record_mission_started() -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        MISSIONS_ACTIVE.inc()
    except Exception:
        pass


def record_mission_completed(duration_seconds: float) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        MISSIONS_ACTIVE.dec()
        MISSION_DURATION.observe(duration_seconds)
    except Exception:
        pass


def record_tool_execution(tool_name: str, status: str = "success") -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        TOOL_EXECUTIONS_TOTAL.labels(tool_name=tool_name, status=status).inc()
    except Exception:
        pass


def record_llm_tokens(provider: str, input_tokens: int, output_tokens: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        LLM_TOKENS_TOTAL.labels(provider=provider, token_type="input").inc(input_tokens)
        LLM_TOKENS_TOTAL.labels(provider=provider, token_type="output").inc(output_tokens)
    except Exception:
        pass


def record_api_request(method: str, path_pattern: str, status_code: int, duration_seconds: float) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        API_REQUESTS_TOTAL.labels(
            method=method.upper(),
            path_pattern=_normalize_path(path_pattern),
            status_code=str(status_code),
        ).inc()
        API_DURATION.observe(duration_seconds)
    except Exception:
        pass


def record_error(error_type: str) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        ERRORS_TOTAL.labels(error_type=error_type).inc()
    except Exception:
        pass


def update_queue_depth(queue_name: str, depth: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        WORKER_QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)
    except Exception:
        pass


def update_approvals_pending(count: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        APPROVALS_PENDING.set(count)
    except Exception:
        pass


def record_opportunity_approved() -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITIES_APPROVED_TOTAL.inc()
    except Exception:
        pass


def record_opportunity_rejected() -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITIES_REJECTED_TOTAL.inc()
    except Exception:
        pass


def record_opportunity_executed() -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITIES_EXECUTED_TOTAL.inc()
    except Exception:
        pass


def record_opportunity_missions_generated(count: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_MISSIONS_GENERATED_TOTAL.inc(max(0, count))
    except Exception:
        pass


def observe_opportunity_validated_findings(count: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_VALIDATED_FINDINGS_TOTAL.inc(max(0, count))
    except Exception:
        pass


def observe_opportunity_execution_success_rate(value: float) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_EXECUTION_SUCCESS_RATE.observe(max(0.0, min(1.0, float(value))))
    except Exception:
        pass


def observe_opportunity_yield(value: float) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_YIELD.observe(max(0.0, float(value)))
    except Exception:
        pass


def record_opportunity_expansion_created() -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_EXPANSIONS_CREATED_TOTAL.inc()
    except Exception:
        pass


def record_opportunity_expansion_ranked() -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_EXPANSIONS_RANKED_TOTAL.inc()
    except Exception:
        pass


def record_opportunity_batch_ready(count: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_BATCHES_READY_TOTAL.inc(max(0, int(count)))
    except Exception:
        pass


def record_opportunity_expansion_approved(target_count: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        OPPORTUNITY_EXPANSIONS_APPROVED_TOTAL.inc()
        OPPORTUNITY_EXPANSION_TARGETS_SELECTED_TOTAL.inc(max(0, int(target_count)))
    except Exception:
        pass


def generate_metrics_output() -> tuple[str, str]:
    """
    Generate Prometheus text format metrics output.
    Returns (body, content_type).
    """
    if not _PROMETHEUS_AVAILABLE:
        return "# prometheus_client not installed\n", "text/plain; charset=utf-8"
    # Refresh queue depth from Redis if available
    _try_refresh_queue_depths()
    body = generate_latest(_reg).decode("utf-8")
    return body, CONTENT_TYPE_LATEST


def _normalize_path(path: str) -> str:
    """Collapse UUID/numeric path segments for Prometheus cardinality safety."""
    import re
    path = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{id}", path)
    path = re.sub(r"/\d+", "/{id}", path)
    return path


def _try_refresh_queue_depths() -> None:
    """Try to read Celery queue depths from Redis."""
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url or not _PROMETHEUS_AVAILABLE:
        return
    try:
        import redis  # type: ignore
        r = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        for q in ("tools", "intrusive", "celery"):
            depth = r.llen(q)
            WORKER_QUEUE_DEPTH.labels(queue_name=q).set(depth)
    except Exception:
        pass
