from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.backend.src.core.phase10_5_agent_framework_service import (
    FIRST_WAVE_AGENT_DEFINITIONS,
    Phase10_5AgentFrameworkService,
)


class _DummyDB:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:  # pragma: no cover - trivial async shim
        return None


@pytest.mark.asyncio
async def test_phase10_5_run_agent_escalates_when_confidence_below_threshold():
    service = Phase10_5AgentFrameworkService(db=object())  # type: ignore[arg-type]

    async def _fake_get_agent(_agent_id: str):
        return SimpleNamespace(
            id=uuid4(),
            agent_id="scope_parsing_agent",
            enabled=True,
            confidence_threshold=0.75,
            escalation_agent_id="analyst_briefing_agent",
        )

    async def _fake_resolve_program_context(**_kwargs):
        return uuid4(), None

    async def _fake_execute_logic(**_kwargs):
        return {
            "status": "SUCCEEDED",
            "confidence": 0.41,
            "reasoning_summary": "low confidence",
            "key_observations": [],
            "suggested_next_action": "defer",
            "supporting_evidence_refs": [],
            "failure_reason": None,
            "escalation_recommended": False,
            "data": {},
        }

    service.get_agent = _fake_get_agent  # type: ignore[method-assign]
    service._resolve_program_context = _fake_resolve_program_context  # type: ignore[method-assign]
    service._execute_logic = _fake_execute_logic  # type: ignore[method-assign]

    output = await service.run_agent(
        agent_id="scope_parsing_agent",
        actor="test.phase10_5",
        input_payload={"target_identifier": "example.org"},
        program_id=uuid4(),
        persist_record=False,
    )

    assert output["status"] == "ESCALATED"
    assert output["escalation_recommended"] is True
    assert "confidence" in output


@pytest.mark.asyncio
async def test_phase10_5_run_agent_validates_required_input_fields():
    service = Phase10_5AgentFrameworkService(db=object())  # type: ignore[arg-type]

    async def _fake_get_agent(_agent_id: str):
        return SimpleNamespace(
            id=uuid4(),
            agent_id="scope_parsing_agent",
            enabled=True,
            confidence_threshold=0.75,
            escalation_agent_id=None,
        )

    service.get_agent = _fake_get_agent  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="Missing required input fields"):
        await service.run_agent(
            agent_id="scope_parsing_agent",
            actor="test.phase10_5",
            input_payload={},
            program_id=uuid4(),
            persist_record=False,
        )


@pytest.mark.asyncio
async def test_phase10_5_evaluate_agent_persists_evaluation_record(monkeypatch):
    dummy_db = _DummyDB()
    service = Phase10_5AgentFrameworkService(db=dummy_db)  # type: ignore[arg-type]

    async def _fake_get_agent(_agent_id: str):
        return SimpleNamespace(
            id=uuid4(),
            agent_id="scope_parsing_agent",
            enabled=True,
            confidence_threshold=0.5,
            escalation_agent_id=None,
        )

    async def _fake_run_agent(**_kwargs):
        return {
            "status": "SUCCEEDED",
            "confidence": 0.88,
            "reasoning_summary": "fixture passed",
            "key_observations": [],
            "suggested_next_action": "continue",
            "supporting_evidence_refs": [],
            "failure_reason": None,
            "escalation_recommended": False,
            "data": {},
        }

    async def _fake_record_transition_event(*_args, **_kwargs):
        return None

    service.get_agent = _fake_get_agent  # type: ignore[method-assign]
    service.run_agent = _fake_run_agent  # type: ignore[method-assign]
    monkeypatch.setattr(
        "apps.backend.src.core.phase10_5_agent_framework_service.record_transition_event",
        _fake_record_transition_event,
    )

    evaluation = await service.evaluate_agent(
        agent_id="scope_parsing_agent",
        actor="test.phase10_5",
        benchmark_name="default",
    )

    assert evaluation.status == "PASSED"
    assert evaluation.success_rate == 1.0
    assert dummy_db.added


def test_phase10_5_agent_inventory_contains_first_wave_roles():
    ids = {item.agent_id for item in FIRST_WAVE_AGENT_DEFINITIONS}
    assert "scope_parsing_agent" in ids
    assert "next_best_workflow_agent" in ids
    assert "analyst_briefing_agent" in ids
    assert len(ids) >= 10
