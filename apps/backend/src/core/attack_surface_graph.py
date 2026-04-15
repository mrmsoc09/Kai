from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import networkx as nx
from pydantic import BaseModel, Field

from .praison_execution_events import MissionEvent, get_event_bus

logger = logging.getLogger(__name__)

class NodeType(str, Enum):
    ASSET = "asset"
    SERVICE = "service"
    VULNERABILITY = "vulnerability"
    IDENTITY = "identity"

class EdgeType(str, Enum):
    RESOLVES_TO = "RESOLVES_TO"
    HOSTS = "HOSTS"
    VULNERABLE_TO = "VULNERABLE_TO"
    ACCESSES_WITH = "ACCESSES_WITH"

class AttackSurfaceGraph:
    """
    K1 Attack Surface Graph (DAG).
    Implemented using NetworkX for high-performance in-memory analysis.
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()
        self._lock = threading.RLock()

    def add_asset_node(self, node_id: str, asset_type: str, metadata: Dict[str, Any] | None = None) -> str:
        with self._lock:
            self._graph.add_node(
                node_id,
                node_type=NodeType.ASSET,
                asset_type=asset_type,
                metadata=metadata or {},
                observed_at=datetime.now(UTC).isoformat()
            )
            return node_id

    def add_service_node(self, node_id: str, port: int, protocol: str, metadata: Dict[str, Any] | None = None) -> str:
        with self._lock:
            self._graph.add_node(
                node_id,
                node_type=NodeType.SERVICE,
                port=port,
                protocol=protocol,
                metadata=metadata or {},
                observed_at=datetime.now(UTC).isoformat()
            )
            return node_id

    def add_vulnerability_node(self, node_id: str, cve_id: str, severity: str, metadata: Dict[str, Any] | None = None) -> str:
        with self._lock:
            self._graph.add_node(
                node_id,
                node_type=NodeType.VULNERABILITY,
                cve_id=cve_id,
                severity=severity,
                exploit_status="potential",
                metadata=metadata or {},
                observed_at=datetime.now(UTC).isoformat()
            )
            return node_id

    def add_identity_node(self, node_id: str, identity_type: str, value: str, metadata: Dict[str, Any] | None = None) -> str:
        with self._lock:
            self._graph.add_node(
                node_id,
                node_type=NodeType.IDENTITY,
                identity_type=identity_type,
                value=value,
                metadata=metadata or {},
                observed_at=datetime.now(UTC).isoformat()
            )
            return node_id

    def create_edge(self, source_id: str, target_id: str, edge_type: EdgeType, weight: float = 1.0, metadata: Dict[str, Any] | None = None):
        with self._lock:
            if not self._graph.has_node(source_id) or not self._graph.has_node(target_id):
                logger.warning(f"Failed to create edge: one or both nodes missing ({source_id} -> {target_id})")
                return

            self._graph.add_edge(
                source_id,
                target_id,
                edge_type=edge_type,
                weight=weight,
                metadata=metadata or {}
            )
            
            # Emit V-RAD Telemetry
            self._emit_vrad_link(source_id, target_id, edge_type)

    def _emit_vrad_link(self, source: str, target: str, edge_type: EdgeType):
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="GRAPH_LINK_CREATED",
                    phase="attack_surface_graph",
                    detail={
                        "source": source,
                        "target": target,
                        "edge_type": edge_type.value,
                        "v-rad_visual": "DYNAMIC_LINKING_LINE"
                    }
                )
            )
        except Exception:
            pass

    def get_node_context(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """Returns the surrounding graph context for a specific node."""
        with self._lock:
            if not self._graph.has_node(node_id):
                return {}
            
            # Use ego_graph to get neighbors up to depth
            ego = nx.ego_graph(self._graph, node_id, radius=depth, center=True, undirected=False)
            
            nodes = []
            for n, d in ego.nodes(data=True):
                nodes.append({"id": n, **d})
                
            edges = []
            for u, v, d in ego.edges(data=True):
                edges.append({"source": u, "target": v, **d})
                
            return {
                "root_node": node_id,
                "subgraph_nodes": nodes,
                "subgraph_edges": edges
            }

    def calculate_golden_path(self, target_node_id: str) -> List[str]:
        """
        Pathfinding: identify shortest sequence of nodes to reach a critical asset.
        Uses Dijkstra's based on edge weights (lower weight = easier path).
        """
        with self._lock:
            # Find entry points (nodes with in_degree 0)
            entry_points = [n for n, d in self._graph.in_degree() if d == 0]
            
            best_path = []
            min_length = float('inf')
            
            for start in entry_points:
                try:
                    path = nx.shortest_path(self._graph, source=start, target=target_node_id, weight='weight')
                    if len(path) < min_length:
                        min_length = len(path)
                        best_path = path
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
            
            if best_path:
                self._emit_golden_path(best_path)
                
            return best_path

    def _emit_golden_path(self, path: List[str]):
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="GOLDEN_PATH_HIGHLIGHTED",
                    phase="attack_surface_graph",
                    detail={
                        "path": path,
                        "color": "GOLD",
                        "v-rad_visual": "PATH_HIGHLIGHTING"
                    }
                )
            )
        except Exception:
            pass

    def mark_node_hard_blocked(
        self,
        node_id: str,
        *,
        playbook_id: str,
        reason: str,
        attempts: int,
    ) -> bool:
        """
        Mark a node as hard blocked after reflection retries are exhausted.
        """
        with self._lock:
            if not self._graph.has_node(node_id):
                return False
            metadata = dict(self._graph.nodes[node_id].get("metadata") or {})
            metadata["hard_blocked"] = True
            metadata["hard_block_reason"] = reason
            metadata["hard_block_playbook"] = playbook_id
            metadata["hard_block_attempts"] = attempts
            self._graph.nodes[node_id]["metadata"] = metadata
            self._graph.nodes[node_id]["block_state"] = "HARD_BLOCKED"
            self._graph.nodes[node_id]["blocked_at"] = datetime.now(UTC).isoformat()

        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="NODE_HARD_BLOCKED",
                    phase="attack_surface_graph",
                    node_id=node_id,
                    detail={
                        "playbook_id": playbook_id,
                        "reason": reason,
                        "attempts": attempts,
                        "v-rad_visual": "AMBER_LOCK",
                    },
                )
            )
        except Exception:
            pass
        return True
