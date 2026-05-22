"""
Kaison K1 - Graph Database API Router
Attack surface visualization and relationship analysis
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging

from ..integrations.neo4j_client import get_neo4j_client
from ..core.auth import require_roles, ROLE_OPERATOR, ROLE_ANALYST

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/graph",
    tags=["graph"],
    dependencies=[Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST))],
)


# Pydantic Models
class CreateTargetRequest(BaseModel):
    target: str
    target_type: str = "domain"


class LinkFindingRequest(BaseModel):
    target: str
    vulnerability_type: str
    cvss: float
    severity: str
    description: str = ""
    tool: str = ""
    cve_ids: List[str] = []


class SubdomainRelationshipRequest(BaseModel):
    parent: str
    subdomain: str


class AttackSurfaceResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    stats: Dict[str, int]


class VulnerabilityPathsResponse(BaseModel):
    paths: List[Dict[str, Any]]
    total_count: int


class CVERelationshipsResponse(BaseModel):
    cve: Optional[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    targets: List[Dict[str, Any]]
    stats: Dict[str, int]


class GraphStatsResponse(BaseModel):
    targets: int
    findings: int
    cves: int
    domains: int
    relationships: int


# Endpoints

@router.post("/targets")
async def create_target_node(request: CreateTargetRequest):
    """Create target node in graph"""
    try:
        client = await get_neo4j_client()

        await client.create_target_node(
            target=request.target,
            target_type=request.target_type
        )

        return {
            'status': 'success',
            'message': f'Target node created: {request.target}'
        }

    except Exception as e:
        logger.error(f"Error creating target node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/findings/{finding_id}/link")
async def link_finding_to_target(finding_id: str, request: LinkFindingRequest):
    """Link finding to target in graph"""
    try:
        client = await get_neo4j_client()

        # Create target if it doesn't exist
        await client.create_target_node(target=request.target)

        # Create finding relationship
        await client.create_finding_relationship(
            target=request.target,
            finding_id=finding_id,
            vulnerability_type=request.vulnerability_type,
            cvss=request.cvss,
            severity=request.severity,
            description=request.description,
            tool=request.tool
        )

        # Link CVEs if present
        for cve_id in request.cve_ids:
            await client.link_cve_to_finding(
                finding_id=finding_id,
                cve_id=cve_id
            )

        return {
            'status': 'success',
            'message': f'Finding {finding_id} linked to target {request.target}'
        }

    except Exception as e:
        logger.error(f"Error linking finding to target: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subdomains")
async def create_subdomain_relationship(request: SubdomainRelationshipRequest):
    """Create subdomain relationship in graph"""
    try:
        client = await get_neo4j_client()

        await client.create_subdomain_relationship(
            parent=request.parent,
            subdomain=request.subdomain
        )

        return {
            'status': 'success',
            'message': f'Subdomain relationship created: {request.parent} -> {request.subdomain}'
        }

    except Exception as e:
        logger.error(f"Error creating subdomain relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attack-surface/{target}", response_model=AttackSurfaceResponse)
async def get_attack_surface(target: str):
    """Get full attack surface for target"""
    try:
        client = await get_neo4j_client()

        attack_surface = await client.query_attack_surface(target)

        return AttackSurfaceResponse(
            nodes=attack_surface['nodes'],
            edges=attack_surface['edges'],
            stats=attack_surface['stats']
        )

    except Exception as e:
        logger.error(f"Error getting attack surface: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vulnerability-paths/{target}", response_model=VulnerabilityPathsResponse)
async def get_vulnerability_paths(
    target: str,
    min_severity: float = Query(7.0, ge=0.0, le=10.0)
):
    """Find vulnerability attack chains for target"""
    try:
        client = await get_neo4j_client()

        paths = await client.get_vulnerability_paths(
            target=target,
            min_severity=min_severity
        )

        return VulnerabilityPathsResponse(
            paths=paths,
            total_count=len(paths)
        )

    except Exception as e:
        logger.error(f"Error getting vulnerability paths: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cve/{cve_id}/relationships", response_model=CVERelationshipsResponse)
async def get_cve_relationships(cve_id: str):
    """Find related CVEs and affected targets"""
    try:
        client = await get_neo4j_client()

        relationships = await client.get_cve_relationships(cve_id)

        return CVERelationshipsResponse(
            cve=relationships['cve'],
            findings=relationships['findings'],
            targets=relationships['targets'],
            stats=relationships['stats']
        )

    except Exception as e:
        logger.error(f"Error getting CVE relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-import")
async def bulk_import_findings(findings: List[Dict[str, Any]]):
    """Bulk import findings into graph"""
    try:
        client = await get_neo4j_client()

        await client.bulk_import_findings(findings)

        return {
            'status': 'success',
            'message': f'Bulk imported {len(findings)} findings',
            'imported_count': len(findings)
        }

    except Exception as e:
        logger.error(f"Error bulk importing findings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats():
    """Get graph database statistics"""
    try:
        client = await get_neo4j_client()

        stats = await client.get_graph_stats()

        return GraphStatsResponse(
            targets=stats['targets'],
            findings=stats['findings'],
            cves=stats['cves'],
            domains=stats['domains'],
            relationships=stats['relationships']
        )

    except Exception as e:
        logger.error(f"Error getting graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_graph_status():
    """Check graph database connection status"""
    try:
        client = await get_neo4j_client()
        stats = await client.get_graph_stats()

        return {
            'status': 'connected',
            'uri': client.uri,
            'stats': stats
        }

    except RuntimeError as e:
        return {
            'status': 'not_initialized',
            'message': str(e)
        }
    except Exception as e:
        logger.error(f"Error checking graph status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
