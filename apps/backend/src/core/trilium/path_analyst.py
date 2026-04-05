from __future__ import annotations

import logging
import json
from typing import Any, Dict, List, Optional
import re

from apps.backend.src.core.trilium.client import TriliumClient
from apps.backend.src.core.trilium.query import OrchestrationQueryLayer
from apps.backend.src.core.trilium.relational import SpiderWebEngine

logger = logging.getLogger(__name__)

class PathAnalyst:
    """
    K1 Path Analyst (Stage 14).
    Maps the 'Blast Radius' of a verified vulnerability using non-destructive observation.
    Generates Mermaid.js visualizations and calculates Impact Scores.
    """

    def __init__(self, trilium_client: TriliumClient, query_layer: OrchestrationQueryLayer, relational_engine: SpiderWebEngine):
        self.trilium = trilium_client
        self.query_layer = query_layer
        self.relational_engine = relational_engine

    async def analyze_blast_radius(self, verified_poc_note_id: str) -> Dict[str, Any]:
        """
        Identifies potential pivots and calculates impact score for a verified exploit.
        """
        logger.info(f"PathAnalyst: Analyzing blast radius for verified PoC note: {verified_poc_note_id}")

        # 1. Retrieve the verified PoC note and its context
        poc_context = await self.query_layer.get_target_context(verified_poc_note_id)
        if not poc_context:
            logger.error(f"PathAnalyst: Could not retrieve context for {verified_poc_note_id}")
            return {}

        initial_target = poc_context.get("labels", {}).get("target", poc_context.get("title", "unknown_target"))
        logger.info(f"PathAnalyst: Initial verified target: {initial_target}")

        # 2. Relational Inference: Identify Pivots
        # Query Trilium for all assets related to the initial target.
        # This involves traversing relations like 'subdomain_of', 'resolves_to', 'identifies_as',
        # and looking for shared attributes like #subnet, #ssh_key, #api_token.
        # For this implementation, we simulate querying the spider web.
        potential_pivots: List[Dict[str, str]] = []
        
        # Simulate finding pivot notes
        # In a real system, this would involve extensive querying through the relational_engine
        # Example: notes related by 'shared_subnet', 'same_ssh_key_used', 'same_api_token_used_on'
        # For now, let's create some simulated pivots based on the initial target
        if "example.com" in initial_target:
            potential_pivots.extend([
                {"noteId": "pivot_subnet_123", "title": "Shared Subnet 192.168.1.0/24", "type": "subnet", "relation": "shared_network"},
                {"noteId": "pivot_key_456", "title": "Staging SSH Key", "type": "ssh_key", "relation": "shared_credential"},
                {"noteId": "pivot_api_789", "title": "Internal Admin API", "type": "api_endpoint", "relation": "internal_access"},
            ])
        
        logger.info(f"PathAnalyst: Identified {len(potential_pivots)} potential pivots.")

        # 3. Non-Destructive Observation: Predict Lateral Movement
        # For each pivot, query what other high-value targets are reachable.
        # This is a PREDICTIVE step based on known data, not active probing.
        lateral_movement_predictions: List[Dict[str, Any]] = []

        for pivot in potential_pivots:
            # Simulate querying the context of the pivot for reachable high-value targets
            # This would involve query_layer.search_intelligence or similar
            if pivot["type"] == "subnet":
                lateral_movement_predictions.append({
                    "from": pivot["title"],
                    "to": "Internal HR Database (High Value)",
                    "path": "network_access"
                })
            elif pivot["type"] == "ssh_key":
                lateral_movement_predictions.append({
                    "from": pivot["title"],
                    "to": "Production Web Server (High Value)",
                    "path": "ssh_access"
                })
            
        logger.info(f"PathAnalyst: Predicted {len(lateral_movement_predictions)} lateral movement paths.")

        # 4. Visualization: Generate Mermaid.js code
        mermaid_code = self._generate_mermaid_graph(
            initial_target=initial_target,
            verified_exploit_id=verified_poc_note_id,
            pivots=potential_pivots,
            lateral_movements=lateral_movement_predictions
        )

        # 5. Impact Scoring: Calculate 'Bounty Multiplier'
        bounty_multiplier = self._calculate_bounty_multiplier(
            initial_target=initial_target,
            pivots=potential_pivots,
            lateral_movements=lateral_movement_predictions
        )
        
        logger.info(f"PathAnalyst: Calculated Bounty Multiplier: {bounty_multiplier}")

        return {
            "initial_target": initial_target,
            "potential_pivots": potential_pivots,
            "lateral_movement_predictions": lateral_movement_predictions,
            "mermaid_graph": mermaid_code,
            "bounty_multiplier": bounty_multiplier,
            "status": "blast_radius_mapped"
        }

    def _generate_mermaid_graph(
        self, 
        initial_target: str, 
        verified_exploit_id: str, 
        pivots: List[Dict[str, str]], 
        lateral_movements: List[Dict[str, Any]]
    ) -> str:
        """Generates Mermaid.js graph code for visualization."""
        graph_elements = []
        
        # Entry Point
        graph_elements.append(f"graph TD")
        graph_elements.append(f"    A[{initial_target}]:::entry")
        
        # Verified Exploit
        graph_elements.append(f"    B[Verified Exploit ({verified_exploit_id[:8]})]:::exploit")
        graph_elements.append(f"    A --> B")

        # Pivots
        pivot_nodes = {}
        for i, pivot in enumerate(pivots):
            node_id = f"P{i}"
            pivot_nodes[pivot["noteId"]] = node_id
            graph_elements.append(f"    {node_id}[{pivot['title']}]:::pivot")
            graph_elements.append(f"    B --> {node_id}")

        # High-Value Targets
        hvt_counter = 0
        for move in lateral_movements:
            from_node = next((node_id for pid, node_id in pivot_nodes.items() if move["from"] in pivot[
... [TRUNCATED] ...
hvt_node_id}({move['to']})
            graph_elements.append(f"    {from_node} --> {hvt_node_id}")

        # Styling
        graph_elements.append(f"classDef entry fill:#f87171,stroke:#dc2626,stroke-width:2px,color:#fff;")
        graph_elements.append(f"classDef exploit fill:#facc15,stroke:#eab308,stroke-width:2px,color:#000;")
        graph_elements.append(f"classDef pivot fill:#a1a1aa,stroke:#71717a,stroke-width:2px,color:#fff;")
        graph_elements.append(f"classDef hvt fill:#fbbf24,stroke:#f59e0b,stroke-width:2px,color:#000;") # Gold

        return "
".join(graph_elements)

    def _calculate_bounty_multiplier(
        self, 
        initial_target: str, 
        pivots: List[Dict[str, str]], 
        lateral_movements: List[Dict[str, Any]]
    ) -> float:
        """
        Calculates a 'Bounty Multiplier' based on the reachability of high-value targets.
        This is a heuristic.
        """
        base_bounty = 1.0
        if not pivots and not lateral_movements:
            return base_bounty # No lateral movement potential

        # Factors:
        # 1. Number of unique pivots
        # 2. Number of unique high-value targets reachable
        # 3. Criticality of paths (e.g., SSH access > network access)
        
        unique_pivots = len(set(p["noteId"] for p in pivots))
        unique_hvts = len(set(m["to"] for m in lateral_movements))
        
        multiplier = base_bounty + (unique_pivots * 0.5) + (unique_hvts * 1.0)
        
        for move in lateral_movements:
            if "ssh_access" in move["path"] or "db_access" in move["path"]:
                multiplier += 1.5 # Critical path
            elif "network_access" in move["path"]:
                multiplier += 0.5 # Basic network access
        
        return round(multiplier, 2)
