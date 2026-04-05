"""
Praison Orchestration Topology
================================
Graph topology model for K1's hybrid orchestration system.
"""

from __future__ import annotations

import os
import uuid
import asyncio
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, Optional

from apps.backend.src.core.trilium.client import TriliumClient
from apps.backend.src.core.trilium.query import OrchestrationQueryLayer
from apps.backend.src.core.trilium.session_manager import SessionManager
from apps.backend.src.core.trilium.exploit_coordinator import ExploitCoordinator
from apps.backend.src.core.trilium.vulnerability_chainer import VulnerabilityChainer
from apps.backend.src.core.trilium.handoff import StateHandoffSystem
from apps.backend.src.core.governance.governor import Governor 

logger = logging.getLogger(__name__)


# ── Edge routing conditions ───────────────────────────────────────────────────

class EdgeCondition(str):
    ALWAYS          = "always"
    ON_SUCCESS      = "on_success"
    ON_FAILURE      = "on_failure"
    ON_APPROVAL     = "on_approval"
    ON_REJECTION    = "on_rejection"
    ON_ARTIFACT     = "on_artifact"
    ON_HIGH_SIGNAL  = "on_high_signal"
    ON_LOW_SIGNAL   = "on_low_signal"
    ON_PHASE_COMPLETE = "on_phase_complete"


# ── Node spec ─────────────────────────────────────────────────────────────────

@dataclass
class NodeSpec:
    node_id: str
    agent_id: str
    node_type: str
    cluster_id: str        = ""
    agent_class: str       = "specialist"
    risk_profile: str      = "standard"
    review_policy: str     = "standard"
    memory_scope: str      = "session"
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt: str     = ""
    litellm_model: str     = ""
    interrupt_before: bool = False
    interrupt_after: bool  = False
    is_entry: bool         = False
    is_exit: bool          = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_langgraph_spec(cls, spec: dict[str, Any], cluster_id: str = "") -> "NodeSpec":
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
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "node_type": self.node_type,
            "cluster_id": self.cluster_id,
            "is_entry": self.is_entry,
            "is_exit": self.is_exit,
        }


# ── Edge spec ─────────────────────────────────────────────────────────────────

@dataclass
class EdgeSpec:
    edge_id: str      = field(default_factory=lambda: str(uuid.uuid4()))
    source: str       = ""
    target: str       = ""
    condition: str    = EdgeCondition.ALWAYS
    artifact_type: str = ""
    label: str        = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
        }


# ── Cluster spec ──────────────────────────────────────────────────────────────

@dataclass
class ClusterSpec:
    cluster_id: str         = field(default_factory=lambda: str(uuid.uuid4()))
    cluster_name: str       = ""
    phase: str              = ""
    coordinator_id: str     = ""
    specialist_ids: list[str] = field(default_factory=list)
    entry_node: str         = ""
    exit_node: str          = ""
    parallel_execution: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"cluster_id": self.cluster_id, "cluster_name": self.cluster_name}


# ── Mission graph spec ────────────────────────────────────────────────────────

@dataclass
class MissionGraphSpec:
    graph_id: str           = field(default_factory=lambda: str(uuid.uuid4()))
    mission_name: str       = ""
    workflow_id: str        = ""
    program_id: str         = ""
    nodes: dict[str, NodeSpec]   = field(default_factory=dict)
    edges: list[EdgeSpec]        = field(default_factory=list)
    clusters: dict[str, ClusterSpec] = field(default_factory=dict)
    entry_node: str         = ""
    exit_node: str          = ""
    checkpointer_scope: str = "workflow"
    governor: Governor | None = None

    def add_node(self, node: NodeSpec) -> "MissionGraphSpec":
        self.nodes[node.node_id] = node
        if node.is_entry: self.entry_node = node.node_id
        if node.is_exit: self.exit_node = node.node_id
        return self

    def add_edge(self, source: str, target: str, condition: str = EdgeCondition.ALWAYS) -> "MissionGraphSpec":
        self.edges.append(EdgeSpec(source=source, target=target, condition=condition))
        return self

    def add_cluster(self, cluster: ClusterSpec) -> "MissionGraphSpec":
        self.clusters[cluster.cluster_id] = cluster
        return self


# ── Execution order resolution ────────────────────────────────────────────────

