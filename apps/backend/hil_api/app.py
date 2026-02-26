"""Legacy HiL API compatibility app.

This module now forwards to consolidated implementations in ``apps/backend/src``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.src.routers import (
    hil_embeddings,
    hil_findings,
    hil_providers,
    hil_scopes,
    hil_workflow,
)

app = FastAPI(title="K1 HiL API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hil_findings.router)
app.include_router(hil_workflow.router)
app.include_router(hil_scopes.router)
app.include_router(hil_providers.router)
app.include_router(hil_embeddings.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
