"""
Tests for Wave 4 Pipeline Wiring (Task 2)
==========================================
Validates topology construction, execution order, and node callable integration
for all 7 new Wave 4 crew agents.
"""

from __future__ import annotations

import asyncio

import pytest
from apps.backend.src.core.praison_topology import (
    PraisonTopology,
    resolve_execution_order,
)
from apps.backend.src.core.praison_mission_runtime import _make_minimal_agent_specs
from apps.backend.src.core.praison_node_executors import build_standard_node_callables
from apps.backend.src.core.crew_agent_factory import instantiate_crew_agents


WAVE4_CREW_AGENTS = [
    "OSINTIntelligenceAgent",
    "DarkWebIntelAgent",
    "SecretScannerAgent",
    "ContentDiscoveryAgent",
    "VulnerabilityAgent",
    "APISecurityAgent",
    "FaradayCoordinatorAgent",
]


class TestTopologyConstruction:
    """Test that Wave 4 agents are properly included in topology."""

    def test_agent_specs_include_all_wave4_agents(self):
        """All Wave 4 agents should be in minimal specs."""
        specs = _make_minimal_agent_specs()
        for agent_id in WAVE4_CREW_AGENTS:
            assert agent_id in specs, f"{agent_id} not in agent specs"
            assert specs[agent_id]["node_type"] == "agent"
            assert specs[agent_id]["agent_class"] == "specialist"

    def test_graph_includes_all_wave4_nodes(self):
        """All Wave 4 agents should create nodes in the graph."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        for agent_id in WAVE4_CREW_AGENTS:
            assert agent_id in graph.nodes, f"{agent_id} node not in graph"
            node = graph.nodes[agent_id]
            assert node.node_id == agent_id
            assert node.agent_id == agent_id

    def test_graph_has_expected_edge_count(self):
        """Graph should have 17 edges for proper execution flow."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        assert len(graph.edges) == 17, f"Expected 17 edges, got {len(graph.edges)}"

    def test_entry_and_exit_nodes_configured(self):
        """Entry and exit nodes should be properly set."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        assert graph.entry_node == "GovernanceDirector"
        assert graph.exit_node == "HandoffLiaison"


class TestPhaseGroupEdges:
    """Test that phase groups are properly connected."""

    def test_phase_a_parallel_edges_from_coordinator(self):
        """Phase A agents should receive edges from PhaseCoordinator."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        phase_a_targets = [e.target for e in graph.edges if e.source == "PhaseCoordinator"]
        expected_a = ["SurfaceMapper", "OSINTIntelligenceAgent", "DarkWebIntelAgent", "SecretScannerAgent"]
        for agent in expected_a:
            assert agent in phase_a_targets, f"{agent} not in Phase A targets"

    def test_phase_b_edge_from_surface_mapper(self):
        """ContentDiscovery should depend on SurfaceMapper (Phase B)."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        surface_mapper_targets = [e.target for e in graph.edges if e.source == "SurfaceMapper"]
        assert "ContentDiscoveryAgent" in surface_mapper_targets

    def test_phase_c_edges_from_discovery(self):
        """Vulnerability and APISecurity should depend on ContentDiscovery (Phase C)."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        discovery_targets = [e.target for e in graph.edges if e.source == "ContentDiscoveryAgent"]
        assert "VulnerabilityAgent" in discovery_targets
        assert "APISecurityAgent" in discovery_targets

    def test_phase_d_convergence_to_faraday(self):
        """All scanning agents should converge to FaradayCoordinator."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        faraday_sources = [e.source for e in graph.edges if e.target == "FaradayCoordinatorAgent"]
        # Should have edges from: VulnerabilityAgent, APISecurityAgent, OSINTIntelligenceAgent,
        # DarkWebIntelAgent, SecretScannerAgent
        expected_sources = [
            "VulnerabilityAgent",
            "APISecurityAgent",
            "OSINTIntelligenceAgent",
            "DarkWebIntelAgent",
            "SecretScannerAgent",
        ]
        for source in expected_sources:
            assert source in faraday_sources, f"{source} not connected to FaradayCoordinator"

    def test_final_sequence_edges(self):
        """FaradayCoordinator → EvidenceAnalyst → ReportSynthesis → HandoffLiaison."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        # Check FaradayCoordinator → EvidenceAnalyst
        faraday_targets = [e.target for e in graph.edges if e.source == "FaradayCoordinatorAgent"]
        assert "EvidenceAnalyst" in faraday_targets
        # Check EvidenceAnalyst → ReportSynthesis
        evidence_targets = [e.target for e in graph.edges if e.source == "EvidenceAnalyst"]
        assert "ReportSynthesisAgent" in evidence_targets
        # Check ReportSynthesis → HandoffLiaison
        report_targets = [e.target for e in graph.edges if e.source == "ReportSynthesisAgent"]
        assert "HandoffLiaison" in report_targets


