"""
Tests: Praison Hybrid Hierarchical Orchestration
=================================================
Validates all Phase 3 modules:
  - praison_agent.py   — AgentIdentity extended fields
  - praison_contracts.py — DelegationContract lifecycle
  - praison_artifacts.py — AgentArtifact + ArtifactStore
  - praison_runtime_policy.py — PraisonRuntimePolicy decisions
  - praison_topology.py — MissionGraphSpec / NodeSpec / ClusterSpec
  - praison_langgraph_builder.py — build_scaffold_spec() (no LangGraph install required)
  - praison_registry.py — loading + validation of new schema fields
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_agent(
    agent_id: str = "TestSpecialist",
    agent_class: str = "specialist",
    delegation_scope: str = "none",
    risk_profile: str = "standard",
    review_policy: str = "standard",
    memory_scope: str = "session",
    interrupt_policy: str = "none",
    escalation_policy: str = "hil_for_band2",
    handoff_policy: str = "coordinator_visible",
    allowed_tools: list[str] | None = None,
    allowed_peer_targets: list[str] | None = None,
    workflow_id: str = "wf-test",
    program_id: str = "prog-test",
):
    from apps.backend.src.core.praison_agent import AgentIdentity
    return AgentIdentity(
        agent_id=agent_id,
        persona=f"{agent_id} Persona",
        description="Test agent",
        system_prompt="You are a test agent.",
        allowed_tools=allowed_tools or ["tool_a", "tool_b"],
        risk_profile=risk_profile,
        llm_pin="anthropic",
        memory_scope=memory_scope,
        review_policy=review_policy,
        agent_class=agent_class,
        delegation_scope=delegation_scope,
        allowed_peer_targets=allowed_peer_targets or [],
        handoff_policy=handoff_policy,
        interrupt_policy=interrupt_policy,
        escalation_policy=escalation_policy,
        workflow_id=workflow_id,
        program_id=program_id,
    )


def _make_coordinator(allowed_peer_targets: list[str] | None = None):
    """Coordinator with no peer target restriction by default (empty = unrestricted)."""
    return _make_agent(
        "Coordinator",
        agent_class="coordinator",
        delegation_scope="local",
        allowed_peer_targets=allowed_peer_targets or [],
    )


def _make_director():
    return _make_agent(
        "Director",
        agent_class="director",
        delegation_scope="phase",
        risk_profile="orchestration",
        review_policy="moderate",
        memory_scope="mission",
    )


def _make_governor():
    return _make_agent(
        "Governor",
        agent_class="governor",
        delegation_scope="global",
        risk_profile="governance",
        review_policy="strict",
        memory_scope="mission",
        interrupt_policy="before_sensitive_tools",
        escalation_policy="governor_review_for_sensitive",
    )


# ── praison_agent.py tests ───────────────────────────────────────────────────

class TestAgentIdentityExtendedFields:
    def test_default_agent_class_is_specialist(self):
        from apps.backend.src.core.praison_agent import AgentIdentity
        agent = AgentIdentity(
            agent_id="X", persona="X", description="X", system_prompt="X"
        )
        assert agent.agent_class == "specialist"

    def test_default_delegation_scope_is_none(self):
        from apps.backend.src.core.praison_agent import AgentIdentity
        agent = AgentIdentity(
            agent_id="X", persona="X", description="X", system_prompt="X"
        )
        assert agent.delegation_scope == "none"

    def test_can_delegate_to_lower_class(self):
        coordinator = _make_coordinator()
        assert coordinator.can_delegate_to("specialist") is True
        assert coordinator.can_delegate_to("coordinator") is False
        assert coordinator.can_delegate_to("director") is False

    def test_governor_can_delegate_downward_but_not_to_governor(self):
        """SECURITY FIX (Phase 3.5): governors cannot delegate to other governors
        — prevents circular governance chains."""
        governor = _make_governor()
        assert governor.can_delegate_to("director") is True
        assert governor.can_delegate_to("coordinator") is True
        assert governor.can_delegate_to("specialist") is True
        assert governor.can_delegate_to("governor") is False  # blocked in Phase 3.5

    def test_specialist_cannot_delegate_to_anyone(self):
        agent = _make_agent("Spec", agent_class="specialist")
        for cls in ("governor", "director", "coordinator", "specialist"):
            assert agent.can_delegate_to(cls) is False

    def test_to_dict_includes_new_fields(self):
        agent = _make_agent(
            "TestAgent", agent_class="coordinator", delegation_scope="local",
            interrupt_policy="before_phase_exit", escalation_policy="hil_for_band2"
        )
        d = agent.to_dict()
        assert d["agent_class"] == "coordinator"
        assert d["delegation_scope"] == "local"
        assert d["interrupt_policy"] == "before_phase_exit"
        assert d["escalation_policy"] == "hil_for_band2"
        assert "allowed_peer_targets" in d
        assert "handoff_policy" in d

    def test_memory_scope_rank_phase(self):
        from apps.backend.src.core.praison_agent import AgentIdentity
        agent = AgentIdentity(
            agent_id="X", persona="X", description="X", system_prompt="X",
            memory_scope="phase"
        )
        assert agent.memory_scope_rank == 1

    def test_memory_scope_rank_mission(self):
        from apps.backend.src.core.praison_agent import AgentIdentity
        agent = AgentIdentity(
            agent_id="X", persona="X", description="X", system_prompt="X",
            memory_scope="mission"
        )
        assert agent.memory_scope_rank == 3

    def test_can_write_to_lower_scope(self):
        agent = _make_agent(memory_scope="mission")
        assert agent.can_write_to_scope("session") is True
        assert agent.can_write_to_scope("phase") is True
        assert agent.can_write_to_scope("workflow") is True
        assert agent.can_write_to_scope("mission") is True
        assert agent.can_write_to_scope("persistent") is False

    def test_delegation_authority_property(self):
        coordinator = _make_coordinator()
        authority = coordinator.delegation_authority
        assert "specialist" in authority
        assert "coordinator" not in authority


# ── praison_contracts.py tests ───────────────────────────────────────────────

class TestDelegationContract:
    def test_create_contract_coordinator_to_specialist(self):
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coordinator = _make_coordinator()  # no peer target restriction
        specialist = _make_agent("Spec1", agent_class="specialist", delegation_scope="none")
        contract = create_delegation_contract(
            coordinator, specialist, objective="Scan targets"
        )
        assert contract.delegator_id == "Coordinator"
        assert contract.delegate_id == "Spec1"
        assert contract.objective == "Scan targets"
        assert contract.workflow_id == "wf-test"

    def test_create_contract_fails_if_no_authority(self):
        from apps.backend.src.core.praison_contracts import (
            ContractValidationError,
            create_delegation_contract,
        )
        specialist = _make_agent("Spec1", agent_class="specialist")
        specialist2 = _make_agent("Spec2", agent_class="specialist")
        with pytest.raises(ContractValidationError, match="cannot delegate"):
            create_delegation_contract(specialist, specialist2, objective="test")

    def test_create_contract_fails_if_delegation_scope_none(self):
        from apps.backend.src.core.praison_contracts import (
            ContractValidationError,
            create_delegation_contract,
        )
        coordinator = _make_coordinator()
        # coordinator with delegation_scope=none cannot delegate
        coordinator_no_deleg = _make_agent("NoDelegCoord", agent_class="coordinator", delegation_scope="none")
        specialist = _make_agent("Spec", agent_class="specialist")
        with pytest.raises(ContractValidationError, match="delegation_scope=none"):
            create_delegation_contract(coordinator_no_deleg, specialist, objective="test")

    def test_contract_lifecycle_pending_active_complete(self):
        from apps.backend.src.core.praison_contracts import (
            ContractState,
            create_delegation_contract,
        )
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist")
        contract = create_delegation_contract(coord, spec, objective="Execute recon")
        assert contract.state == ContractState.PENDING

        active = contract.activate()
        assert active.state == ContractState.ACTIVE
        assert active.activated_at is not None

        done = active.complete(artifact_id="art-123")
        assert done.state == ContractState.COMPLETED
        assert done.result_artifact_id == "art-123"
        assert done.is_terminal is True

    def test_contract_revoke(self):
        from apps.backend.src.core.praison_contracts import (
            ContractState,
            create_delegation_contract,
        )
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist")
        contract = create_delegation_contract(coord, spec, objective="test").activate()
        revoked = contract.revoke()
        assert revoked.state == ContractState.REVOKED
        assert revoked.is_terminal is True

    def test_contract_mark_violated(self):
        from apps.backend.src.core.praison_contracts import (
            ContractState,
            ContractViolation,
            create_delegation_contract,
        )
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist")
        contract = create_delegation_contract(coord, spec, objective="test").activate()
        violated = contract.mark_violated(ContractViolation.TOOL_NOT_ALLOWED, "used nmap without auth")
        assert violated.state == ContractState.VIOLATED
        assert violated.violation == ContractViolation.TOOL_NOT_ALLOWED
        assert "nmap" in violated.violation_detail

    def test_contract_tool_allowed(self):
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist", allowed_tools=["nmap", "nuclei"])
        contract = create_delegation_contract(
            coord, spec, objective="test", allowed_tools=["nmap"]
        )
        assert contract.tool_allowed("nmap") is True
        assert contract.tool_allowed("nuclei") is False
        assert contract.tool_allowed("ffuf") is False

    def test_contract_tool_allowed_empty_means_deny_all(self):
        """SEMANTICS FIX (Phase 3.5): empty allowed_tools = NO tools permitted."""
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist", allowed_tools=["nmap"])
        contract = create_delegation_contract(coord, spec, objective="test", allowed_tools=[])
        # empty allowed_tools tuple = deny all (not permit all)
        assert contract.tool_allowed("nmap") is False
        assert contract.tool_allowed("anything") is False

    def test_cannot_grant_tools_not_in_delegate_allowed_tools(self):
        from apps.backend.src.core.praison_contracts import (
            ContractValidationError,
            create_delegation_contract,
        )
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist", allowed_tools=["nmap"])
        with pytest.raises(ContractValidationError, match="not in delegate's allowed_tools"):
            create_delegation_contract(coord, spec, objective="test", allowed_tools=["sqlmap"])

    def test_invalid_state_transition_raises(self):
        from apps.backend.src.core.praison_contracts import (
            ContractStateError,
            create_delegation_contract,
        )
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist")
        contract = create_delegation_contract(coord, spec, objective="test")
        with pytest.raises(ContractStateError):
            contract.complete()  # can't complete a PENDING contract

    def test_contract_to_dict(self):
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist")
        contract = create_delegation_contract(coord, spec, objective="test")
        d = contract.to_dict()
        assert d["delegator_id"] == "Coordinator"
        assert d["delegate_id"] == "S"
        assert d["state"] == "pending"
        assert "contract_id" in d
        assert "created_at" in d


# ── praison_artifacts.py tests ───────────────────────────────────────────────

class TestAgentArtifact:
    def test_make_recon_surface(self):
        from apps.backend.src.core.praison_artifacts import (
            ArtifactType,
            make_recon_surface,
        )
        artifact = make_recon_surface(
            "SurfaceMapper",
            hosts=["host1.example.com", "host2.example.com"],
            endpoints=["/api/v1", "/admin"],
            technologies=["nginx", "react"],
            workflow_id="wf-1",
            program_id="prog-1",
        )
        assert artifact.artifact_type == ArtifactType.RECON_SURFACE
        assert artifact.producer_id == "SurfaceMapper"
        assert "host1.example.com" in artifact.content["hosts"]
        assert artifact.memory_scope == "workflow"

    def test_make_vulnerability_signal_critical_sets_flags(self):
        from apps.backend.src.core.praison_artifacts import (
            ArtifactType,
            make_vulnerability_signal,
        )
        artifact = make_vulnerability_signal(
            "ReconSpecialist",
            target="admin.example.com",
            signal_type="sqli",
            severity="critical",
            evidence={"payload": "' OR 1=1"},
            workflow_id="wf-1",
            program_id="prog-1",
        )
        assert artifact.requires_human_review is True
        assert artifact.requires_governance_approval is True
        assert artifact.blocking is True

    def test_make_governance_decision(self):
        from apps.backend.src.core.praison_artifacts import (
            ArtifactType,
            make_governance_decision,
        )
        artifact = make_governance_decision(
            "GovernanceDirector",
            approved=True,
            reason="Scope confirmed, risk acceptable",
            subject_artifact_id="art-123",
            workflow_id="wf-1",
            program_id="prog-1",
        )
        assert artifact.artifact_type == ArtifactType.GOVERNANCE_DECISION
        assert artifact.content["approved"] is True
        assert artifact.blocking is True

    def test_artifact_annotate_adds_tags(self):
        from apps.backend.src.core.praison_artifacts import make_recon_surface
        artifact = make_recon_surface(
            "SM", hosts=["h.example.com"], endpoints=[], technologies=[],
            workflow_id="wf-1", program_id="prog-1",
        )
        annotated = artifact.annotate(consumer_id="EvidenceAnalyst", tags=["phase_complete"])
        assert annotated.consumer_id == "EvidenceAnalyst"
        assert "phase_complete" in annotated.tags
        # original unchanged
        assert artifact.consumer_id == ""

    def test_artifact_forward_creates_new_id(self):
        from apps.backend.src.core.praison_artifacts import make_recon_surface
        artifact = make_recon_surface(
            "SM", hosts=[], endpoints=[], technologies=[],
            workflow_id="wf-1", program_id="prog-1",
        )
        forwarded = artifact.forward("EvidenceAnalyst")
        assert forwarded.artifact_id != artifact.artifact_id
        assert forwarded.consumer_id == "EvidenceAnalyst"

    def test_artifact_store_put_and_get(self):
        from apps.backend.src.core.praison_artifacts import (
            ArtifactStore,
            make_recon_surface,
        )
        store = ArtifactStore()
        artifact = make_recon_surface(
            "SM", hosts=["h.example.com"], endpoints=[], technologies=[],
            workflow_id="wf-test-store", program_id="prog-1",
        )
        store.put(artifact)
        retrieved = store.get(artifact.artifact_id)
        assert retrieved is not None
        assert retrieved.artifact_id == artifact.artifact_id

    def test_artifact_store_list_for_workflow(self):
        from apps.backend.src.core.praison_artifacts import (
            ArtifactStore,
            ArtifactType,
            make_recon_surface,
            make_vulnerability_signal,
        )
        store = ArtifactStore()
        wf = f"wf-{uuid.uuid4().hex[:8]}"
        art1 = make_recon_surface("SM", hosts=[], endpoints=[], technologies=[], workflow_id=wf, program_id="p")
        art2 = make_vulnerability_signal("RS", target="t", signal_type="xss", severity="medium",
                                          evidence={}, workflow_id=wf, program_id="p")
        store.put(art1)
        store.put(art2)
        results = store.list_for_workflow(wf)
        assert len(results) == 2
        surface_only = store.list_for_workflow(wf, artifact_type=ArtifactType.RECON_SURFACE)
        assert len(surface_only) == 1


# ── praison_runtime_policy.py tests ──────────────────────────────────────────

class TestPraisonRuntimePolicy:
    def setup_method(self):
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        self.policy = PraisonRuntimePolicy()

    def test_coordinator_can_delegate_to_specialist(self):
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist")
        decision = self.policy.check_delegation(coord, spec)
        assert decision.allowed is True

    def test_specialist_cannot_delegate(self):
        spec1 = _make_agent("S1", agent_class="specialist")
        spec2 = _make_agent("S2", agent_class="specialist")
        decision = self.policy.check_delegation(spec1, spec2)
        assert decision.allowed is False
        # specialists have delegation_scope=none — caught by scope check first
        assert decision.reason != ""

    def test_agent_with_no_delegation_scope_blocked(self):
        coord = _make_agent("C", agent_class="coordinator", delegation_scope="none")
        spec = _make_agent("S", agent_class="specialist")
        decision = self.policy.check_delegation(coord, spec)
        assert decision.allowed is False
        assert "delegation_scope=none" in decision.reason

    def test_no_interrupt_policy_permits(self):
        agent = _make_agent(interrupt_policy="none")
        decision = self.policy.check_interrupt_before(agent)
        assert decision.allowed is True

    def test_strict_review_policy_requires_interrupt(self):
        agent = _make_agent(agent_class="governor", delegation_scope="global",
                            review_policy="strict", interrupt_policy="before_sensitive_tools")
        decision = self.policy.check_interrupt_before(agent)
        assert decision.allowed is False

    def test_interrupt_event_sensitive_tool(self):
        agent = _make_agent(interrupt_policy="before_sensitive_tools", review_policy="standard")
        decision = self.policy.check_interrupt_for_event(agent, "sensitive_tool")
        assert decision.allowed is False

    def test_interrupt_event_not_triggered_wrong_type(self):
        agent = _make_agent(interrupt_policy="before_sensitive_tools")
        decision = self.policy.check_interrupt_for_event(agent, "phase_exit")
        assert decision.allowed is True

    def test_escalation_hil_for_band2(self):
        agent = _make_agent(escalation_policy="hil_for_band2")
        decision = self.policy.check_escalation(agent, "band2_tool")
        assert decision.allowed is True
        assert decision.requires_escalation is True

    def test_escalation_not_triggered_wrong_event(self):
        agent = _make_agent(escalation_policy="hil_for_band2")
        decision = self.policy.check_escalation(agent, "scope_expansion")
        assert decision.requires_escalation is False

    def test_memory_write_within_scope(self):
        agent = _make_agent(memory_scope="workflow", workflow_id="wf1", program_id="p1")
        decision = self.policy.check_memory_write(agent, "session")
        assert decision.allowed is True

    def test_memory_write_above_scope_blocked(self):
        agent = _make_agent(memory_scope="session")
        decision = self.policy.check_memory_write(agent, "workflow")
        assert decision.allowed is False

    def test_memory_write_size_limit(self):
        agent = _make_agent(memory_scope="workflow")
        decision = self.policy.check_memory_write(agent, "session", data_bytes=2_000_000, max_bytes=1_000_000)
        assert decision.allowed is False
        assert "exceeds limit" in decision.reason

    def test_persistent_scope_requires_context(self):
        agent = _make_agent(memory_scope="persistent", workflow_id="", program_id="")
        decision = self.policy.check_memory_write(agent, "persistent")
        assert decision.allowed is False
        assert "require workflow_id" in decision.reason

    def test_validate_identity_valid_agent(self):
        agent = _make_agent(
            agent_class="coordinator", delegation_scope="local",
            handoff_policy="coordinator_visible", interrupt_policy="none",
            escalation_policy="hil_for_band2",
        )
        errors = self.policy.validate_identity(agent)
        assert errors == []

    def test_validate_identity_specialist_with_delegation_scope(self):
        agent = _make_agent(agent_class="specialist", delegation_scope="local")
        errors = self.policy.validate_identity(agent)
        assert any("delegation_scope=none" in e for e in errors)

    def test_contract_tool_check_active_contract(self):
        from apps.backend.src.core.praison_contracts import create_delegation_contract
        coord = _make_coordinator()
        spec = _make_agent("S", agent_class="specialist", allowed_tools=["nmap"])
        contract = create_delegation_contract(coord, spec, objective="test", allowed_tools=["nmap"])
        active = contract.activate()
        decision = self.policy.check_tool_under_contract(active, "nmap")
        assert decision.allowed is True
        decision_denied = self.policy.check_tool_under_contract(active, "sqlmap")
        assert decision_denied.allowed is False


# ── praison_topology.py tests ─────────────────────────────────────────────────

class TestPraisonTopology:
    def test_node_spec_from_langgraph_spec(self):
        from apps.backend.src.core.praison_topology import NodeSpec
        spec = {
            "node_id": "TestAgent",
            "node_type": "agent",
            "risk_profile": "recon",
            "memory_scope": "phase",
            "allowed_tools": ["nmap"],
            "interrupt_policy": {"interrupt_before": True, "interrupt_after": False},
        }
        node = NodeSpec.from_langgraph_spec(spec, cluster_id="cluster-1")
        assert node.node_id == "TestAgent"
        assert node.interrupt_before is True
        assert node.cluster_id == "cluster-1"

    def test_mission_graph_spec_add_node_and_edge(self):
        from apps.backend.src.core.praison_topology import (
            EdgeCondition,
            MissionGraphSpec,
            NodeSpec,
        )
        graph = MissionGraphSpec(workflow_id="wf-1", program_id="p-1")
        n1 = NodeSpec(node_id="A", agent_id="A", node_type="governance", is_entry=True)
        n2 = NodeSpec(node_id="B", agent_id="B", node_type="agent", is_exit=True)
        graph.add_node(n1).add_node(n2)
        graph.add_edge("A", "B", condition=EdgeCondition.ON_APPROVAL)

        assert "A" in graph.nodes
        assert "B" in graph.nodes
        assert graph.entry_node == "A"
        assert graph.exit_node == "B"
        assert len(graph.outgoing_edges("A")) == 1
        assert graph.outgoing_edges("A")[0].condition == EdgeCondition.ON_APPROVAL

    def test_governance_nodes_filter(self):
        from apps.backend.src.core.praison_topology import MissionGraphSpec, NodeSpec
        graph = MissionGraphSpec(workflow_id="wf-1", program_id="p-1")
        graph.add_node(NodeSpec(node_id="Gov", agent_id="Gov", node_type="governance"))
        graph.add_node(NodeSpec(node_id="Agent", agent_id="Agent", node_type="agent"))
        gov_nodes = graph.governance_nodes()
        assert len(gov_nodes) == 1
        assert gov_nodes[0].node_id == "Gov"

    def test_cluster_spec_all_node_ids(self):
        from apps.backend.src.core.praison_topology import ClusterSpec
        cluster = ClusterSpec(
            cluster_name="recon",
            phase="recon",
            coordinator_id="PhaseCoordinator",
            specialist_ids=["SurfaceMapper", "ReconSpecialist"],
        )
        all_ids = cluster.all_node_ids
        assert "PhaseCoordinator" in all_ids
        assert "SurfaceMapper" in all_ids
        assert "ReconSpecialist" in all_ids

    def test_build_standard_bug_bounty_topology(self):
        from apps.backend.src.core.praison_topology import PraisonTopology
        agent_specs = {
            agent_id: {
                "node_id": agent_id,
                "node_type": "agent",
                "risk_profile": "standard",
                "memory_scope": "session",
                "allowed_tools": [],
                "interrupt_policy": {"interrupt_before": False, "interrupt_after": False},
            }
            for agent_id in [
                "GovernanceDirector", "MissionDirector", "PhaseCoordinator",
                "SurfaceMapper", "ReconSpecialist", "EvidenceAnalyst",
                "ReportSynthesisAgent", "HandoffLiaison",
            ]
        }
        graph = PraisonTopology.build_standard_bug_bounty("wf-1", "prog-1", agent_specs)
        assert graph.workflow_id == "wf-1"
        assert len(graph.nodes) == 8
        assert len(graph.edges) > 0
        assert len(graph.clusters) == 1


# ── praison_langgraph_builder.py tests ───────────────────────────────────────

class TestPraisonLangGraphBuilder:
    def _make_graph_spec(self):
        from apps.backend.src.core.praison_topology import (
            EdgeCondition,
            MissionGraphSpec,
            NodeSpec,
        )
        graph = MissionGraphSpec(workflow_id="wf-1", program_id="p-1")
        n1 = NodeSpec(node_id="Gov", agent_id="Gov", node_type="governance",
                      is_entry=True, interrupt_before=True)
        n2 = NodeSpec(node_id="Worker", agent_id="Worker", node_type="agent", is_exit=True)
        graph.add_node(n1).add_node(n2)
        graph.add_edge("Gov", "Worker", condition=EdgeCondition.ALWAYS)
        return graph

    def test_build_scaffold_spec_no_langgraph(self):
        from apps.backend.src.core.praison_langgraph_builder import PraisonLangGraphBuilder
        spec = self._make_graph_spec()
        builder = PraisonLangGraphBuilder(spec, {})
        scaffold = builder.build_scaffold_spec()
        assert scaffold["workflow_id"] == "wf-1"
        assert len(scaffold["nodes"]) == 2
        assert len(scaffold["edges"]) == 1
        assert "Gov" in scaffold["interrupt_before"]
        assert isinstance(scaffold["langgraph_available"], bool)

    def test_compile_returns_none_when_langgraph_unavailable(self):
        from apps.backend.src.core.praison_langgraph_builder import (
            PraisonLangGraphBuilder,
            _LANGGRAPH_AVAILABLE,
        )
        if _LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph is installed — scaffold-only test not applicable")
        spec = self._make_graph_spec()
        builder = PraisonLangGraphBuilder(spec, {})
        result = builder.compile()
        assert result is None


# ── praison_registry.py tests ─────────────────────────────────────────────────

MINIMAL_YAML = """
agents:
  TestAgent:
    persona: "Test Persona"
    description: "A test agent"
    system_prompt: "You are a test agent."
    risk_profile: standard
    memory_scope: session
    review_policy: standard
    agent_class: specialist
    delegation_scope: none
    allowed_peer_targets: []
    handoff_policy: coordinator_visible
    interrupt_policy: none
    escalation_policy: hil_for_band2
