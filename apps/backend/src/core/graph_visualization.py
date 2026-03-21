"""
Graph Visualization for K1 Missions
====================================
Utilities for exporting LangGraph structure and current mission state
for visualization in the Operator Interface.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from apps.backend.src.core.praison_mission_runtime import get_mission_runtime
from apps.backend.src.core.praison_topology import MissionGraphSpec

logger = logging.getLogger(__name__)


def export_graph_structure(mission_id: str, tenant_id: UUID) -> dict[str, Any]:
    """
    Export the graph structure and current state for a mission.
    
    Returns:
      - nodes: list of node definitions
      - edges: list of edge definitions
      - node_state: current status/state of each node
      - phase: current mission phase
      - execution_status: overall mission lifecycle status
    """
    runtime = get_mission_runtime()
    try:
        status = runtime.get_status(mission_id, tenant_id=tenant_id)
        inspect = runtime.inspect_state(mission_id, tenant_id=tenant_id)
    except ValueError as exc:
        logger.error("Failed to get mission %s for graph export: %s", mission_id, exc)
        return {"error": str(exc)}

    # Get the graph spec from the handle (accessible via inspect or internal)
    # MissionRuntime._missions is internal, but we can get it from the handle if we had it.
    # For now, let's assume we can get the graph spec from the handle.
    handle = runtime._missions.get((tenant_id, mission_id))
    if not handle:
        return {"error": "Mission handle not found"}
    
    graph_spec: MissionGraphSpec = handle.graph_spec
    state = runtime.get_state(mission_id)
    
    # 1. Nodes
    nodes = []
    for node_id, node_spec in graph_spec.nodes.items():
        nodes.append({
            "id": node_id,
            "label": node_id,
            "type": node_spec.node_type,
            "agent_class": node_spec.agent_class,
            "cluster_id": node_spec.cluster_id,
        })
    
    # 2. Edges
    edges = []
    for edge in graph_spec.edges:
        edges.append({
            "id": edge.edge_id,
            "source": edge.source,
            "target": edge.target,
            "condition": edge.condition,
            "label": edge.label,
        })
    
    # 3. Node State (execution status per node)
    node_history = state.get("node_history", [])
    active_node = status.active_node
    
    node_state = {}
    for node_id in graph_spec.nodes:
        if node_id == active_node:
            status_val = "running"
        elif any(h.get("node_id") == node_id for h in node_history):
            status_val = "completed"
        else:
            status_val = "pending"
        
        node_state[node_id] = {
            "status": status_val,
            "last_executed": next((h.get("timestamp") for h in reversed(node_history) if h.get("node_id") == node_id), None)
        }

    return {
        "mission_id": mission_id,
        "workflow_id": status.workflow_id,
        "program_id": status.program_id,
        "phase": status.phase,
        "execution_status": status.state,
        "nodes": nodes,
        "edges": edges,
        "node_state": node_state,
        "progress": status.progress,
        "error": status.error,
    }
