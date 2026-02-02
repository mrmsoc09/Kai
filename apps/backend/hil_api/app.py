import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from .routers import findings as findings_router
from .routers import hil as hil_router
from .routers import scopes as scopes_router
from .routers import providers as providers_router

load_dotenv()
app = FastAPI(title="K1 HiL API", version="0.1.0")

# Dev CORS (tighten in prod)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(findings_router.router)
app.include_router(hil_router.router)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

app.include_router(providers_router.router)

from .routers import embeddings as embeddings_router

app.include_router(scopes_router.router)

app.include_router(embeddings_router.router)
