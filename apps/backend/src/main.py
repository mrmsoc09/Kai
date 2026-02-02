from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import security configurations and middleware
from apps.backend.src.config.cors_config import get_cors_config, print_cors_config
from apps.backend.src.middleware.rate_limit import RateLimitMiddleware
from apps.backend.src.middleware.csrf import CSRFProtectionMiddleware
from apps.backend.src.middleware.security_headers import SecurityHeadersMiddleware

# Import routers exactly once
from apps.backend.src.routers import (
    agent0,
    auth,
    chains,
    docs,
    dorks,
    embeddings,
    evidence,
    export,
    findings,
    graph,
    intel,
    kai_authorized_scanning,
    knowledge,
    logs,
    mailer,
    mcp,
    metrics,
    orchestrator,
    persona,
    planner,
    programs,
    programs_discovery,
    realtime,
    recordings,
    reports,
    runs,
    scope,
    state,
    tools,
)
from apps.backend.src.routers import triage


app = FastAPI(title="K1 Backend")

# ==================== SECURITY MIDDLEWARE ====================
# Order matters: innermost middleware is applied last to responses

# 1. Security Headers (should be last, applied to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF Protection (before rate limiting)
app.add_middleware(CSRFProtectionMiddleware)

# 3. Rate Limiting (before CORS)
app.add_middleware(RateLimitMiddleware)

# 4. CORS (outermost, handles preflight requests)
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# Print CORS configuration for debugging
if os.getenv("DEBUG_MODE", "false").lower() == "true":
    print_cors_config()

# Health
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

# Register routers (logical groups)
# Public/low-priv status endpoints first
app.include_router(state.router)
app.include_router(metrics.router)

# Auth and scope
app.include_router(auth.router)
app.include_router(scope.router)

# Knowledge / OSINT utilities
app.include_router(dorks.router)
app.include_router(knowledge.router)
app.include_router(graph.router)

# Core operations (Tools and orchestration)
app.include_router(tools.router)
app.include_router(orchestrator.router)
app.include_router(planner.router)
app.include_router(chains.router)
app.include_router(embeddings.router)
app.include_router(intel.router)
app.include_router(mcp.router)

# Evidence and findings lifecycle
app.include_router(evidence.router)
app.include_router(findings.router)
app.include_router(recordings.router)
app.include_router(reports.router)
app.include_router(export.router)
app.include_router(programs.router)
app.include_router(programs_discovery.router)
app.include_router(runs.router)

# Communications and logs
app.include_router(mailer.router)
app.include_router(logs.router)
app.include_router(agent0.router)
app.include_router(docs.router)
app.include_router(triage.router)

# Kai Security - Authorized scanning with guardrails
app.include_router(kai_authorized_scanning.router)

# Optional: dynamic vector router (pgvector) if present
try:
    import importlib
    _vector_mod = importlib.import_module('apps.backend.src.routers.vector')
    app.include_router(_vector_mod.router)

except Exception:
    pass