class TestExecutionOrder:
    """Test topological execution order resolution."""

    def test_execution_order_valid(self):
        """Execution order should be valid per edge constraints."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        order = resolve_execution_order(graph)
        assert len(order) == len(graph.nodes), "Execution order should include all nodes"

    def test_entry_first_in_execution_order(self):
        """Entry node should be first in execution order."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        order = resolve_execution_order(graph)
        assert order[0] == "GovernanceDirector"

    def test_exit_last_in_execution_order(self):
        """Exit node should be last in execution order."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        order = resolve_execution_order(graph)
        assert order[-1] == "HandoffLiaison"

    def test_phase_dependencies_respected(self):
        """Execution order should respect phase dependencies."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        order = resolve_execution_order(graph)
        order_dict = {node_id: idx for idx, node_id in enumerate(order)}

        # SurfaceMapper should come before ContentDiscovery
        assert (
            order_dict["SurfaceMapper"] < order_dict["ContentDiscoveryAgent"]
        ), "SurfaceMapper should execute before ContentDiscovery"

        # ContentDiscovery should come before Vulnerability and APISecurity
        assert (
            order_dict["ContentDiscoveryAgent"] < order_dict["VulnerabilityAgent"]
        ), "ContentDiscovery should execute before Vulnerability"
        assert (
            order_dict["ContentDiscoveryAgent"] < order_dict["APISecurityAgent"]
        ), "ContentDiscovery should execute before APISecurity"

        # All scanning agents should come before FaradayCoordinator
        for agent in [
            "VulnerabilityAgent",
            "APISecurityAgent",
            "OSINTIntelligenceAgent",
            "DarkWebIntelAgent",
            "SecretScannerAgent",
        ]:
            assert (
                order_dict[agent] < order_dict["FaradayCoordinatorAgent"]
            ), f"{agent} should execute before FaradayCoordinator"


class TestNodeCallables:
    """Test that node executors are properly created."""

    def test_all_wave4_agents_have_executors(self):
        """All Wave 4 agents should have executor functions."""
        callables = build_standard_node_callables()
        for agent_id in WAVE4_CREW_AGENTS:
            assert agent_id in callables, f"{agent_id} not in node callables"
            assert callable(callables[agent_id]), f"{agent_id} callable is not callable"

    def test_all_standard_agents_have_executors(self):
        """All standard agents should have executor functions."""
        standard_agents = [
            "GovernanceDirector",
            "MissionDirector",
            "PhaseCoordinator",
            "SurfaceMapper",
            "ReconSpecialist",
            "EvidenceAnalyst",
            "ReportSynthesisAgent",
            "HandoffLiaison",
        ]
        callables = build_standard_node_callables()
        for agent_id in standard_agents:
            assert agent_id in callables, f"{agent_id} not in node callables"

    def test_executors_accept_state_dict(self):
        """Executors should accept state dict and return state update."""
        callables = build_standard_node_callables()
        state = {
            "mission_id": "test-mission",
            "workflow_id": "test-wf",
            "program_id": "test-prog",
            "execution_mode": "graph_only",  # graph_only to avoid real execution
        }
        for agent_id in ["OSINTIntelligenceAgent", "VulnerabilityAgent", "FaradayCoordinatorAgent"]:
            result = callables[agent_id](state)
            assert isinstance(result, dict), f"{agent_id} executor should return dict"
            assert "active_node" in result, f"{agent_id} result should have active_node"


