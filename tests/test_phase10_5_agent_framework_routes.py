from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import apps.backend.src.routers.bug_bounty as bug_bounty_router
from apps.backend.src.core.hil_db import get_db
from apps.backend.src.main import app


def _agent_row():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        agent_id="scope_parsing_agent",
        agent_name="Scope Parsing Agent",
        agent_role="scope_parsing_agent",
        category="recon_discovery",
        purpose="Parse scope target identifiers.",
        allowed_tools_json=["scope_resolver"],
        forbidden_tools_json=["sqlmap"],
        input_schema_reference="phase10_5.scope_parsing_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-small",
        model_runtime="self_hosted",
        confidence_threshold=0.75,
        max_runtime_seconds=30,
        retry_policy_json={"max_retries": 1},
        escalation_agent_id="analyst_briefing_agent",
        enabled=True,
        safety_notes="read-only",
        observability_tags_json=["scope", "phase10_5"],
        details_json={},
        created_at=now,
        updated_at=now,
    )


def _execution_row(program_id, scope_target_id):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        agent_registry_id=uuid4(),
        agent_id="scope_parsing_agent",
        program_id=program_id,
        scope_target_id=scope_target_id,
        workflow_run_id=None,
        analyst_case_id=None,
        analyst_queue_item_id=None,
        input_ref=None,
        input_hash="hash",
        output_json={"status": "SUCCEEDED", "confidence": 0.88},
        model_used="kai/selfhosted-small",
        routing_policy="self_hosted_default",
        confidence=0.88,
        execution_status="SUCCEEDED",
        failure_reason=None,
        escalation_taken=False,
        escalation_agent_id=None,
        started_at=now,
        finished_at=now,
        duration_ms=42,
        log_path=None,
        artifact_refs_json=[],
        details_json={},
        created_at=now,
        updated_at=now,
    )


def _evaluation_row():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        agent_registry_id=uuid4(),
        agent_id="scope_parsing_agent",
        benchmark_name="default",
        model_used="kai/selfhosted-small",
        fixture_count=1,
        passed_count=1,
        failed_count=0,
        avg_confidence=0.88,
        avg_latency_ms=28,
        success_rate=1.0,
        status="PASSED",
        results_json={"fixtures": [{"ok": True}]},
        run_by="test.phase10_5",
        run_reason="test",
        executed_at=now,
        created_at=now,
        updated_at=now,
    )


def test_phase10_5_agent_routes(client, monkeypatch):
    agent = _agent_row()
    program_id = uuid4()
    scope_target_id = uuid4()
    execution = _execution_row(program_id, scope_target_id)
    evaluation = _evaluation_row()

    class _FakeService:
        def __init__(self, _db):
            pass

        async def sync_registry(self, *, actor):
            assert actor
            return {"created": 1, "updated": 0, "total": 11}

        async def list_agents(self, *, enabled_only=False, category=None, limit=200):
            assert limit == 200
            _ = enabled_only
            _ = category
            return [agent]

        async def get_agent(self, agent_id):
            if agent_id == "scope_parsing_agent":
                return agent
            return None

        async def list_executions(self, *, program_id=None, agent_id=None, execution_status=None, limit=500):
            assert limit == 500
            _ = program_id
            _ = agent_id
            _ = execution_status
            return [execution]

        async def list_evaluations(self, *, agent_id=None, status=None, limit=500):
            assert limit == 500
            _ = agent_id
            _ = status
            return [evaluation]

        async def run_agent(self, **kwargs):
            assert kwargs["agent_id"] == "scope_parsing_agent"
            return execution

        async def evaluate_agent(self, *, agent_id, actor, benchmark_name):
            assert agent_id == "scope_parsing_agent"
            assert actor
            assert benchmark_name == "default"
            return evaluation

    async def _override_db():
        yield object()

    monkeypatch.setattr(bug_bounty_router, "Phase10_5AgentFrameworkService", _FakeService)
    app.dependency_overrides[get_db] = _override_db
    try:
        sync_response = client.post("/api/v1/bug-bounty/agents/sync")
        assert sync_response.status_code == 200
        assert sync_response.json()["total"] == 11

        list_response = client.get("/api/v1/bug-bounty/agents")
        assert list_response.status_code == 200
        assert list_response.json()[0]["agent_id"] == "scope_parsing_agent"

        get_response = client.get("/api/v1/bug-bounty/agents/scope_parsing_agent")
        assert get_response.status_code == 200
        assert get_response.json()["agent_name"] == "Scope Parsing Agent"

        executions_response = client.get("/api/v1/bug-bounty/agents/executions")
        assert executions_response.status_code == 200
        assert executions_response.json()[0]["execution_status"] == "SUCCEEDED"

        evaluations_response = client.get("/api/v1/bug-bounty/agents/evaluations")
        assert evaluations_response.status_code == 200
        assert evaluations_response.json()[0]["status"] == "PASSED"

        run_response = client.post(
            "/api/v1/bug-bounty/agents/scope_parsing_agent/run",
            json={
                "actor": "test.phase10_5",
                "program_id": str(program_id),
                "scope_target_id": str(scope_target_id),
                "input_payload": {"target_identifier": "example.org"},
            },
        )
        assert run_response.status_code == 200
        assert run_response.json()["agent_id"] == "scope_parsing_agent"

        evaluate_response = client.post(
            "/api/v1/bug-bounty/agents/scope_parsing_agent/evaluate",
            json={"actor": "test.phase10_5", "benchmark_name": "default"},
        )
        assert evaluate_response.status_code == 200
        assert evaluate_response.json()["benchmark_name"] == "default"
    finally:
        app.dependency_overrides.pop(get_db, None)
