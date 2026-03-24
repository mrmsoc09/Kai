from __future__ import annotations

import pytest

from apps.backend.src.routers.mission_control import _build_graph_spec


def test_build_graph_spec_from_payload_defaults_entry_and_exit() -> None:
    payload = {
        "nodes": [
            {"node_id": "GovernanceDirector", "node_type": "governance", "is_entry": True},
            {"node_id": "MissionDirector", "node_type": "coordinator", "is_exit": True},
        ],
        "edges": [
            {"source": "GovernanceDirector", "target": "MissionDirector", "condition": "always"},
        ],
    }

    graph_spec = _build_graph_spec(
        payload,
        default_workflow_id="wf-default",
        default_program_id="program-default",
        mission_name="Graph Spec Test",
    )

    assert graph_spec.workflow_id == "wf-default"
    assert graph_spec.program_id == "program-default"
    assert graph_spec.entry_node == "GovernanceDirector"
    assert graph_spec.exit_node == "MissionDirector"
    assert len(graph_spec.nodes) == 2
    assert len(graph_spec.edges) == 1


def test_build_graph_spec_rejects_edge_with_unknown_node() -> None:
    payload = {
        "nodes": [
            {"node_id": "GovernanceDirector", "node_type": "governance"},
        ],
        "edges": [
            {"source": "GovernanceDirector", "target": "UnknownNode", "condition": "always"},
        ],
    }

    with pytest.raises(ValueError, match="unknown node"):
        _build_graph_spec(
            payload,
            default_workflow_id="wf-default",
            default_program_id="program-default",
            mission_name="Graph Spec Invalid",
        )

