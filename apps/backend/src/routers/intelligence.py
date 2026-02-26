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
