"""
/metrics — Prometheus text format endpoint.

Requires ROLE_ADMIN or is restricted to internal scrape IP when configured.
Set K1_METRICS_INTERNAL_ONLY=true to restrict to 127.0.0.1 without auth.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from apps.backend.src.core.prometheus_metrics import generate_metrics_output

router = APIRouter(tags=["observability"])

_INTERNAL_ONLY = os.getenv("K1_METRICS_INTERNAL_ONLY", "false").lower() in {"1", "true", "yes"}
_SCRAPE_TOKEN = os.getenv("K1_METRICS_SCRAPE_TOKEN", "")


def _check_metrics_access(request: Request) -> None:
    """
    Allow access if:
    - K1_METRICS_INTERNAL_ONLY=false (open, rely on network perimeter), OR
    - request comes from loopback/internal IP, OR
    - valid K1_METRICS_SCRAPE_TOKEN provided in Authorization header
    """
    if not _INTERNAL_ONLY:
        return  # open

    # Check scrape token
    if _SCRAPE_TOKEN:
        auth_header = request.headers.get("Authorization", "")
        if auth_header == f"Bearer {_SCRAPE_TOKEN}":
            return

    # Check internal IP
    client_ip = (request.client.host if request.client else "")
    if client_ip in {"127.0.0.1", "::1", "localhost"}:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Metrics endpoint restricted. Set K1_METRICS_SCRAPE_TOKEN.",
    )


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus metrics",
    description="Prometheus text format metrics for scraping.",
)
async def prometheus_metrics(request: Request) -> PlainTextResponse:
    _check_metrics_access(request)
    body, content_type = generate_metrics_output()
    return PlainTextResponse(content=body, media_type=content_type)