def resolve_execution_order(graph_spec: "MissionGraphSpec") -> list[str]:
    """
    Resolve execution order for the mission graph using topological sort.

    Returns a list of node IDs in valid execution order, starting from entry_node
    and ending at exit_node, respecting edge constraints.
    """
    if not graph_spec.nodes:
        return []

    # Build adjacency list
    graph: dict[str, list[str]] = {node_id: [] for node_id in graph_spec.nodes}
    in_degree: dict[str, int] = {node_id: 0 for node_id in graph_spec.nodes}

    for edge in graph_spec.edges:
        if edge.source in graph_spec.nodes and edge.target in graph_spec.nodes:
            graph[edge.source].append(edge.target)
            in_degree[edge.target] += 1

    # Topological sort (Kahn's algorithm)
    queue: list[str] = [node_id for node_id in graph_spec.nodes if in_degree[node_id] == 0]
    order: list[str] = []

    while queue:
        # Prefer entry node first if available
        if graph_spec.entry_node in queue:
            current = graph_spec.entry_node
            queue.remove(current)
        else:
            current = queue.pop(0)

        order.append(current)

        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order


# ── PraisonTopology ───────────────────────────────────────────────────────────

class PraisonTopology:
    @staticmethod
    def build_standard_bug_bounty(
        workflow_id: str,
        program_id: str,
        agent_specs: dict[str, dict[str, Any]],
        governor: Governor | None = None,
    ) -> MissionGraphSpec:
        graph = MissionGraphSpec(
            mission_name=f"bug_bounty_{program_id}",
            workflow_id=workflow_id,
            program_id=program_id,
            governor=governor,
        )
        for agent_id, spec in agent_specs.items():
            node = NodeSpec.from_langgraph_spec(spec)
            is_entry = (agent_id == "GovernanceDirector")
            is_exit = (agent_id == "HandoffLiaison")
            node.is_entry = is_entry
            node.is_exit = is_exit
            graph.add_node(node)

        # Core orchestration flow: governance → mission direction → phase coordination
        graph.add_edge("GovernanceDirector", "MissionDirector", EdgeCondition.ON_SUCCESS)
        graph.add_edge("MissionDirector", "PhaseCoordinator", EdgeCondition.ON_SUCCESS)

        # Phase Group A (parallel from PhaseCoordinator: surface mapping + OSINT + dark web + secrets)
        graph.add_edge("PhaseCoordinator", "SurfaceMapper", EdgeCondition.ON_SUCCESS)
        graph.add_edge("PhaseCoordinator", "OSINTIntelligenceAgent", EdgeCondition.ON_SUCCESS)
        graph.add_edge("PhaseCoordinator", "DarkWebIntelAgent", EdgeCondition.ON_SUCCESS)
        graph.add_edge("PhaseCoordinator", "SecretScannerAgent", EdgeCondition.ON_SUCCESS)

        # Phase Group B (content discovery after Phase 1-2: depends on SurfaceMapper completion)
        graph.add_edge("SurfaceMapper", "ContentDiscoveryAgent", EdgeCondition.ON_SUCCESS)

        # Phase Group C (vulnerability & API testing after content discovery)
        graph.add_edge("ContentDiscoveryAgent", "VulnerabilityAgent", EdgeCondition.ON_SUCCESS)
        graph.add_edge("ContentDiscoveryAgent", "APISecurityAgent", EdgeCondition.ON_SUCCESS)

        # Phase Group D (aggregation & evidence analysis after all scanning complete)
        # All scanning agents converge into faraday coordinator
        graph.add_edge("VulnerabilityAgent", "FaradayCoordinatorAgent", EdgeCondition.ON_SUCCESS)
        graph.add_edge("APISecurityAgent", "FaradayCoordinatorAgent", EdgeCondition.ON_SUCCESS)
        # Parallel agents (OSINT, dark web, secrets) also feed to faraday
        graph.add_edge("OSINTIntelligenceAgent", "FaradayCoordinatorAgent", EdgeCondition.ON_SUCCESS)
        graph.add_edge("DarkWebIntelAgent", "FaradayCoordinatorAgent", EdgeCondition.ON_SUCCESS)
        graph.add_edge("SecretScannerAgent", "FaradayCoordinatorAgent", EdgeCondition.ON_SUCCESS)

        # Evidence analysis → reporting → handoff (final convergence)
        graph.add_edge("FaradayCoordinatorAgent", "EvidenceAnalyst", EdgeCondition.ON_SUCCESS)
        graph.add_edge("EvidenceAnalyst", "ReportSynthesisAgent", EdgeCondition.ON_SUCCESS)
        graph.add_edge("ReportSynthesisAgent", "HandoffLiaison", EdgeCondition.ON_SUCCESS)

        return graph


