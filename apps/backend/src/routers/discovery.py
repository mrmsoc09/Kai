"""
Discovery Optimizer Router

Provides endpoints for optimized vulnerability discovery.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from apps.backend.src.core.discovery_optimizer import get_discovery_optimizer

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


class OptimizedHuntRequest(BaseModel):
    """Request model for optimized hunt."""
    target: str
    target_type: str = 'web'
    intensity: str = 'normal'
    time_budget: Optional[int] = None


@router.post("/optimized-hunt")
async def create_optimized_hunt(request: OptimizedHuntRequest) -> Dict[str, Any]:
    """Create an optimized vulnerability hunt.

    Combines EPSS prioritization with parallel tool chaining.
    """
    optimizer = get_discovery_optimizer()

    hunt = optimizer.create_optimized_hunt(
        target=request.target,
        target_type=request.target_type,
        intensity=request.intensity,
        time_budget=request.time_budget
    )

    return {
        'success': True,
        'hunt_id': hunt.hunt_id,
        'target': hunt.target,
        'tool_chains': [
            {
                'name': chain.name,
                'tools': chain.tools,
                'parallel': chain.parallel,
                'description': chain.description
            }
            for chain in hunt.tool_chains
        ],
        'estimated_findings': hunt.estimated_findings,
        'estimated_duration_minutes': hunt.estimated_duration
    }


@router.get("/tool-chains")
async def get_tool_chains() -> Dict[str, Any]:
    """Get all available tool chain templates."""
    optimizer = get_discovery_optimizer()
    templates = optimizer.get_tool_chain_templates()

    return {
        'success': True,
        'tool_chains': templates,
        'total': len(templates)
    }


@router.post("/execute-parallel")
async def execute_parallel_tools(
    target: str = Query(...),
    tools: str = Query(..., description="Comma-separated tool names")
) -> Dict[str, Any]:
    """Execute multiple tools in parallel."""
    tool_list = [t.strip() for t in tools.split(',')]

    optimizer = get_discovery_optimizer()
    results = await optimizer.execute_parallel_tools(tool_list, target)

    return {
        'success': True,
        'target': target,
        **results
    }


@router.post("/prioritize-cves")
async def prioritize_cves(
    cves: List[str],
    min_epss: float = Query(0.7, ge=0.0, le=1.0)
) -> Dict[str, Any]:
    """Prioritize CVEs using EPSS scores."""
    optimizer = get_discovery_optimizer()

    high_priority, low_priority = optimizer.prioritize_with_epss(cves, min_epss)

    return {
        'success': True,
        'total_cves': len(cves),
        'high_priority': {
            'count': len(high_priority),
            'cves': high_priority
        },
        'low_priority': {
            'count': len(low_priority),
            'cves': low_priority
        },
        'threshold': min_epss
    }


@router.get("/stats")
async def get_discovery_stats() -> Dict[str, Any]:
    """Get discovery optimizer statistics."""
    optimizer = get_discovery_optimizer()
    stats = optimizer.get_stats()

    return {
        'success': True,
        'stats': stats
    }