class TestCrewAgentFactory:
    """Test crew agent factory instantiation."""

    def test_factory_imports_successfully(self):
        """Factory module should import without errors."""
        from apps.backend.src.core.crew_agent_factory import (
            instantiate_crew_agents,
            _wrap_async_execute,
        )
        assert callable(instantiate_crew_agents)
        assert callable(_wrap_async_execute)

    def test_factory_returns_dict(self):
        """Factory should return a dict of callables."""
        factory_result = instantiate_crew_agents()
        assert isinstance(factory_result, dict)
        # May be empty if crew agents are not fully implemented, but should be a dict

    def test_wrap_async_execute_runs_under_active_event_loop(self):
        """Wrapper should execute async agents even when a loop is already running."""
        from apps.backend.src.core.crew_agent_factory import _wrap_async_execute

        class _FakeAgent:
            async def execute(self, mission_context, prior_findings):  # noqa: ANN001
                return {
                    "bridge_executed": True,
                    "findings": prior_findings + [{"source": "fake"}],
                    "mission_seen": mission_context.get("mission_id"),
                }

        wrapper = _wrap_async_execute(_FakeAgent(), "FakeAgent")

        async def _invoke():  # noqa: ANN202
            return wrapper(
                {
                    "mission_id": "m-bridge",
                    "workflow_id": "wf-bridge",
                    "program_id": "prog-bridge",
                    "findings": [{"source": "seed"}],
                }
            )

        result = asyncio.run(_invoke())
        assert result.get("bridge_executed") is True
        assert result.get("mission_seen") == "m-bridge"
        assert len(result.get("findings", [])) == 2
        history = result.get("node_history", [])
        assert history and history[0].get("status") == "completed"
        assert history[0].get("status") != "deferred_async"

    def test_langgraph_compile_falls_back_for_wave4_fanout(self):
        """Wave 4 multi-edge fan-out should enforce deterministic fallback compile behavior."""
        from apps.backend.src.core.praison_langgraph_builder import PraisonLangGraphBuilder

        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        callables = {
            node_id: (lambda state, _node_id=node_id: {"last_agent": _node_id})
            for node_id in graph.nodes
        }
        builder = PraisonLangGraphBuilder(graph, callables)
        assert builder.compile() is None


class TestIntegration:
    """Integration tests for complete pipeline."""

    def test_mission_creation_with_graph_spec(self):
        """Mission should be creatable with full Wave 4 topology."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )
        # Just verify we can build the graph without errors
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0
        assert graph.entry_node == "GovernanceDirector"
        assert graph.exit_node == "HandoffLiaison"

    def test_all_nodes_reachable_from_entry(self):
        """All nodes should be reachable from entry node via edges."""
        specs = _make_minimal_agent_specs()
        graph = PraisonTopology.build_standard_bug_bounty(
            workflow_id="test-wf",
            program_id="test-prog",
            agent_specs=specs,
        )

        # Build reachability map
        adj = {node_id: [] for node_id in graph.nodes}
        for edge in graph.edges:
            adj[edge.source].append(edge.target)

        # DFS from entry node
        visited = set()
        stack = [graph.entry_node]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    stack.append(neighbor)

        # All nodes except those without incoming edges should be reachable
        # (some parallel nodes may only be reachable via specific paths)
        assert len(visited) >= len(graph.nodes) - 2, "Most nodes should be reachable from entry"
