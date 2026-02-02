"""
Program Discovery API Router
Handles program scraping, discovery, and matching
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
import logging
import asyncio
import json

from ..core.program_scrapers import ScraperFactory, ScrapingProgress
from ..schemas.programs import Program, ProgramsListResponse, ScrapeJob
from ..schemas.common import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/programs", tags=["Programs"])

# In-memory storage for demo (replace with database in production)
_programs_cache: List[dict] = []
_scrape_jobs: dict = {}


@router.get("/health", tags=["Health"])
async def programs_health():
    """Health check for programs system"""
    return Response(
        success=True,
        data={
            "status": "healthy",
            "total_programs_cached": len(_programs_cache),
            "active_scrape_jobs": len(_scrape_jobs),
        },
    )


# ============================================================================
# Program Discovery Endpoints
# ============================================================================


@router.get("", response_model=Response)
async def list_programs(
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_payout: Optional[float] = Query(None),
    max_payout: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List available programs"""
    try:
        programs = _programs_cache.copy()

        # Apply filters
        if platform:
            programs = [p for p in programs if p.get("platform") == platform]

        if status:
            programs = [p for p in programs if p.get("status") == status]

        if min_payout is not None:
            programs = [p for p in programs if (p.get("max_payout") or 0) >= min_payout]

        if max_payout is not None:
            programs = [p for p in programs if (p.get("min_payout") or 0) <= max_payout]

        if search:
            search_lower = search.lower()
            programs = [
                p
                for p in programs
                if search_lower in p.get("name", "").lower()
                or search_lower in p.get("description", "").lower()
            ]

        # Sort by average payout (descending)
        programs.sort(key=lambda p: p.get("average_payout", 0), reverse=True)

        # Apply pagination
        total = len(programs)
        programs = programs[offset : offset + limit]

        return Response(
            success=True,
            data={
                "programs": programs,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    except Exception as e:
        logger.error(f"Error listing programs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{program_id}", response_model=Response)
async def get_program(program_id: str):
    """Get details for a specific program"""
    try:
        program = next((p for p in _programs_cache if p.get("id") == program_id), None)

        if not program:
            raise HTTPException(status_code=404, detail=f"Program not found: {program_id}")

        return Response(
            success=True,
            data=program,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting program: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Program Scraping Endpoints
# ============================================================================


@router.post("/scrape/{platform}", response_model=Response)
async def scrape_programs(
    platform: str,
    background_tasks: BackgroundTasks,
):
    """Start scraping programs from a platform"""
    try:
        scraper = ScraperFactory.create(platform)
        if not scraper:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported platform: {platform}. Available: {list(ScraperFactory._scrapers.keys())}",
            )

        job_id = f"{platform}_{int(__import__('time').time())}"
        _scrape_jobs[job_id] = {
            "id": job_id,
            "platform": platform,
            "status": "pending",
            "progress": 0,
        }

        async def run_scrape():
            try:
                _scrape_jobs[job_id]["status"] = "running"
                programs = await scraper.scrape()

                # Add to cache
                for prog in programs:
                    prog["id"] = f"{platform}_{prog.get('name', 'unknown').replace(' ', '_').lower()}"
                    _programs_cache.append(prog)

                _scrape_jobs[job_id]["status"] = "completed"
                _scrape_jobs[job_id]["programs_found"] = len(programs)
                logger.info(f"Scrape completed for {platform}: {len(programs)} programs")

            except Exception as e:
                _scrape_jobs[job_id]["status"] = "failed"
                _scrape_jobs[job_id]["error"] = str(e)
                logger.error(f"Scrape error for {platform}: {str(e)}")

        background_tasks.add_task(run_scrape)

        return Response(
            success=True,
            data={
                "job_id": job_id,
                "platform": platform,
                "status": "queued",
                "message": "Scrape job queued for execution",
            },
            status_code=202,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting scrape: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape-all", response_model=Response)
async def scrape_all_programs(background_tasks: BackgroundTasks):
    """Start scraping all platforms"""
    try:
        scrapers = ScraperFactory.get_all_scrapers()

        async def run_all_scrapes():
            for scraper in scrapers:
                try:
                    programs = await scraper.scrape()
                    for prog in programs:
                        prog["id"] = f"{scraper.platform_name}_{prog.get('name', 'unknown').replace(' ', '_').lower()}"
                        _programs_cache.append(prog)

                    logger.info(f"Scrape completed for {scraper.platform_name}: {len(programs)} programs")

                except Exception as e:
                    logger.error(f"Scrape error for {scraper.platform_name}: {str(e)}")

        background_tasks.add_task(run_all_scrapes)

        return Response(
            success=True,
            data={
                "message": "All platform scrapes queued",
                "platforms": [s.platform_name for s in scrapers],
            },
            status_code=202,
        )

    except Exception as e:
        logger.error(f"Error starting all scrapes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape-status/{job_id}", response_model=Response)
async def get_scrape_status(job_id: str):
    """Get status of a scrape job"""
    if job_id not in _scrape_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return Response(
        success=True,
        data=_scrape_jobs[job_id],
    )


@router.get("/scrape/stream/{platform}")
async def stream_scrape_programs(platform: str):
    """Stream programs as they are scraped from a platform"""
    scraper = ScraperFactory.create(platform)
    if not scraper:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform: {platform}",
        )

    async def event_generator():
        async def progress_callback(progress: ScrapingProgress):
            yield f"data: {json.dumps({'type': 'progress', 'data': {'percent': progress.get_progress_percent(), 'current': progress.current_program}})}\n\n"

        scraper.on_progress(progress_callback)

        try:
            yield f"data: {json.dumps({'type': 'start', 'platform': platform})}\n\n"

            programs = await scraper.scrape()

            for prog in programs:
                prog["id"] = f"{platform}_{prog.get('name', 'unknown').replace(' ', '_').lower()}"
                _programs_cache.append(prog)
                yield f"data: {json.dumps({'type': 'program', 'data': prog})}\n\n"

            yield f"data: {json.dumps({'type': 'complete', 'total': len(programs)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# ============================================================================
# Program Matching Endpoints
# ============================================================================


@router.post("/match", response_model=Response)
async def match_programs(
    finding_title: str = Query(...),
    finding_scope: str = Query(...),
    severity: Optional[str] = Query(None),
    vulnerability_type: Optional[str] = Query(None),
):
    """Find matching programs for a finding"""
    try:
        # Filter programs by scope and type
        matches = []

        for prog in _programs_cache:
            match_score = 0.0

            # Check scope match
            scope_items = prog.get("allowed_scope", [])
            for scope in scope_items:
                if scope.get("value") in finding_scope or "*" in scope.get("value", ""):
                    match_score += 0.5
                    break

            # Adjust by severity payout
            if severity:
                payouts = prog.get("payout_structure", [])
                for payout in payouts:
                    if payout.get("severity_level") == severity:
                        match_score += 0.3
                        break

            if match_score > 0:
                matches.append(
                    {
                        "program_id": prog.get("id"),
                        "program_name": prog.get("name"),
                        "match_score": round(match_score, 2),
                        "estimated_payout": prog.get("average_payout", 0),
                    }
                )

        # Sort by match score
        matches.sort(key=lambda m: m["match_score"], reverse=True)

        return Response(
            success=True,
            data={
                "finding": {
                    "title": finding_title,
                    "scope": finding_scope,
                    "severity": severity,
                },
                "matches": matches[:10],  # Top 10
                "total_matches": len(matches),
            },
        )

    except Exception as e:
        logger.error(f"Error matching programs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Platform Statistics
# ============================================================================


@router.get("/platforms/list", response_model=Response)
async def list_platforms():
    """List all supported platforms"""
    return Response(
        success=True,
        data={
            "platforms": list(ScraperFactory._scrapers.keys()),
            "total": len(ScraperFactory._scrapers),
        },
    )


@router.get("/statistics", response_model=Response)
async def get_statistics():
    """Get statistics about cached programs"""
    try:
        by_platform = {}
        total_payout = 0.0

        for prog in _programs_cache:
            platform = prog.get("platform", "unknown")
            if platform not in by_platform:
                by_platform[platform] = 0
            by_platform[platform] += 1
            total_payout += prog.get("average_payout", 0)

        return Response(
            success=True,
            data={
                "total_programs": len(_programs_cache),
                "by_platform": by_platform,
                "total_average_payout": round(total_payout, 2),
                "average_payout_per_program": round(total_payout / len(_programs_cache), 2) if _programs_cache else 0,
                "cached_since": "session_start",
            },
        )

    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