# ── Mission Orchestrator ──────────────────────────────

@dataclass
class MissionCheckpoint:
    mission_id: str
    target_id: str
    last_processed_stage: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "target_id": self.target_id,
            "last_processed_stage": self.last_processed_stage,
            "timestamp": self.timestamp,
        }

class MissionOrchestrator:
    def __init__(
        self,
        trilium_client: TriliumClient,
        query_layer: OrchestrationQueryLayer,
        session_manager: SessionManager,
        exploit_coordinator: ExploitCoordinator,
        vulnerability_chainer: VulnerabilityChainer,
        state_handoff_system: StateHandoffSystem,
        governor: Governor | None = None,
    ):
        self.trilium_client = trilium_client
        self.query_layer = query_layer
        self.session_manager = session_manager
        self.exploit_coordinator = exploit_coordinator
        self.vulnerability_chainer = vulnerability_chainer
        self.state_handoff_system = state_handoff_system
        self.governor = governor
        self.operator_absent = os.environ.get("K1_OPERATOR", "true").lower() == "false"
        self.checkpoint_root_id = os.environ.get("K1_CHECKPOINT_ROOT_ID", "checkpoints")

    async def start_mission(self, mission_id: str, target_id: str):
        logger.info(f"Orchestrator: Starting mission {mission_id} for {target_id}")
        
        last_checkpoint = await self._load_last_checkpoint(mission_id)
        stages = ["recon", "scanning", "analysis", "chaining", "exploitation", "reporting", "handoff"]
        start_idx = stages.index(last_checkpoint.last_processed_stage) + 1 if last_checkpoint else 0

        for i in range(start_idx, len(stages)):
            stage = stages[i]
            
            if self.governor and not await self.governor.request_token(f"orchestrator_{stage}"):
                logger.error(f"Governor: Denied token for stage {stage}.")
                break

            if self.operator_absent:
                logger.info(f"Orchestrator: K1_OPERATOR=False. Autonomous mode for {stage}.")

            try:
                await self._execute_stage(stage, target_id)
                if stage in ["chaining", "exploitation"]:
                    await self._save_checkpoint(mission_id, target_id, stage)
            except Exception as e:
                logger.error(f"Orchestrator: Stage {stage} failed: {str(e)}")
                break

    async def _execute_stage(self, stage: str, target_id: str):
        logger.info(f"Orchestrator: Executing {stage}...")
        await asyncio.sleep(1)
        if stage == "chaining":
            await self.vulnerability_chainer.scan_for_potential_chains(target_id)

    async def _save_checkpoint(self, mission_id: str, target_id: str, stage: str):
        checkpoint = MissionCheckpoint(mission_id, target_id, stage)
        content = f"<pre><code>{json.dumps(checkpoint.to_dict(), indent=2)}</code></pre>"
        title = f"Checkpoint:{mission_id}:{stage}"
        new_note = await self.trilium_client.create_note(self.checkpoint_root_id, title, content)
        note_id = new_note["note"]["noteId"]
        await self.trilium_client.create_attribute(note_id, "label", "mission_id", mission_id)
        await self.trilium_client.create_attribute(note_id, "label", "type", "checkpoint")
        await self.trilium_client.create_attribute(note_id, "label", "stage", stage)

    async def _load_last_checkpoint(self, mission_id: str) -> MissionCheckpoint | None:
        query = f"note.labels.mission_id='{mission_id}' AND note.labels.type='checkpoint'"
        results = await self.trilium_client.search_notes(query)
        if not results: return None
        
        checkpoints = []
        for r in results:
            note = await self.trilium_client.get_note(r["noteId"])
            try:
                raw_json = re.sub(r"<.*?>", "", note.get("content", "{}")).strip()
                data = json.loads(raw_json)
                checkpoints.append(MissionCheckpoint(**data))
            except Exception: continue
        
        if not checkpoints: return None
        checkpoints.sort(key=lambda x: x.timestamp, reverse=True)
        return checkpoints[0]

    async def stop_all_components(self):
        await self.session_manager.stop()
        await self.state_handoff_system.stop()
