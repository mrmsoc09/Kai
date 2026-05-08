"""
Kaison K1 - Intelligence API Router
RSS feed monitoring, RAG queries, and threat intelligence endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging

from ..core.intelligence_engine import get_intelligence_engine
from ..integrations.rss_parser import get_rss_parser
from ..integrations.llamaindex_rag import get_llamaindex_rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


# Pydantic Models
class RSSFeedInfo(BaseModel):
    name: str
    url: str
    description: str
    priority: int


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = 5


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    source_documents: List[Dict[str, Any]]
    relevance_scores: List[float]
    query_time: float


class FindingContextRequest(BaseModel):
    finding_id: str


class IntelligenceScanResponse(BaseModel):
    status: str
    items_found: int
    message: str


class HighPriorityCVEsResponse(BaseModel):
    cves: List[Dict[str, Any]]
    total_count: int


class IndexStatsResponse(BaseModel):
    total_documents: int
    total_nodes: int
    storage_size_mb: float
    last_updated: str


# Endpoints

@router.get("/rss/feeds", response_model=List[RSSFeedInfo])
async def get_rss_feeds():
    """Get list of all configured RSS feeds"""
    try:
        parser = get_rss_parser()
        feeds = parser.get_feed_list()

        return [
            RSSFeedInfo(
                name=feed['name'],
                url=feed['url'],
                description=feed['description'],
                priority=feed['priority']
            )
            for feed in feeds
        ]

    except Exception as e:
        logger.error(f"Error getting RSS feeds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rss/latest")
async def get_latest_intelligence(hours: int = Query(24, ge=1, le=168)):
    """Get latest intelligence from RSS feeds"""
    try:
        engine = await get_intelligence_engine()

        # Scan feeds
        items = await engine.scan_feeds()

        # Filter by time window
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_items = [
            {
                'id': item.id,
                'source': item.source,
                'title': item.title,
                'link': item.link,
                'published': item.published.isoformat(),
                'cves': item.cves,
                'max_epss_score': item.max_epss_score,
                'priority_score': item.priority_score,
                'summary': item.summary
            }
            for item in items
            if item.published >= cutoff_time
        ]

        return {
            'items': recent_items,
            'total_count': len(recent_items),
            'hours': hours
        }

    except Exception as e:
        logger.error(f"Error getting latest intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rss/scan", response_model=IntelligenceScanResponse)
async def trigger_rss_scan():
    """Trigger manual RSS feed scan"""
    try:
        engine = await get_intelligence_engine()

        # Check if scan is already running
        status = engine.get_scan_status()
        if status['is_scanning']:
            return IntelligenceScanResponse(
                status="in_progress",
                items_found=0,
                message="Scan already in progress"
            )

        # Trigger scan
        items = await engine.scan_feeds()

        return IntelligenceScanResponse(
            status="completed",
            items_found=len(items),
            message=f"Successfully scanned feeds and found {len(items)} items"
        )

    except Exception as e:
        logger.error(f"Error triggering RSS scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rss/high-priority", response_model=HighPriorityCVEsResponse)
async def get_high_priority_cves(
    min_epss: float = Query(0.7, ge=0.0, le=1.0),
    hours: int = Query(24, ge=1, le=168)
):
    """Get high-priority CVEs based on EPSS score"""
    try:
        engine = await get_intelligence_engine()

        high_priority = await engine.get_high_priority_cves(
            min_epss=min_epss,
            hours=hours
        )

        return HighPriorityCVEsResponse(
            cves=high_priority,
            total_count=len(high_priority)
        )

    except Exception as e:
        logger.error(f"Error getting high-priority CVEs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/query", response_model=RAGQueryResponse)
async def query_rag(request: RAGQueryRequest):
    """Semantic search query against RAG index"""
    try:
        rag = await get_llamaindex_rag()

        response = await rag.query(
            query_str=request.query,
            top_k=request.top_k
        )

        return RAGQueryResponse(
            query=response.query,
            answer=response.answer,
            source_documents=response.source_documents,
            relevance_scores=response.relevance_scores,
            query_time=response.query_time
        )

    except Exception as e:
        logger.error(f"Error querying RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/finding-context/{finding_id}")
async def get_finding_context(finding_id: str):
    """Get contextual analysis for a finding using RAG"""
    try:
        rag = await get_llamaindex_rag()

        context = await rag.analyze_finding_context(finding_id)

        return {
            'finding_id': finding_id,
            'context': context,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Error getting finding context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/stats", response_model=IndexStatsResponse)
async def get_rag_stats():
    """Get RAG index statistics"""
    try:
        rag = await get_llamaindex_rag()

        stats = await rag.get_stats()

        return IndexStatsResponse(
            total_documents=stats.total_documents,
            total_nodes=stats.total_nodes,
            storage_size_mb=stats.storage_size_mb,
            last_updated=stats.last_updated.isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting RAG stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/search-cves")
async def search_cves(query: str = Query(..., description="Search query for CVEs"), top_k: int = Query(10, ge=1, le=50)):
    """Semantic search for CVEs"""
    try:
        rag = await get_llamaindex_rag()

        results = await rag.search_cves(query, top_k=top_k)

        return {
            'query': query,
            'results': results,
            'total_count': len(results)
        }

    except Exception as e:
        logger.error(f"Error searching CVEs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nuclei/generate/{cve_id}")
async def generate_nuclei_template(cve_id: str):
    """Auto-generate Nuclei template for a CVE"""
    try:
        rag = await get_llamaindex_rag()

        template = await rag.generate_nuclei_template(cve_id)

        if template:
            return {
                'cve_id': cve_id,
                'template': template,
                'status': 'success'
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Could not generate template for {cve_id}. No context found."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Nuclei template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_intelligence_status():
    """Get intelligence system status"""
    try:
        engine = await get_intelligence_engine()
        scan_status = engine.get_scan_status()

        rag = await get_llamaindex_rag()
        rag_stats = await rag.get_stats()

        return {
            'scanner': scan_status,
            'rag': {
                'total_documents': rag_stats.total_documents,
                'storage_size_mb': rag_stats.storage_size_mb,
                'last_updated': rag_stats.last_updated.isoformat()
            },
            'status': 'operational'
        }

    except Exception as e:
        logger.error(f"Error getting intelligence status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Platform Intelligence — Wazuh / MISP / Cortex / TheHive / Shuffle
# ---------------------------------------------------------------------------

@router.get("/platforms/health")
async def get_platform_health():
    """
    Health check for all five intelligence platforms.
    Returns reachability status for each platform.
    """
    import asyncio
    results: Dict[str, Any] = {}

    async def _check(name: str, fn):
        try:
            healthy = await asyncio.get_event_loop().run_in_executor(None, fn)
            results[name] = {"healthy": bool(healthy), "error": None}
        except Exception as exc:
            results[name] = {"healthy": False, "error": str(exc)}

    try:
        from ..core.wazuh_client import WazuhClient
        from ..core.misp_client import MISPClient
        from ..core.cortex_client import CortexClient
        from ..core.hil_thehive_client import TheHiveClient
        from ..core.shuffle_client import ShuffleClient

        await asyncio.gather(
            _check("wazuh",   WazuhClient().health_check),
            _check("misp",    MISPClient().health_check),
            _check("cortex",  CortexClient().health_check),
            _check("thehive", TheHiveClient().health_check),
            _check("shuffle", ShuffleClient().health_check),
        )
    except Exception as exc:
        logger.error("Platform health check error: %s", exc)

    healthy_count = sum(1 for v in results.values() if v.get("healthy"))
    return {
        "platforms": results,
        "healthy_count": healthy_count,
        "total": len(results),
        "all_healthy": healthy_count == len(results),
    }


@router.get("/platforms/wazuh/alerts")
async def get_wazuh_alerts(hours: int = Query(1, ge=1, le=24)):
    """Recent Wazuh host alerts from the last N hours."""
    import asyncio
    try:
        from ..core.wazuh_client import WazuhClient
        client = WazuhClient()
        loop = asyncio.get_event_loop()
        alerts = await loop.run_in_executor(
            None, lambda: client.get_recent_alerts(hours=hours, level_min=5)
        )
        anomaly = await loop.run_in_executor(None, client.check_host_anomalies)
        return {"alerts": alerts[:50], "alert_count": len(alerts), "anomaly_summary": anomaly}
    except Exception as exc:
        logger.error("Wazuh alerts error: %s", exc)
        return {"alerts": [], "alert_count": 0, "anomaly_summary": {}, "error": str(exc)}


@router.post("/platforms/misp/enrich")
async def misp_enrich_ioc(body: Dict[str, Any]):
    """
    Enrich an IOC against MISP.
    Body: {"ioc_type": "ip|domain|url|hash", "value": "..."}
    """
    import asyncio
    ioc_type = body.get("ioc_type", "domain")
    value = body.get("value", "")
    if not value:
        raise HTTPException(status_code=400, detail="value is required")
    try:
        from ..core.misp_client import MISPClient
        client = MISPClient()
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: client.enrich_ioc(ioc_type=ioc_type, ioc_value=value)
        )
        return result
    except Exception as exc:
        logger.error("MISP enrich error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/platforms/misp/events")
async def get_misp_recent_events(limit: int = Query(10, ge=1, le=50)):
    """Fetch recent MISP threat events."""
    import asyncio
    try:
        from ..core.misp_client import MISPClient
        client = MISPClient()
        events = await asyncio.get_event_loop().run_in_executor(
            None, lambda: client.search_events(limit=limit)
        )
        return {"events": events, "count": len(events)}
    except Exception as exc:
        logger.error("MISP events error: %s", exc)
        return {"events": [], "count": 0, "error": str(exc)}


@router.get("/platforms/cortex/analyzers")
async def get_cortex_analyzers():
    """List available Cortex analyzers."""
    import asyncio
    try:
        from ..core.cortex_client import CortexClient
        client = CortexClient()
        analyzers = await asyncio.get_event_loop().run_in_executor(
            None, client.list_analyzers
        )
        return {"analyzers": analyzers, "count": len(analyzers)}
    except Exception as exc:
        logger.error("Cortex analyzers error: %s", exc)
        return {"analyzers": [], "count": 0, "error": str(exc)}


@router.get("/platforms/thehive/cases")
async def get_thehive_cases(limit: int = Query(20, ge=1, le=100)):
    """Fetch recent TheHive cases."""
    import asyncio
    try:
        from ..core.hil_thehive_client import TheHiveClient
        client = TheHiveClient()

        def _fetch():
            url = f"{client.base_url}/api/v1/case"
            resp = client.session.get(url, params={"max": limit}, timeout=15)
            if resp.status_code < 400:
                return resp.json()
            return []

        cases = await asyncio.get_event_loop().run_in_executor(None, _fetch)
        return {"cases": cases if isinstance(cases, list) else [], "count": len(cases) if isinstance(cases, list) else 0}
    except Exception as exc:
        logger.error("TheHive cases error: %s", exc)
        return {"cases": [], "count": 0, "error": str(exc)}
