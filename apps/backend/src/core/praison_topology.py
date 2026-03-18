"""
Praison Orchestration Topology
================================
Graph topology model for K1's hybrid orchestration system.

Defines the static structure of the mission execution graph:
  - NodeSpec: a single agent node with all policy metadata
  - EdgeSpec: a directed edge between nodes with routing condition
  - ClusterSpec: a bounded group of nodes (phase cluster)
  - MissionGraphSpec: the complete graph for a campaign mission

This module is STRUCTURAL ONLY — it defines graph shape.
  - PraisonLangGraphBuilder converts this into an executable LangGraph StateGraph
  - PraisonClusterRuntime executes clusters against this topology

Standard topology for a K1 bug bounty mission:
  GovernanceDirector
       ↓ delegates to
  MissionDirector ─────────────────────────────────┐
       ↓ delegates to                               ↓
  PhaseCoordinator (recon)   PhaseCoordinator (scanning)
       ↓ delegates to               ↓ delegates to
  SurfaceMapper               ReconSpecialist
  (specialist)                (specialist)
       ↓ artifacts ──→ EvidenceAnalyst ──→ ReportSynthesisAgent
                             ↓ artifacts
                        GovernanceDirector (approval gate)
                             ↓ approved
                        HandoffLiaison ──→ SUBMITTED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


# ── Edge routing conditions ───────────────────────────────────────────────────

class EdgeCondition(str):
    """String constants for conditional edge routing in LangGraph."""
    ALWAYS          = "always"           # unconditional
    ON_SUCCESS      = "on_success"       # previous node completed without error
    ON_FAILURE      = "on_failure"       # previous node errored
    ON_APPROVAL     = "on_approval"      # HIL or governance approved
    ON_REJECTION    = "on_rejection"     # HIL or governance rejected
    ON_ARTIFACT     = "on_artifact"      # specific artifact type was produced
    ON_HIGH_SIGNAL  = "on_high_signal"   # high-confidence vulnerability signal found
    ON_LOW_SIGNAL   = "on_low_signal"    # no significant findings
    ON_PHASE_COMPLETE = "on_phase_complete"


# ── Node spec ─────────────────────────────────────────────────────────────────

@dataclass
class NodeSpec:
    """
    Specification for a single agent node in the mission graph.
    Derived from AgentIdentity + topology-specific metadata.
    """
    node_id: str           # unique in graph (= agent_id)
    agent_id: str          # canonical agent_id from registry
    node_type: str         # governance|coordinator|reporter|agent
    cluster_id: str        = ""     # cluster this node belongs to
    agent_class: str       = "specialist"
    risk_profile: str      = "standard"
    review_policy: str     = "standard"
    memory_scope: str      = "session"
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt: str     = ""
    litellm_model: str     = ""
    interrupt_before: bool = False   # LangGraph interrupt_before=[node_id]
    interrupt_after: bool  = False   # LangGraph interrupt_after=[node_id]
    is_entry: bool         = False   # graph entry point
    is_exit: bool          = False   # terminal node
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_langgraph_spec(cls, spec: dict[str, Any], cluster_id: str = "") -> "NodeSpec":
        """Build a NodeSpec from a LangGraph adapter spec dict."""
        interrupt_policy = spec.get("interrupt_policy", {})
        return cls(
            node_id=spec["node_id"],
            agent_id=spec["node_id"],
            node_type=spec.get("node_type", "agent"),
            cluster_id=cluster_id,
            agent_class=spec.get("agent_class", "specialist"),
            risk_profile=spec.get("risk_profile", "standard"),
            review_policy=spec.get("review_policy", "standard"),
            memory_scope=spec.get("memory_scope", "session"),
            allowed_tools=spec.get("allowed_tools", []),
            system_prompt=spec.get("system_prompt", ""),
            litellm_model=spec.get("litellm_model", ""),
            interrupt_before=interrupt_policy.get("interrupt_before", False),
            interrupt_after=interrupt_policy.get("interrupt_after", False),
            metadata=spec,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id":         self.node_id,
            "agent_id":        self.agent_id,
            "node_type":       self.node_type,
            "cluster_id":      self.cluster_id,
            "agent_class":     self.agent_class,
            "risk_profile":    self.risk_profile,
            "review_policy":   self.review_policy,
            "memory_scope":    self.memory_scope,
            "allowed_tools":   self.allowed_tools,
            "interrupt_before": self.interrupt_before,
            "interrupt_after":  self.interrupt_after,
            "is_entry":        self.is_entry,
            "is_exit":         self.is_exit,
        }


# ── Edge spec ─────────────────────────────────────────────────────────────────

@dataclass
class EdgeSpec:
    """Directed edge between two nodes in the mission graph."""
    edge_id: str      = field(default_factory=lambda: str(uuid.uuid4()))
    source: str       = ""   # node_id
    target: str       = ""   # node_id
    condition: str    = EdgeCondition.ALWAYS
    artifact_type: str = ""  # required artifact type if condition=ON_ARTIFACT
    label: str        = ""   # human-readable edge label for UI

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id":       self.edge_id,
            "source":        self.source,
            "target":        self.target,
            "condition":     self.condition,
            "artifact_type": self.artifact_type,
            "label":         self.label,
        }


# ── Cluster spec ──────────────────────────────────────────────────────────────

@dataclass
class ClusterSpec:
    """
    A bounded phase cluster — a group of agents that execute within
    a single workflow phase under a coordinator's authority.

    Cluster execution is decentralized: the coordinator delegates to
    specialists independently. Cross-cluster communication goes through
    the MissionDirector or GovernanceDirector.
    """
    cluster_id: str         = field(default_factory=lambda: str(uuid.uuid4()))
    cluster_name: str       = ""    # human-readable, e.g. "recon_cluster"
    phase: str              = ""    # workflow phase this cluster executes in
    coordinator_id: str     = ""    # node_id of the coordinator agent
    specialist_ids: list[str] = field(default_factory=list)  # specialist node_ids
    entry_node: str         = ""    # first node executed in this cluster
    exit_node: str          = ""    # last node — signals cluster completion
    parallel_execution: bool = True  # specialists can run in parallel

    @property
    def all_node_ids(self) -> list[str]:
        ids = []
        if self.coordinator_id:
            ids.append(self.coordinator_id)
        ids.extend(self.specialist_ids)
        return ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id":         self.cluster_id,
            "cluster_name":       self.cluster_name,
            "phase":              self.phase,
            "coordinator_id":     self.coordinator_id,
            "specialist_ids":     self.specialist_ids,
            "entry_node":         self.entry_node,
            "exit_node":          self.exit_node,
            "parallel_execution": self.parallel_execution,
        }


# ── Mission graph spec ────────────────────────────────────────────────────────

@dataclass
class MissionGraphSpec:
    """
    Complete graph specification for a K1 campaign mission.

    Contains:
      - All node specs (one per agent instance)
      - All edge specs (directed graph)
      - All cluster specs (phase groupings)
      - Entry/exit node IDs
      - Global graph metadata
    """
    graph_id: str           = field(default_factory=lambda: str(uuid.uuid4()))
    mission_name: str       = ""
    workflow_id: str        = ""
    program_id: str         = ""
    nodes: dict[str, NodeSpec]   = field(default_factory=dict)    # node_id → NodeSpec
    edges: list[EdgeSpec]        = field(default_factory=list)
    clusters: dict[str, ClusterSpec] = field(default_factory=dict)  # cluster_id → ClusterSpec
    entry_node: str         = ""
    exit_node: str          = ""
    checkpointer_scope: str = "workflow"  # PostgreSQL checkpointer scope for LangGraph

    # ── Mutation helpers ──────────────────────────────────────────────────────

    def add_node(self, node: NodeSpec) -> "MissionGraphSpec":
        self.nodes[node.node_id] = node
        if node.is_entry:
            self.entry_node = node.node_id
        if node.is_exit:
            self.exit_node = node.node_id
        return self

    def add_edge(
        self,
        source: str,
        target: str,
        condition: str = EdgeCondition.ALWAYS,
        artifact_type: str = "",
        label: str = "",
    ) -> "MissionGraphSpec":
        self.edges.append(EdgeSpec(
            source=source,
            target=target,
            condition=condition,
            artifact_type=artifact_type,
            label=label,
        ))
        return self

    def add_cluster(self, cluster: ClusterSpec) -> "MissionGraphSpec":
        self.clusters[cluster.cluster_id] = cluster
        return self

    # ── Queries ───────────────────────────────────────────────────────────────

    def outgoing_edges(self, node_id: str) -> list[EdgeSpec]:
        return [e for e in self.edges if e.source == node_id]

    def incoming_edges(self, node_id: str) -> list[EdgeSpec]:
        return [e for e in self.edges if e.target == node_id]

    def cluster_for_node(self, node_id: str) -> ClusterSpec | None:
        for cluster in self.clusters.values():
            if node_id in cluster.all_node_ids:
                return cluster
        return None

    def governance_nodes(self) -> list[NodeSpec]:
        return [n for n in self.nodes.values() if n.node_type == "governance"]

    def nodes_requiring_interrupt(self) -> list[NodeSpec]:
        return [n for n in self.nodes.values() if n.interrupt_before or n.interrupt_after]

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id":           self.graph_id,
            "mission_name":       self.mission_name,
            "workflow_id":        self.workflow_id,
            "program_id":         self.program_id,
            "nodes":              {k: v.to_dict() for k, v in self.nodes.items()},
            "edges":              [e.to_dict() for e in self.edges],
            "clusters":           {k: v.to_dict() for k, v in self.clusters.items()},
            "entry_node":         self.entry_node,
            "exit_node":          self.exit_node,
            "checkpointer_scope": self.checkpointer_scope,
        }


# ── PraisonTopology ───────────────────────────────────────────────────────────

class PraisonTopology:
    """
    Builder for standard K1 mission graph topologies.

    Provides pre-built topology patterns for common campaign shapes.
    Custom topologies can be assembled directly via MissionGraphSpec.
    """

    @staticmethod
    def build_standard_bug_bounty(
        workflow_id: str,
        program_id: str,
        agent_specs: dict[str, dict[str, Any]],
    ) -> MissionGraphSpec:
        """
        Build the standard K1 bug bounty mission graph topology.

        Standard shape:
          GovernanceDirector → MissionDirector → [recon cluster] → [scan cluster]
          → EvidenceAnalyst → GovernanceDirector (approval) → ReportSynthesisAgent
          → HandoffLiaison → EXIT

        agent_specs: {agent_id: langgraph_node_spec_dict}
        All 11 canonical agents should be present.
        """
        graph = MissionGraphSpec(
            mission_name=f"bug_bounty_{program_id}",
            workflow_id=workflow_id,
            program_id=program_id,
            checkpointer_scope="workflow",
        )

        # Add all nodes
        for agent_id, spec in agent_specs.items():
            node = NodeSpec.from_langgraph_spec(spec)
            is_entry = (agent_id == "GovernanceDirector")
            is_exit = (agent_id == "HandoffLiaison")
            node = NodeSpec(
                **{k: v for k, v in vars(node).items() if k not in ("is_entry", "is_exit")},
                is_entry=is_entry,
                is_exit=is_exit,
            )
            graph.add_node(node)

        # Governance → Mission direction
        graph.add_edge("GovernanceDirector", "MissionDirector",
                       condition=EdgeCondition.ON_APPROVAL, label="mission_approved")

        # Mission → Phase coordinators
        graph.add_edge("MissionDirector", "PhaseCoordinator",
                       condition=EdgeCondition.ON_SUCCESS, label="recon_phase")

        # Recon cluster: coordinator → specialists (parallel)
        graph.add_edge("PhaseCoordinator", "SurfaceMapper",
                       condition=EdgeCondition.ON_SUCCESS, label="surface_scan")
        graph.add_edge("PhaseCoordinator", "ReconSpecialist",
                       condition=EdgeCondition.ON_SUCCESS, label="active_recon")

        # Specialists → analysis
        graph.add_edge("SurfaceMapper", "EvidenceAnalyst",
                       condition=EdgeCondition.ON_ARTIFACT,
                       artifact_type="recon_surface", label="surface_artifact")
        graph.add_edge("ReconSpecialist", "EvidenceAnalyst",
                       condition=EdgeCondition.ON_ARTIFACT,
                       artifact_type="pentest_evidence", label="evidence_artifact")

        # Analysis → governance gate
        graph.add_edge("EvidenceAnalyst", "GovernanceDirector",
                       condition=EdgeCondition.ON_HIGH_SIGNAL, label="requires_approval")
        graph.add_edge("EvidenceAnalyst", "ReportSynthesisAgent",
                       condition=EdgeCondition.ON_LOW_SIGNAL, label="direct_to_report")

        # Governance → report (approved path)
        graph.add_edge("GovernanceDirector", "ReportSynthesisAgent",
                       condition=EdgeCondition.ON_APPROVAL, label="findings_approved")

        # Report → handoff → exit
        graph.add_edge("ReportSynthesisAgent", "HandoffLiaison",
                       condition=EdgeCondition.ON_SUCCESS, label="report_ready")

        # Build clusters
        recon_cluster = ClusterSpec(
            cluster_name="recon_cluster",
            phase="recon",
            coordinator_id="PhaseCoordinator",
            specialist_ids=["SurfaceMapper", "ReconSpecialist"],
            entry_node="PhaseCoordinator",
            exit_node="EvidenceAnalyst",
            parallel_execution=True,
        )
        graph.add_cluster(recon_cluster)

        return graph


# ── Topological execution order ──────────────────────────────────────────────


def resolve_execution_order(spec: MissionGraphSpec) -> list[str]:
    """
    Resolve topological execution order from graph topology.

    Starting from ``spec.entry_node``, performs a DFS traversal following
    outgoing edges.  Any nodes not reachable from the entry are appended
    at the end.  If there is no entry node, the dict-insertion order of
    ``spec.nodes`` is returned.
    """
    if not spec.entry_node:
        return list(spec.nodes.keys())
    visited: list[str] = []
    _topo_visit(spec.entry_node, spec, visited, set())
    for nid in spec.nodes:
        if nid not in visited:
            visited.append(nid)
    return visited


def _topo_visit(
    node_id: str,
    spec: MissionGraphSpec,
    visited: list[str],
    in_progress: set[str],
) -> None:
    """DFS helper for :func:`resolve_execution_order`."""
    if node_id in visited or node_id in in_progress:
        return
    in_progress.add(node_id)
    visited.append(node_id)
    in_progress.discard(node_id)
    for edge in spec.outgoing_edges(node_id):
        _topo_visit(edge.target, spec, visited, in_progress)
