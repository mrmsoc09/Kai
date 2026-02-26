"""
EPSS Router - Exploit Prediction Scoring System endpoints

Provides access to EPSS scores for vulnerability prioritization.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from apps.backend.src.integrations.epss_client import get_epss_client, EPSSScore

router = APIRouter(prefix="/api/v1/epss", tags=["epss"])


class EPSSScoreResponse(BaseModel):
    """EPSS score response model."""
    cve_id: str
    epss: float
    percentile: float
    date: str
    fetched_at: str
    risk_level: str  # low, medium, high, critical


class EPSSBatchRequest(BaseModel):
    """Batch request model."""
    cve_ids: List[str]


@router.get("/scores/{cve_id}")
async def get_cve_score(cve_id: str) -> Dict[str, Any]:
    """Get EPSS score for a specific CVE.

    Args:
        cve_id: CVE identifier (e.g., CVE-2021-44228)

    Returns:
        EPSS score and metadata
    """
    client = get_epss_client()

    score = await client.get_score(cve_id)

    if not score:
        raise HTTPException(
            status_code=404,
            detail=f"EPSS score not found for {cve_id}"
        )

    return {
        "success": True,
        "cve_id": score.cve_id,
        "epss": score.epss,
        "percentile": score.percentile,
        "date": score.date,
        "fetched_at": score.fetched_at,
        "risk_level": _get_risk_level(score.epss),
        "interpretation": _interpret_score(score.epss, score.percentile)
    }


@router.post("/scores/batch")
async def get_batch_scores(request: EPSSBatchRequest) -> Dict[str, Any]:
    """Get EPSS scores for multiple CVEs.

    Args:
        request: Batch request with list of CVE IDs

    Returns:
        Dict of CVE scores
    """
    client = get_epss_client()

    scores = await client.get_scores_batch(request.cve_ids)

    results = []
    for cve_id, score in scores.items():
        results.append({
            "cve_id": score.cve_id,
            "epss": score.epss,
            "percentile": score.percentile,
            "date": score.date,
            "fetched_at": score.fetched_at,
            "risk_level": _get_risk_level(score.epss),
        })

    # Prioritize
    high_priority, low_priority = client.prioritize_cves(scores, threshold=0.5)

    return {
        "success": True,
        "total": len(scores),
        "scores": results,
        "prioritization": {
            "high_priority": high_priority,
            "low_priority": low_priority,
            "threshold": 0.5
        }
    }


@router.get("/high-risk")
async def get_high_risk_cves(
    min_epss: float = Query(0.7, ge=0.0, le=1.0, description="Minimum EPSS score"),
    limit: int = Query(100, le=1000, description="Maximum results")
) -> Dict[str, Any]:
    """Get CVEs with high exploitation probability.

    Args:
        min_epss: Minimum EPSS score (0-1)
        limit: Maximum number of results

    Returns:
        List of high-risk CVEs
    """
    client = get_epss_client()

    scores = await client.get_high_risk_cves(min_epss=min_epss, limit=limit)

    return {
        "success": True,
        "min_epss": min_epss,
        "count": len(scores),
        "cves": [
            {
                "cve_id": score.cve_id,
                "epss": score.epss,
                "percentile": score.percentile,
                "date": score.date,
                "risk_level": _get_risk_level(score.epss),
            }
            for score in scores
        ]
    }


@router.get("/prioritize")
async def prioritize_findings(
    findings: str = Query(..., description="Comma-separated CVE IDs"),
    threshold: float = Query(0.5, ge=0.0, le=1.0, description="Priority threshold")
) -> Dict[str, Any]:
    """Prioritize findings based on EPSS scores.

    Args:
        findings: Comma-separated list of CVE IDs
        threshold: EPSS threshold for high priority

    Returns:
        Prioritized findings
    """
    cve_ids = [cve.strip() for cve in findings.split(",")]

    client = get_epss_client()

    scores = await client.get_scores_batch(cve_ids)

    if not scores:
        return {
            "success": False,
            "error": "No EPSS scores found for provided CVEs"
        }

    high_priority, low_priority = client.prioritize_cves(scores, threshold=threshold)

    return {
        "success": True,
        "total_cves": len(scores),
        "threshold": threshold,
        "high_priority": {
            "count": len(high_priority),
            "cves": [
                {
                    "cve_id": cve_id,
                    "epss": scores[cve_id].epss,
                    "percentile": scores[cve_id].percentile,
                    "risk_level": _get_risk_level(scores[cve_id].epss)
                }
                for cve_id in high_priority
            ]
        },
        "low_priority": {
            "count": len(low_priority),
            "cves": [
                {
                    "cve_id": cve_id,
                    "epss": scores[cve_id].epss,
                    "percentile": scores[cve_id].percentile,
                    "risk_level": _get_risk_level(scores[cve_id].epss)
                }
                for cve_id in low_priority
            ]
        }
    }


@router.get("/stats")
async def get_epss_stats() -> Dict[str, Any]:
    """Get EPSS client statistics.

    Returns:
        Client usage statistics
    """
    client = get_epss_client()

    stats = client.get_stats()

    return {
        "success": True,
        "stats": stats
    }


@router.get("/heatmap-data")
async def get_heatmap_data(
    cve_ids: Optional[str] = Query(None, description="Comma-separated CVE IDs for specific data"),
    limit: int = Query(50, le=200, description="Number of recent high-risk CVEs to include")
) -> Dict[str, Any]:
    """Get data formatted for heat map visualization.

    Args:
        cve_ids: Optional list of specific CVEs to include
        limit: Number of high-risk CVEs to fetch

    Returns:
        Heat map data with EPSS scores
    """
    client = get_epss_client()

    data_points = []

    # Get specific CVEs if provided
    if cve_ids:
        cve_list = [cve.strip() for cve in cve_ids.split(",")]
        scores = await client.get_scores_batch(cve_list)

        for cve_id, score in scores.items():
            data_points.append({
                "id": score.cve_id,
                "x": score.epss,
                "y": score.percentile,
                "value": score.epss,
                "label": score.cve_id,
                "risk_level": _get_risk_level(score.epss),
                "date": score.date
            })

    # Also get high-risk CVEs for context
    high_risk = await client.get_high_risk_cves(min_epss=0.7, limit=limit)

    for score in high_risk:
        # Avoid duplicates
        if not any(dp["id"] == score.cve_id for dp in data_points):
            data_points.append({
                "id": score.cve_id,
                "x": score.epss,
                "y": score.percentile,
                "value": score.epss,
                "label": score.cve_id,
                "risk_level": _get_risk_level(score.epss),
                "date": score.date
            })

    # Sort by EPSS score
    data_points.sort(key=lambda x: x["value"], reverse=True)

    return {
        "success": True,
        "data_points": data_points,
        "total": len(data_points),
        "metadata": {
            "x_axis": "EPSS Score (Exploitation Probability)",
            "y_axis": "Percentile Rank",
            "risk_levels": {
                "critical": {"min": 0.9, "color": "#dc2626"},
                "high": {"min": 0.7, "color": "#ea580c"},
                "medium": {"min": 0.3, "color": "#eab308"},
                "low": {"min": 0.0, "color": "#84cc16"}
            }
        }
    }


# Helper functions

def _get_risk_level(epss: float) -> str:
    """Determine risk level from EPSS score."""
    if epss >= 0.9:
        return "critical"
    elif epss >= 0.7:
        return "high"
    elif epss >= 0.3:
        return "medium"
    else:
        return "low"


def _interpret_score(epss: float, percentile: float) -> str:
    """Provide human-readable interpretation of EPSS score."""
    risk = _get_risk_level(epss)

    if risk == "critical":
        return f"CRITICAL: {epss*100:.1f}% probability of exploitation in the next 30 days. Top {(1-percentile)*100:.1f}% of all CVEs."
    elif risk == "high":
        return f"HIGH: {epss*100:.1f}% probability of exploitation in the next 30 days. Top {(1-percentile)*100:.1f}% of all CVEs."
    elif risk == "medium":
        return f"MEDIUM: {epss*100:.1f}% probability of exploitation in the next 30 days. Higher than {percentile*100:.1f}% of all CVEs."
    else:
        return f"LOW: {epss*100:.1f}% probability of exploitation in the next 30 days. Lower risk than most CVEs."
