"""
Wordlist API — catalog, generation, and status endpoints.

Endpoints:
  GET  /api/v1/wordlists/status          — SecLists install status
  GET  /api/v1/wordlists/catalog         — list available wordlists
  GET  /api/v1/wordlists/recommend       — recommend lists for phase/tech
  POST /api/v1/wordlists/generate        — generate a custom wordlist
  GET  /api/v1/wordlists/seclists/{key}  — download a specific SecLists file
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wordlists", tags=["wordlists"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class WordlistStatusResponse(BaseModel):
    available: bool
    path: str
    total_catalog_entries: int
    installed_entries: int
    install_command: str


class WordlistCatalogEntry(BaseModel):
    key: str
    category: str
    path: str
    exists: bool
    size_lines: Optional[int]


class RecommendResponse(BaseModel):
    phase: str
    tech_stack: List[str]
    wordlists: List[dict]


class GenerateRequest(BaseModel):
    target_domain: str = ""
    company_name: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    discovered_paths: List[str] = Field(default_factory=list)
    discovered_params: List[str] = Field(default_factory=list)
    custom_seeds: List[str] = Field(default_factory=list)
    phase: str = "discovery"
    include_seclists: bool = True
    include_mutations: bool = True
    include_ai: bool = False
    ai_count: int = Field(default=200, ge=10, le=1000)
    max_words: int = Field(default=50_000, ge=100, le=500_000)
    dedupe: bool = True
    sort: bool = False


class GenerateResponse(BaseModel):
    total: int
    source_breakdown: dict
    generation_time_ms: float
    truncated: bool
    words: List[str] = Field(default_factory=list)
    preview: List[str] = Field(default_factory=list)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status", response_model=WordlistStatusResponse)
async def get_wordlist_status():
    """Check SecLists installation status."""
    from ..core.wordlist_manager import get_wordlist_manager
    wm = get_wordlist_manager()
    return wm.status()


@router.get("/catalog", response_model=List[WordlistCatalogEntry])
async def get_wordlist_catalog(
    category: Optional[str] = Query(None, description="Filter by category: content|dns|fuzz|api|cms|passwords|usernames"),
    only_installed: bool = Query(True, description="Only return installed wordlists"),
):
    """List all wordlists in the catalog."""
    from ..core.wordlist_manager import get_wordlist_manager
    wm = get_wordlist_manager()
    entries = wm.catalog(only_existing=only_installed)
    result = []
    for e in entries:
        if category and e.category != category:
            continue
        result.append(WordlistCatalogEntry(
            key=e.key,
            category=e.category,
            path=str(e.path),
            exists=e.exists,
            size_lines=e.size_lines,
        ))
    return result


@router.get("/recommend", response_model=RecommendResponse)
async def recommend_wordlists(
    phase: str = Query("discovery", description="Scan phase: recon|discovery|vuln_scanning|api_testing|brute_force"),
    tech_stack: Optional[str] = Query(None, description="Comma-separated tech stack: wordpress,php,django"),
):
    """Get recommended wordlists for a scan phase and tech stack."""
    from ..core.wordlist_manager import get_wordlist_manager
    wm = get_wordlist_manager()
    techs = [t.strip() for t in tech_stack.split(",")] if tech_stack else []
    paths = wm.for_phase(phase, tech_stack=techs)
    wordlists = []
    for p in paths:
        # Count lines efficiently
        try:
            with open(p, "rb") as f:
                count = sum(1 for _ in f)
        except OSError:
            count = 0
        wordlists.append({"path": str(p), "name": p.name, "lines": count})
    return RecommendResponse(phase=phase, tech_stack=techs, wordlists=wordlists)


@router.post("/generate", response_model=GenerateResponse)
async def generate_wordlist(body: GenerateRequest):
    """
    Generate a custom wordlist from context, SecLists, and optionally AI.

    Returns up to *max_words* deduplicated entries.
    The response includes a *preview* (first 100 words) and the full *words* list.
    For very large lists, stream the SecLists file directly via the /seclists/{key} endpoint.
    """
    from ..core.wordlist_generator import WordlistRequest, generate_wordlist as _gen

    req = WordlistRequest(
        target_domain=body.target_domain,
        company_name=body.company_name,
        tech_stack=body.tech_stack,
        discovered_paths=body.discovered_paths,
        discovered_params=body.discovered_params,
        custom_seeds=body.custom_seeds,
        phase=body.phase,
        include_seclists=body.include_seclists,
        include_mutations=body.include_mutations,
        include_ai=body.include_ai,
        ai_count=body.ai_count,
        max_words=body.max_words,
        dedupe=body.dedupe,
        sort=body.sort,
    )

    try:
        result = await _gen(req)
    except Exception as exc:
        logger.error("Wordlist generation error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return GenerateResponse(
        total=result.total,
        source_breakdown=result.source_breakdown,
        generation_time_ms=result.generation_time_ms,
        truncated=result.truncated,
        words=result.words,
        preview=result.words[:100],
    )


@router.get("/seclists/{key:path}", response_class=PlainTextResponse)
async def download_seclists_file(key: str):
    """
    Stream a SecLists wordlist by its catalog key (e.g. content/common).
    Returns plain text, one entry per line.
    """
    from ..core.wordlist_manager import get_wordlist_manager, CATALOG
    wm = get_wordlist_manager()

    # Validate key is in catalog (prevents path traversal)
    if key not in CATALOG:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown wordlist key {key!r}. Use GET /api/v1/wordlists/catalog for valid keys.",
        )

    path = wm.get(key)
    if path is None or not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Wordlist {key!r} is not installed. Run: scripts/install_seclists.sh",
        )

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        return PlainTextResponse(content=content, media_type="text/plain")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