"""

INVALID_AGENT_CLASS_YAML = """
agents:
  BadAgent:
    persona: "Bad Agent"
    description: "Bad"
    system_prompt: "Bad"
    agent_class: overlord
    delegation_scope: none
"""

SPECIALIST_WITH_DELEGATION_YAML = """
agents:
  BadSpec:
    persona: "Bad Specialist"
    description: "Bad"
    system_prompt: "Bad"
    agent_class: specialist
    delegation_scope: local
"""


class TestPraisonRegistryExtended:
    def _registry_from_yaml(self, yaml_str: str, tmp_path):
        p = tmp_path / "agents.yaml"
        p.write_text(yaml_str)
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        reg = PraisonAgentRegistry(str(p))
        return reg

    def test_load_minimal_valid_agent(self, tmp_path):
        reg = self._registry_from_yaml(MINIMAL_YAML, tmp_path)
        reg.load_agents()
        agent = reg.get_agent("TestAgent")
        assert agent.agent_class == "specialist"
        assert agent.delegation_scope == "none"
        assert agent.interrupt_policy == "none"
        assert agent.escalation_policy == "hil_for_band2"

    def test_invalid_agent_class_raises(self, tmp_path):
        reg = self._registry_from_yaml(INVALID_AGENT_CLASS_YAML, tmp_path)
        with pytest.raises(RuntimeError, match="agent_class"):
            reg.load_agents()

    def test_specialist_with_delegation_scope_raises(self, tmp_path):
        reg = self._registry_from_yaml(SPECIALIST_WITH_DELEGATION_YAML, tmp_path)
        with pytest.raises(RuntimeError, match="delegation_scope"):
            reg.load_agents()

    def test_load_full_agents_yaml(self):
        """Load the actual agents.yaml and verify all 11 agents load without error."""
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        reg = PraisonAgentRegistry()
        reg.load_agents()
        ids = reg.agent_ids()
        expected = {
            "SecurityGovernorAgent", "GovernanceDirector", "MissionDirector",
            "PhaseCoordinator", "InterscanReportAgent", "HandoffAgent",
            "HandoffLiaison", "SurfaceMapper", "ReconSpecialist",
            "EvidenceAnalyst", "ReportSynthesisAgent",
        }
        for agent_id in expected:
            assert agent_id in ids, f"{agent_id} not loaded from agents.yaml"

    def test_governance_agents_have_correct_class(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        reg = PraisonAgentRegistry()
        reg.load_agents()
        for agent_id in ("SecurityGovernorAgent", "GovernanceDirector"):
            agent = reg.get_agent(agent_id)
            assert agent.agent_class == "governor", f"{agent_id} should be governor class"

    def test_specialists_have_delegation_scope_none(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        reg = PraisonAgentRegistry()
        reg.load_agents()
        for agent_id in ("SurfaceMapper", "ReconSpecialist", "EvidenceAnalyst", "ReportSynthesisAgent"):
            agent = reg.get_agent(agent_id)
            assert agent.delegation_scope == "none", f"{agent_id} should have delegation_scope=none"

    def test_all_agents_have_valid_policy_fields(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
        reg = PraisonAgentRegistry()
        reg.load_agents()
        policy = PraisonRuntimePolicy()
        for agent_id in reg.agent_ids():
            agent = reg.get_agent(agent_id)
            errors = policy.validate_identity(agent)
            assert errors == [], f"{agent_id} has policy errors: {errors}"


# ── Integration: contract + runtime policy ────────────────────────────────────

class TestContractRuntimePolicyIntegration:
    def test_full_delegation_lifecycle(self):
        """Director → Coordinator → Specialist contract chain."""
        from apps.backend.src.core.praison_contracts import (
            ContractState,
            create_delegation_contract,
            validate_contract,
        )
        from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy

        policy = PraisonRuntimePolicy()
        director = _make_director()
        coordinator = _make_coordinator()
        specialist = _make_agent("Spec", agent_class="specialist")

        # Director → Coordinator
        dir_decision = policy.check_delegation(director, coordinator)
        assert dir_decision.allowed is True
        dir_contract = create_delegation_contract(
            director, coordinator, objective="Execute recon phase"
        )
        validate_contract(dir_contract)
        dir_active = dir_contract.activate()
        assert dir_active.state == ContractState.ACTIVE

        # Coordinator → Specialist
        coord_decision = policy.check_delegation(coordinator, specialist)
        assert coord_decision.allowed is True
        spec_contract = create_delegation_contract(
            coordinator, specialist, objective="Map attack surface"
        )
        validate_contract(spec_contract)
        spec_active = spec_contract.activate()
        assert spec_active.state == ContractState.ACTIVE

        # Specialist completes
        spec_done = spec_active.complete("art-001")
        assert spec_done.state == ContractState.COMPLETED

    def test_specialist_cannot_sub_delegate(self):
        """Specialists may not create contracts even if marked can_sub_delegate."""
        from apps.backend.src.core.praison_contracts import (
            ContractValidationError,
            create_delegation_contract,
        )
        spec = _make_agent("Spec", agent_class="specialist")
        spec2 = _make_agent("Spec2", agent_class="specialist")
        with pytest.raises(ContractValidationError):
            create_delegation_contract(spec, spec2, objective="test")
