from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .attack_surface_graph import AttackSurfaceGraph, EdgeType, NodeType

logger = logging.getLogger(__name__)

class AssetRegistry:
    """
    K1 Asset Registry with Graph-Node Support.
    Synchronizes asset discoveries with the Attack Surface DAG.
    """

    def __init__(self, graph: AttackSurfaceGraph | None = None) -> None:
        self.graph = graph or AttackSurfaceGraph()
        self._assets: Dict[str, Dict[str, Any]] = {}

    def register_asset(
        self,
        asset_id: str,
        asset_type: str,
        target_root: str,
        metadata: Dict[str, Any] | None = None
    ) -> str:
        """Registers a basic asset (FQDN, IP, etc.) and adds to Graph."""
        now = datetime.now(UTC).isoformat()
        record = {
            "id": asset_id,
            "type": asset_type,
            "target_root": target_root,
            "metadata": metadata or {},
            "registered_at": now
        }
        self._assets[asset_id] = record
        
        # Graph Integration
        self.graph.add_asset_node(asset_id, asset_type, metadata)
        
        # If target_root is different, create a relationship
        if target_root and target_root != asset_id:
            self.graph.add_asset_node(target_root, "root_domain")
            self.graph.create_edge(asset_id, target_root, EdgeType.RESOLVES_TO)
            
        return asset_id

    def register_service(
        self,
        asset_id: str,
        port: int,
        protocol: str,
        banner: str | None = None,
        version: str | None = None,
        metadata: Dict[str, Any] | None = None
    ) -> str:
        """Registers a service on an asset and links them in the Graph."""
        service_id = f"{asset_id}:{port}"
        
        service_meta = metadata or {}
        if banner: service_meta["banner"] = banner
        if version: service_meta["version"] = version
        
        # Add Service Node
        self.graph.add_service_node(service_id, port, protocol, service_meta)
        
        # Link Asset HOSTS Service
        self.graph.create_edge(asset_id, service_id, EdgeType.HOSTS)
        
        return service_id

    def map_vulnerability(self, service_id: str, cve_id: str, severity: str):
        """Links a vulnerability to a service in the Graph."""
        vuln_node_id = f"{service_id}:{cve_id}"
        self.graph.add_vulnerability_node(vuln_node_id, cve_id, severity)
        self.graph.create_edge(service_id, vuln_node_id, EdgeType.VULNERABLE_TO)

    def associate_identity(self, asset_id: str, identity_id: str, identity_type: str, value: str):
        """Links an identity (API Key, Credential) to an asset."""
        self.graph.add_identity_node(identity_id, identity_type, value)
        self.graph.create_edge(identity_id, asset_id, EdgeType.ACCESSES_WITH)

    def get_asset_summary(self) -> Dict[str, Any]:
        return {
            "total_assets": len(self._assets),
            "graph_nodes": len(self.graph._graph.nodes),
            "graph_edges": len(self.graph._graph.edges)
        }
