"""Comprehensive tests for ScanQueueRotator.

Uses SQLite + aiosqlite (same pattern as the rest of the test suite) so no
external services are required.  All Celery dispatch calls are mocked.
"""
from __future__ import annotations

import os

# Must be set before any app imports so hil_db resolves the SQLite URL.
os.environ.setdefault("K1_TEST_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "test")

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.backend.src.models.base import Base
from apps.backend.src.models.scan_pool import (
    OpportunityScanPool,
    OpportunityScanPoolEntry,
)

# ---------------------------------------------------------------------------
# Ensure all models are imported so their tables are registered with Base.metadata
# ---------------------------------------------------------------------------
import apps.backend.src.models.bug_bounty  # noqa: F401 — registers HuntScheduleJob table
import apps.backend.src.models.scan_pool  # noqa: F401

# ---------------------------------------------------------------------------
# SQLite test fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite://"  # in-memory database


@pytest_asyncio.fixture
async def async_engine():
    """Create a fresh in-memory SQLite engine for each test.

    Uses StaticPool so that all "connections" share the same underlying
    aiosqlite connection and therefore the same in-memory database.
    NullPool would give each connection its own empty database, making
    tables created in create_all invisible to subsequent sessions.

    Does NOT use detect_types: the UTCAwareDatetime TypeDecorator in
    models/mixins.py handles timezone-aware datetime conversion for all
    timestamp columns, making manual sqlite3.register_converter unnecessary.
    Combining detect_types with RETURNING clauses causes str_to_datetime
    failures in aiosqlite, so we skip it entirely.
    """
    engine = create_async_engine(
        TEST_DB_URL,
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Register SQLite compatibility shims required by CHECK constraints.
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine.sync_engine, "connect")
    def _register_compat(dbapi_conn, _conn_record):
        dbapi_conn.create_function("btrim", 1, str.strip)
        dbapi_conn.create_function("btrim", 2, lambda s, chars="": s.strip(chars))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    """Provide a fresh AsyncSession per test."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


async def make_pool(
    db: AsyncSession,
    *,
    name: str = "Test Pool",
    status: str = "active",
    min_concurrent: int = 2,
    max_concurrent: int = 5,
) -> OpportunityScanPool:
    pool = OpportunityScanPool(
        id=uuid4(),
        name=name,
        status=status,
        min_concurrent=min_concurrent,
        max_concurrent=max_concurrent,
        current_cycle=0,
    )
    db.add(pool)
    await db.flush()
    return pool


async def make_entry(
    db: AsyncSession,
    pool: OpportunityScanPool,
    *,
    program_name: str = "Test Program",
    status: str = "waiting",
    queue_position: int | None = None,
    schedule_job_id=None,
    current_cycle_scanned: bool = False,
    last_activated_at=None,
) -> OpportunityScanPoolEntry:
    if queue_position is None:
        from sqlalchemy import func, select

        max_pos_result = await db.execute(
            select(func.max(OpportunityScanPoolEntry.queue_position)).where(
                OpportunityScanPoolEntry.pool_id == pool.id
            )
        )
        queue_position = (max_pos_result.scalar() or 0) + 1

    entry = OpportunityScanPoolEntry(
        id=uuid4(),
        pool_id=pool.id,
        program_name=program_name,
        status=status,
        queue_position=queue_position,
        total_scans_completed=0,
        current_cycle_scanned=current_cycle_scanned,
        schedule_job_id=schedule_job_id,
        last_activated_at=last_activated_at,
    )
    db.add(entry)
    await db.flush()
    return entry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_opportunity_appends_to_queue(db_session):
    """Adding entries increases the queue length and assigns ascending positions."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session)
    rotator = ScanQueueRotator()

    e1 = await rotator.add_opportunity(db_session, pool.id, "Program A")
    e2 = await rotator.add_opportunity(db_session, pool.id, "Program B")
    e3 = await rotator.add_opportunity(db_session, pool.id, "Program C")

    assert e1.queue_position < e2.queue_position < e3.queue_position
    assert e1.program_name == "Program A"
    assert e2.program_name == "Program B"
    assert e3.status == "waiting"


@pytest.mark.asyncio
async def test_advance_queue_activates_up_to_min_concurrent(db_session):
    """advance_queue fills the window up to min_concurrent active entries."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session, min_concurrent=2, max_concurrent=5)
    job_id = uuid4()
    await make_entry(db_session, pool, program_name="P1", schedule_job_id=job_id, queue_position=1)
    await make_entry(db_session, pool, program_name="P2", schedule_job_id=job_id, queue_position=2)
    await make_entry(db_session, pool, program_name="P3", schedule_job_id=job_id, queue_position=3)

    fake_task = MagicMock()
    fake_task.id = "celery-task-abc"

    rotator = ScanQueueRotator()
    with patch(
        "apps.backend.src.core.scan_queue_rotator.run_bug_bounty_schedule_task",
        create=True,
    ) as mock_task:
        mock_task.delay.return_value = fake_task
        # Patch the import inside activate_entry
        with patch(
            "apps.backend.src.core.scan_queue_rotator"
            ".ScanQueueRotator.activate_entry",
            wraps=rotator.activate_entry,
        ):
            # Use patched import
            with patch.dict(
                "sys.modules",
                {
                    "apps.backend.src.worker.campaign_tasks": MagicMock(
                        run_bug_bounty_schedule_task=MagicMock(
                            delay=MagicMock(return_value=fake_task)
                        )
                    )
                },
            ):
                activated = await rotator.advance_queue(db_session, pool)

    # With min_concurrent=2 and 0 currently active, 2 entries should start.
    assert activated == 2


@pytest.mark.asyncio
async def test_advance_queue_does_not_exceed_max_concurrent(db_session):
    """Hard ceiling: advance_queue never activates more than max_concurrent total."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session, min_concurrent=3, max_concurrent=3)
    job_id = uuid4()

    # Pre-populate 2 already-active entries.
    for i in range(1, 3):
        e = await make_entry(
            db_session, pool, program_name=f"Active {i}", status="active",
            schedule_job_id=job_id, queue_position=i,
        )

    # 3 more waiting entries.
    for i in range(3, 6):
        await make_entry(
            db_session, pool, program_name=f"Waiting {i}",
            schedule_job_id=job_id, queue_position=i,
        )

    fake_task = MagicMock()
    fake_task.id = "t1"

    rotator = ScanQueueRotator()
    with patch.dict(
        "sys.modules",
        {
            "apps.backend.src.worker.campaign_tasks": MagicMock(
                run_bug_bounty_schedule_task=MagicMock(
                    delay=MagicMock(return_value=fake_task)
                )
            )
        },
    ):
        activated = await rotator.advance_queue(db_session, pool)

    # max_concurrent=3, already active=2 → only 1 slot available.
    assert activated == 1


@pytest.mark.asyncio
async def test_complete_entry_moves_to_tail(db_session):
    """After completion the entry's queue_position is max_position + 1."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session, min_concurrent=1, max_concurrent=2)
    e1 = await make_entry(db_session, pool, program_name="P1", status="active", queue_position=1)
    await make_entry(db_session, pool, program_name="P2", status="waiting", queue_position=2)
    await make_entry(db_session, pool, program_name="P3", status="waiting", queue_position=3)

    rotator = ScanQueueRotator()
    with patch.dict(
        "sys.modules",
        {
            "apps.backend.src.worker.campaign_tasks": MagicMock(
                run_bug_bounty_schedule_task=MagicMock(
                    delay=MagicMock(return_value=MagicMock(id="t2"))
                )
            )
        },
    ):
        await rotator.complete_entry(db_session, pool.id, e1.id, success=True)

    await db_session.refresh(e1)
    # Position should now be 4 (max was 3, new tail = 4).
    assert e1.queue_position == 4


@pytest.mark.asyncio
async def test_complete_entry_re_queues_as_waiting(db_session):
    """Completed entry status must return to 'waiting' for the next rotation."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session, min_concurrent=1, max_concurrent=1)
    entry = await make_entry(
        db_session, pool, status="active", queue_position=1,
    )

    rotator = ScanQueueRotator()
    with patch.dict(
        "sys.modules",
        {
            "apps.backend.src.worker.campaign_tasks": MagicMock(
                run_bug_bounty_schedule_task=MagicMock(
                    delay=MagicMock(return_value=MagicMock(id="t3"))
                )
            )
        },
    ):
        await rotator.complete_entry(db_session, pool.id, entry.id, success=False)

    await db_session.refresh(entry)
    assert entry.status == "waiting"
    assert entry.last_scan_status == "failed"
    assert entry.total_scans_completed == 1


@pytest.mark.asyncio
async def test_cycle_increments_when_all_entries_scanned(db_session):
    """cycle counter increments when every entry has current_cycle_scanned=True."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session, min_concurrent=1, max_concurrent=2)
    await make_entry(
        db_session, pool, program_name="P1", status="waiting",
        current_cycle_scanned=True, queue_position=1,
    )
    await make_entry(
        db_session, pool, program_name="P2", status="waiting",
        current_cycle_scanned=True, queue_position=2,
    )

    rotator = ScanQueueRotator()
    completed = await rotator.check_cycle_completion(db_session, pool)

    assert completed is True
    await db_session.refresh(pool)
    assert pool.current_cycle == 1


@pytest.mark.asyncio
async def test_cycle_resets_scanned_flags_after_cycle(db_session):
    """After a cycle completes, all current_cycle_scanned flags are reset."""
    from sqlalchemy import select
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session)
    e1 = await make_entry(
        db_session, pool, program_name="P1", current_cycle_scanned=True, queue_position=1,
    )
    e2 = await make_entry(
        db_session, pool, program_name="P2", current_cycle_scanned=True, queue_position=2,
    )

    rotator = ScanQueueRotator()
    await rotator.check_cycle_completion(db_session, pool)
    await db_session.flush()

    await db_session.refresh(e1)
    await db_session.refresh(e2)
    assert e1.current_cycle_scanned is False
    assert e2.current_cycle_scanned is False


@pytest.mark.asyncio
async def test_paused_pool_does_not_advance(db_session):
    """tick_pool returns early without activating entries when pool is paused."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session, status="paused")
    job_id = uuid4()
    await make_entry(db_session, pool, schedule_job_id=job_id, queue_position=1)

    rotator = ScanQueueRotator()
    result = await rotator.tick_pool(db_session, pool.id)

    assert result.get("skipped") is True
    # Entry must still be waiting.
    from sqlalchemy import select

    entry_result = await db_session.execute(
        select(OpportunityScanPoolEntry).where(
            OpportunityScanPoolEntry.pool_id == pool.id
        )
    )
    entries = entry_result.scalars().all()
    assert all(e.status == "waiting" for e in entries)


@pytest.mark.asyncio
async def test_remove_waiting_entry_succeeds(db_session):
    """Waiting entries can be removed from the queue."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session)
    entry = await make_entry(db_session, pool, status="waiting", queue_position=1)

    rotator = ScanQueueRotator()
    removed = await rotator.remove_opportunity(db_session, pool.id, entry.id)

    assert removed is True
    from sqlalchemy import select

    result = await db_session.execute(
        select(OpportunityScanPoolEntry).where(OpportunityScanPoolEntry.id == entry.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_remove_active_entry_fails(db_session):
    """Active entries cannot be removed — must wait for scan completion."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session)
    entry = await make_entry(db_session, pool, status="active", queue_position=1)

    rotator = ScanQueueRotator()
    removed = await rotator.remove_opportunity(db_session, pool.id, entry.id)

    assert removed is False
    from sqlalchemy import select

    result = await db_session.execute(
        select(OpportunityScanPoolEntry).where(OpportunityScanPoolEntry.id == entry.id)
    )
    # Entry must still exist and still be active.
    still_there = result.scalar_one_or_none()
    assert still_there is not None
    assert still_there.status == "active"


@pytest.mark.asyncio
async def test_stale_active_entry_marked_error(db_session):
    """Entries active for more than stale_after_hours are marked 'error'."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session)
    stale_time = datetime.now(timezone.utc) - timedelta(hours=5)
    entry = await make_entry(
        db_session,
        pool,
        status="active",
        queue_position=1,
        last_activated_at=stale_time,
    )

    rotator = ScanQueueRotator()
    recovered = await rotator.check_stale_active_entries(db_session, pool, stale_after_hours=4)

    assert recovered == 1
    await db_session.refresh(entry)
    assert entry.status == "error"
    assert entry.last_scan_status == "timeout"


@pytest.mark.asyncio
async def test_concurrency_settings_update(db_session):
    """set_concurrency persists new values and validates min <= max."""
    from apps.backend.src.core.scan_queue_rotator import ScanQueueRotator

    pool = await make_pool(db_session, min_concurrent=2, max_concurrent=5)
    rotator = ScanQueueRotator()

    # Valid update.
    await rotator.set_concurrency(db_session, pool.id, min_concurrent=3, max_concurrent=10)
    await db_session.refresh(pool)
    assert pool.min_concurrent == 3
    assert pool.max_concurrent == 10

    # Invalid: min > max.
    with pytest.raises(ValueError, match="min_concurrent must be <= max_concurrent"):
        await rotator.set_concurrency(db_session, pool.id, min_concurrent=8, max_concurrent=5)

    # Invalid: max > 25.
    with pytest.raises(ValueError, match="max_concurrent must be between 1 and 25"):
        await rotator.set_concurrency(db_session, pool.id, min_concurrent=1, max_concurrent=30)
