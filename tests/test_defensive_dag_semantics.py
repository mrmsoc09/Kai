from __future__ import annotations

from fastapi import FastAPI
from tests.asgi_test_client import ASGITestClient

from apps.backend.src.core.orchestration_graph import HuntPhase, OrchestrationGraph
from apps.backend.src.routers import orchestration


def test_orchestration_phases_are_defensive_only():
    values = {p.value for p in HuntPhase}
    assert "exploitation" not in values
    assert "signal_validation" in values


def test_orchestration_graph_transition_path():
    graph = OrchestrationGraph("s1", "example.com", "defensive mission")
    assert graph.transitions[HuntPhase.ANALYSIS] == [HuntPhase.SIGNAL_VALIDATION, HuntPhase.REPORTING]


def test_router_rejects_non_defensive_action_type():
    app = FastAPI()
    app.include_router(orchestration.router)
    client = ASGITestClient(app)

    create = client.post(
        "/api/orchestration/sessions",
        json={"target_domain": "example.com", "mission_statement": "defensive"},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    bad = client.post(
        f"/api/orchestration/sessions/{session_id}/plan",
        json={
            "action_type": "exploitation",
            "target": "example.com",
            "description": "exploit target",
            "expected_outcome": "none",
            "risk_level": "high",
            "requires_approval": True,
        },
    )
    assert bad.status_code == 400
