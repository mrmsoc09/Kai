from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.backend.src.core.bug_bounty_hunting_service import BugBountyHuntingService


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, schedules):
        self.schedules = schedules

    async def execute(self, stmt):  # noqa: ARG002
        now = datetime.now(timezone.utc)
        due = [
            item
            for item in self.schedules
            if item.status == "ACTIVE"
            and (item.next_scheduled_run_at is None or item.next_scheduled_run_at <= now)
        ]
        return _ScalarResult(due)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_dispatch_due_schedules_reserves_next_run_to_prevent_duplicate_dispatch(monkeypatch):
    now = datetime.now(timezone.utc)
    schedule = SimpleNamespace(
        id=uuid4(),
        program_id=uuid4(),
        scope_target_id=uuid4(),
        workflow_template="workflow_recon_surface_map",
        schedule_type="interval",
        interval_minutes=60,
        status="ACTIVE",
        priority_tier=1,
        failure_backoff_minutes=5,
        next_scheduled_run_at=now - timedelta(minutes=1),
        last_run_started_at=None,
        last_run_status=None,
        last_failure_reason=None,
        updated_by=None,
    )
    fake_db = _FakeDB([schedule])
    svc = BugBountyHuntingService(fake_db)  # type: ignore[arg-type]

    import apps.backend.src.core.bug_bounty_hunting_service as hunting_module
    import apps.backend.src.worker.campaign_tasks as campaign_tasks

    async def _noop_audit(*args, **kwargs):  # noqa: ARG001
        return None

    monkeypatch.setattr(hunting_module, "record_transition_event", _noop_audit)

    class _TaskStub:
        def __init__(self):
            self.calls = 0

        def delay(self, **kwargs):  # noqa: ANN003
            self.calls += 1
            return SimpleNamespace(id=f"task-{self.calls}", payload=kwargs)

    stub = _TaskStub()
    monkeypatch.setattr(campaign_tasks, "run_bug_bounty_schedule_task", stub)

    first = await svc.dispatch_due_schedules(actor="tests.dispatch", limit=25)
    second = await svc.dispatch_due_schedules(actor="tests.dispatch", limit=25)

    assert len(first) == 1
    assert first[0].decision_status == "DISPATCHED"
    assert len(second) == 0
    assert stub.calls == 1
    assert schedule.next_scheduled_run_at > now
