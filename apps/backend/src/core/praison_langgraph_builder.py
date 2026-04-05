"""
Praison LangGraph Builder (Phase 4 / 4.5)
============================================
Compiles a MissionGraphSpec into an executable LangGraph StateGraph.

This module bridges the structural topology layer (praison_topology.py)
with LangGraph's compilation model. It is the ONLY place where LangGraph
objects are instantiated -- all other modules work with spec dicts or
NodeSpec/EdgeSpec objects.

LangGraph is an optional dependency. If not installed, this module
degrades gracefully and the builder returns None with a clear log message.
To enable: pip install langgraph langgraph-checkpoint-postgres

Phase 4 additions:
  - Full mission graph compilation with all standard node types
  - Governance admission → mission director → phase clusters → review → report → handoff
  - Interrupt configuration for governance and review nodes
  - Checkpoint/resume support via thread_id configuration
  - Scaffold spec includes execution_order for fallback path

Phase 4.5 additions:
  - Subgraph compilation for phase clusters
  - Cluster subgraph nodes with shared state propagation
  - Subgraph scaffold specs for cluster-level inspection

What this builder does:
  1. Creates a typed state schema from K1GraphState
  2. Adds all nodes to the StateGraph (bound to wrapped executors)
  3. Wires conditional edges from EdgeSpec routing rules
  4. Configures interrupt_before / interrupt_after for HIL stops
  5. Attaches a PostgreSQL checkpointer for workflow persistence
  6. Compiles and returns the runnable CompiledGraph
  7. (Optional) Compiles phase clusters as LangGraph subgraphs

What this builder does NOT do:
  - Execute the graph (MissionRuntime does that)
  - Make LLM calls (agents do that during execution)
  - Modify agent identities or contracts
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable
from collections import defaultdict

from apps.backend.src.core.praison_topology import (
    ClusterSpec,
    MissionGraphSpec,
    NodeSpec,
    EdgeCondition,
)

logger = logging.getLogger(__name__)

# -- LangGraph availability check ----------------------------------------------
try:
    from langgraph.graph import StateGraph, END, START  # type: ignore[import]
    from langgraph.checkpoint.memory import MemorySaver  # type: ignore[import]
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    logger.info(
        "langgraph not installed -- PraisonLangGraphBuilder will return scaffold specs only. "
        "Install with: pip install langgraph langgraph-checkpoint-postgres"
    )

# PostgreSQL checkpointer (optional -- falls back to MemorySaver)
try:
    from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import]
    _POSTGRES_CHECKPOINTER_AVAILABLE = True
except ImportError:
    _POSTGRES_CHECKPOINTER_AVAILABLE = False

# -- Typed state schema (Phase 3.5 fix, Phase 4 extension) --------------------
# LANGGRAPH STATE FIX: replacing the previous StateGraph(dict) which caused every
# node output to replace the state dict rather than merging into it.
from apps.backend.src.core.praison_state import K1GraphState  # noqa: E402


# -- Condition router factories ------------------------------------------------

def _make_condition_router(
    outgoing_edges: list[Any],  # list of EdgeSpec
) -> Callable[[dict[str, Any]], str]:
    """
    Build a router function for LangGraph conditional_edge dispatch.
    Returns the node_id to route to based on current graph state.
    Exit nodes are handled by explicit terminal edges, not substitution here.
    """
    _end = END if _LANGGRAPH_AVAILABLE else "__end__"

    def router(state: dict[str, Any]) -> str:
        for edge in outgoing_edges:
            cond = edge.condition
            if cond == EdgeCondition.ALWAYS:
                return edge.target
            if cond == EdgeCondition.ON_SUCCESS and not state.get("error"):
                return edge.target
            if cond == EdgeCondition.ON_FAILURE and state.get("error"):
                return edge.target
            if cond == EdgeCondition.ON_APPROVAL and state.get("governance_decision") == "approved":
                return edge.target
            if cond == EdgeCondition.ON_REJECTION and state.get("governance_decision") == "blocked":
                return edge.target
            if cond == EdgeCondition.ON_ARTIFACT:
                last_type = state.get("last_artifact_type", "")
                if edge.artifact_type and last_type == edge.artifact_type:
                    return edge.target
            if cond == EdgeCondition.ON_HIGH_SIGNAL:
                artifacts = state.get("artifacts", [])
                high_signals = [
                    a for a in artifacts
                    if a.get("artifact_type") == "vulnerability_signal"
                    and a.get("confidence") in ("high", "medium")
                ]
                if high_signals:
                    return edge.target
            if cond == EdgeCondition.ON_LOW_SIGNAL:
                artifacts = state.get("artifacts", [])
                high_signals = [
                    a for a in artifacts
                    if a.get("artifact_type") == "vulnerability_signal"
                    and a.get("confidence") in ("high", "medium")
                ]
                if not high_signals:
                    return edge.target
            if cond == EdgeCondition.ON_PHASE_COMPLETE:
                if state.get("phase_complete"):
                    return edge.target
        # Default: end
        return _end

    return router


def _fanout_sources(graph_spec: MissionGraphSpec) -> list[str]:
    """
    Return node_ids that have multi-edge fan-out.

    K1GraphState contains many scalar last-write-wins fields; concurrent branch
    execution on fan-out nodes can yield invalid concurrent updates or silent
    branch loss when reduced to single-target routing. For now, fan-out graphs
    should run via MissionRuntime fallback execution for deterministic behavior.
    """
    outgoing: dict[str, list[Any]] = defaultdict(list)
    for edge in graph_spec.edges:
        if edge.source in graph_spec.nodes and edge.target in graph_spec.nodes:
            outgoing[edge.source].append(edge)
    return sorted([source for source, edges in outgoing.items() if len(edges) > 1])


# -- PraisonLangGraphBuilder ---------------------------------------------------

class PraisonLangGraphBuilder:
    """
    Compiles a MissionGraphSpec into an executable LangGraph graph.

    Usage:
        builder = PraisonLangGraphBuilder(graph_spec, node_callables)
        compiled = builder.compile(checkpointer_dsn="postgresql://...")
        # compiled is a langgraph CompiledGraph -- call compiled.invoke(state)
    """

    def __init__(
        self,
        graph_spec: MissionGraphSpec,
        node_callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    ) -> None:
        """
        graph_spec: The MissionGraphSpec defining topology
        node_callables: {node_id: callable(state) -> state_update_dict}
          Each callable is the agent's execution function -- typically a wrapper
          from praison_node_executors.py
        """
        self._spec = graph_spec
        self._callables = node_callables

    def build_scaffold_spec(self) -> dict[str, Any]:
        """
        Return a complete scaffold specification dict even when LangGraph
        is not installed. Used for serialization, testing, API inspection,
        and fallback execution ordering.
        """
        execution_order = _resolve_execution_order(self._spec)
        return {
            "graph_id":     self._spec.graph_id,
            "workflow_id":  self._spec.workflow_id,
            "program_id":   self._spec.program_id,
            "nodes":        [n.to_dict() for n in self._spec.nodes.values()],
            "edges":        [e.to_dict() for e in self._spec.edges],
            "clusters":     [c.to_dict() for c in self._spec.clusters.values()],
            "entry_node":   self._spec.entry_node,
            "exit_node":    self._spec.exit_node,
            "execution_order": execution_order,
            "interrupt_before": [
                n.node_id for n in self._spec.nodes_requiring_interrupt()
                if n.interrupt_before
            ],
            "interrupt_after": [
                n.node_id for n in self._spec.nodes_requiring_interrupt()
                if n.interrupt_after
            ],
            "langgraph_available": _LANGGRAPH_AVAILABLE,
        }

    def compile(self, checkpointer_dsn: str | None = None) -> Any:
        """
        Compile the graph spec into an executable LangGraph CompiledGraph.

        Returns None if LangGraph is not installed.
        checkpointer_dsn: PostgreSQL DSN for persistent checkpointing.
          Falls back to MemorySaver if None or postgres not available.
        """
        if not _LANGGRAPH_AVAILABLE:
            logger.warning(
                "LangGraph not installed -- returning scaffold spec only. "
                "graph_id=%s", self._spec.graph_id
            )
            return None

        fanout_nodes = _fanout_sources(self._spec)
        if fanout_nodes:
            logger.warning(
                "LangGraph compile fallback engaged for graph_id=%s; "
                "multi-edge fan-out nodes=%s. "
                "Using MissionRuntime fallback execution for deterministic parity.",
                self._spec.graph_id,
                fanout_nodes,
            )
            return None

        try:
            return self._compile_graph(checkpointer_dsn)
        except Exception as exc:
            logger.error("LangGraph compilation failed: %s", exc, exc_info=True)
            raise

    def _compile_graph(self, checkpointer_dsn: str | None) -> Any:
        """Internal compilation -- only called when LangGraph is available."""
        # LANGGRAPH STATE FIX (Phase 3.5):
        # Use K1GraphState (TypedDict with Annotated reducer fields) instead of
        # bare dict. This ensures accumulative fields (messages, artifacts, etc.)
        # are appended across nodes rather than replaced.
        graph = StateGraph(K1GraphState)

        # Register nodes
        interrupt_before_nodes: list[str] = []
        interrupt_after_nodes: list[str] = []

        for node_id, node_spec in self._spec.nodes.items():
            if node_id not in self._callables:
                logger.warning("No callable registered for node %s -- skipping", node_id)
                continue
            graph.add_node(node_id, self._callables[node_id])
            if node_spec.interrupt_before:
                interrupt_before_nodes.append(node_id)
            if node_spec.interrupt_after:
                interrupt_after_nodes.append(node_id)

        # Wire edges
        # Group outgoing edges by source node for conditional routing
        outgoing: dict[str, list] = defaultdict(list)
        for edge in self._spec.edges:
            outgoing[edge.source].append(edge)

        for source_id, edges in outgoing.items():
            if source_id not in self._spec.nodes:
                continue
            # Check if all edges from this node are unconditional
            all_unconditional = all(e.condition == EdgeCondition.ALWAYS for e in edges)
            if all_unconditional and len(edges) == 1:
                graph.add_edge(source_id, edges[0].target)
            else:
                # Build conditional router; no exit_node substitution here —
                # exit_node runs normally and we add a terminal edge below.
                router = _make_condition_router(edges)
                possible_targets = [e.target for e in edges]
                # Always allow the router's fallback path to END (handles unmatched conditions)
                if END not in possible_targets:
                    possible_targets.append(END)
                graph.add_conditional_edges(source_id, router, possible_targets)

        # Explicit terminal edge: exit_node → END so it runs as a real node
        # then terminates the graph cleanly (only add if it has no outgoing edges).
        if self._spec.exit_node and self._spec.exit_node in self._spec.nodes:
            if not outgoing.get(self._spec.exit_node):
                graph.add_edge(self._spec.exit_node, END)

        # Set entry point
        if self._spec.entry_node:
            graph.set_entry_point(self._spec.entry_node)

        # Attach checkpointer
        checkpointer = self._build_checkpointer(checkpointer_dsn)

        # Compile with interrupt configuration
        compiled = graph.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_before_nodes or None,
            interrupt_after=interrupt_after_nodes or None,
        )

        logger.info(
            "LangGraph compiled: graph_id=%s nodes=%d edges=%d interrupt_before=%s",
            self._spec.graph_id,
            len(self._spec.nodes),
            len(self._spec.edges),
            interrupt_before_nodes,
        )
        return compiled

    def _build_checkpointer(self, dsn: str | None) -> Any:
        """Build checkpointer -- PostgreSQL if available, MemorySaver otherwise."""
        if dsn and _POSTGRES_CHECKPOINTER_AVAILABLE:
            try:
                checkpointer = PostgresSaver.from_conn_string(dsn)
                checkpointer.setup()
                logger.info("Using PostgreSQL checkpointer: %s", dsn[:30] + "...")
                return checkpointer
            except Exception as exc:
                logger.warning("PostgreSQL checkpointer failed, falling back to MemorySaver: %s", exc)

        logger.info("Using in-memory checkpointer (MemorySaver)")
        return MemorySaver()

    # -- Subgraph compilation (Phase 4.5) --------------------------------------

    def compile_cluster_subgraph(
        self,
        cluster: ClusterSpec,
        checkpointer_dsn: str | None = None,
    ) -> Any:
        """
        Compile a phase cluster as a LangGraph subgraph.

        Returns a compiled subgraph that can be embedded as a node in the
        parent mission graph. State propagation is automatic through
        LangGraph's subgraph mechanism.

        Returns None if LangGraph is not available or cluster has no nodes.
        """
        if not _LANGGRAPH_AVAILABLE:
            return None

        node_ids = cluster.all_node_ids
        if not node_ids:
            logger.warning("Cluster %s has no nodes — skipping subgraph", cluster.cluster_id)
            return None

        try:
            subgraph = StateGraph(K1GraphState)

            # Add cluster nodes
            for nid in node_ids:
                if nid in self._callables:
                    subgraph.add_node(nid, self._callables[nid])

            # Wire intra-cluster edges
            cluster_edges = [
                e for e in self._spec.edges
                if e.source in node_ids and e.target in node_ids
            ]
            from collections import defaultdict
            outgoing: dict[str, list] = defaultdict(list)
            for edge in cluster_edges:
                outgoing[edge.source].append(edge)

            for source_id, edges in outgoing.items():
                all_unconditional = all(e.condition == EdgeCondition.ALWAYS for e in edges)
                if all_unconditional and len(edges) == 1:
                    subgraph.add_edge(source_id, edges[0].target)
                elif edges:
                    router = _make_condition_router(edges)
                    targets = [e.target for e in edges]
                    if END not in targets:
                        targets.append(END)
                    subgraph.add_conditional_edges(source_id, router, targets)

            # Explicit terminal edge for cluster exit_node
            if cluster.exit_node and cluster.exit_node in node_ids:
                if not outgoing.get(cluster.exit_node):
                    subgraph.add_edge(cluster.exit_node, END)

            # Set entry point
            entry = cluster.entry_node or (cluster.coordinator_id if cluster.coordinator_id else node_ids[0])
            if entry in node_ids:
                subgraph.set_entry_point(entry)

            compiled = subgraph.compile()
            logger.info(
                "Cluster subgraph compiled: cluster=%s nodes=%d edges=%d",
                cluster.cluster_id, len(node_ids), len(cluster_edges),
            )
            return compiled

        except Exception as exc:
            logger.error(
                "Cluster subgraph compilation failed for %s: %s",
                cluster.cluster_id, exc,
            )
            return None

    def build_cluster_scaffold(self, cluster: ClusterSpec) -> dict[str, Any]:
        """
        Return a scaffold spec for a single cluster (subgraph inspection).
        Used for API/UI inspection of cluster topology.
        """
        node_ids = cluster.all_node_ids
        cluster_nodes = [
            n.to_dict() for nid, n in self._spec.nodes.items() if nid in node_ids
        ]
        cluster_edges = [
            e.to_dict() for e in self._spec.edges
            if e.source in node_ids and e.target in node_ids
        ]
        return {
            "cluster_id": cluster.cluster_id,
            "cluster_name": cluster.cluster_name,
            "phase": cluster.phase,
            "nodes": cluster_nodes,
            "edges": cluster_edges,
            "entry_node": cluster.entry_node,
            "exit_node": cluster.exit_node,
            "parallel_execution": cluster.parallel_execution,
        }


# -- Execution order resolution ------------------------------------------------
# Canonical implementation lives in praison_topology.
from apps.backend.src.core.praison_topology import resolve_execution_order as _resolve_execution_order  # noqa: E402,E501
