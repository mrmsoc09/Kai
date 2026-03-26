from __future__ import annotations

from apps.backend.src.core.praison_node_executors import build_standard_node_callables
from apps.backend.src.core.praison_topology import PraisonTopology


def _spec(node_id: str) -> dict[str, str]:
    return {
        "node_id": node_id,
        "node_type": "agent",
        "agent_class": "specialist",
        "risk_profile": "standard",
        "review_policy": "standard",
        "memory_scope": "session",
        "system_prompt": f"Agent {node_id}",
    }


def test_standard_node_callables_include_aliases():
    callables = build_standard_node_callables()
    for required in (
        "GovernanceDirector",
        "GovernanceReview",
        "SecurityGovernorAgent",
        "PhaseCoordinator",
        "ScanningCoordinator",
        "TriageAnalyst",
        "HandoffAgent",
    ):
        assert required in callables


def test_topology_uses_separate_governance_review_node():
    agent_specs = {
        "GovernanceDirector": _spec("GovernanceDirector"),
        "MissionDirector": _spec("MissionDirector"),
        "PhaseCoordinator": _spec("PhaseCoordinator"),
        "SurfaceMapper": _spec("SurfaceMapper"),
        "ReconSpecialist": _spec("ReconSpecialist"),
        "EvidenceAnalyst": _spec("EvidenceAnalyst"),
        "ReportSynthesisAgent": _spec("ReportSynthesisAgent"),
        "HandoffLiaison": _spec("HandoffLiaison"),
    }

    graph = PraisonTopology.build_standard_bug_bounty(
        workflow_id="wf-1",
        program_id="example.com",
        agent_specs=agent_specs,
    )

    assert "GovernanceReview" in graph.nodes

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("GovernanceDirector", "MissionDirector") in edges
    assert ("GovernanceReview", "ReportSynthesisAgent") in edges
    assert ("GovernanceDirector", "ReportSynthesisAgent") not in edges
