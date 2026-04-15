from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .attack_surface_graph import AttackSurfaceGraph, NodeType
from .experience_engine import ExperienceEngine
from .experience_memory import ExperienceMemory

logger = logging.getLogger(__name__)

class GraphRAGService:
    """
    Context-Aware Graph-RAG Service.
    Enriches vector memory queries with surrounding graph topology.
    """

    def __init__(
        self,
        graph: AttackSurfaceGraph | None = None,
        experience_engine: ExperienceEngine | None = None
    ) -> None:
        self.graph = graph or AttackSurfaceGraph()
        self.experience_engine = experience_engine or ExperienceEngine.get_instance()
        self.experience_memory = ExperienceMemory.get_instance()

    def query_with_graph_context(
        self,
        query: str,
        target_node_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieval: provide graph context (neighbors, relationships) to the vector query.
        """
        # 1. Get Graph Context
        context = self.graph.get_node_context(target_node_id, depth=2)
        
        # 2. Synthesize Graph Metadata for RAG
        # Example: "Target Nginx 1.18 is hosted on FQDN example.com, vulnerable to CVE-2021-..."
        metadata_str = self._synthesize_context_string(context)
        
        # 3. Hybrid Query
        enriched_query = f"{query} | Context: {metadata_str}"
        
        # We can use ExperienceMemory directly for deep recall or ExperienceEngine for reflex
        return self.experience_memory.query_lessons(
            target_fingerprint=self._extract_fingerprint(context),
            limit=limit
        )

    def _synthesize_context_string(self, context: Dict[str, Any]) -> str:
        nodes = context.get("subgraph_nodes", [])
        summary = []
        for node in nodes:
            ntype = node.get("node_type")
            if ntype == NodeType.SERVICE:
                summary.append(f"service={node.get('metadata', {}).get('service')} version={node.get('version')}")
            elif ntype == NodeType.VULNERABILITY:
                summary.append(f"vulnerability={node.get('cve_id')}")
        return " | ".join(summary)

    def _extract_fingerprint(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Convert graph context back to a tactical fingerprint."""
        fp = {}
        nodes = context.get("subgraph_nodes", [])
        for node in nodes:
            ntype = node.get("node_type")
            if ntype == NodeType.SERVICE:
                fp["service"] = node.get("metadata", {}).get("service")
                fp["version"] = node.get("version")
            elif ntype == NodeType.ASSET:
                if node.get("asset_type") == "waf":
                    fp["waf"] = node.get("id")
        return fp

    def get_tactical_path_recommendation(self, target_node_id: str) -> Dict[str, Any]:
        """
        Combines pathfinding with experience engine scores.
        """
        path = self.graph.calculate_golden_path(target_node_id)
        if not path:
            return {"status": "no_path_found"}
            
        recommendations = []
        for node_id in path:
            # Check if it's a vulnerability node to get exploit strategy
            node_data = self.graph._graph.nodes[node_id]
            if node_data.get("node_type") == NodeType.VULNERABILITY:
                strategy = self.experience_engine.recommend_tactical_action(
                    target_fingerprint=self._extract_fingerprint(self.graph.get_node_context(node_id)),
                    playbook_id=node_data.get("cve_id")
                )
                recommendations.append({
                    "node": node_id,
                    "cve": node_data.get("cve_id"),
                    "strategy": strategy
                })
                
        return {
            "golden_path": path,
            "tactical_steps": recommendations
        }
