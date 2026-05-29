from __future__ import annotations

import asyncio
import os
import sqlite3 as _sqlite3
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool


def _register_sqlite_timestamp_converter() -> None:
    """Register a TIMESTAMP type converter for sqlite3 that returns UTC-aware datetimes.

    SQLite stores timestamps as plain ISO-8601 strings with no timezone data.
    When ``detect_types=PARSE_DECLTYPES`` is active, sqlite3 routes each cell
    through the registered converter for its declared column type.  Without this
    converter, TIMESTAMP columns come back as naive datetime objects, causing
    ``TypeError: can't compare offset-naive and offset-aware datetimes`` when
    service code compares DB-sourced values against ``datetime.now(timezone.utc)``.

    This is a no-op (idempotent) registration — calling it multiple times is safe.
    """

    def _parse_ts(raw: bytes) -> datetime:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    _sqlite3.register_converter("TIMESTAMP", _parse_ts)


DEFAULT_TEST_DATABASE_URL = "sqlite+aiosqlite:///./.pytest_hil.db"


def _to_async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _is_test_mode() -> bool:
    return os.getenv("K1_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_database_url() -> str:
    configured = (os.getenv("DATABASE_URL", "") or "").strip()
    if configured:
        return _to_async_database_url(configured)
    if _is_test_mode():
        return DEFAULT_TEST_DATABASE_URL
    raise RuntimeError(
        "DATABASE_URL is not configured. Set DATABASE_URL for non-test environments."
    )

_async_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None
_engine_loop_id: int | None = None


def _current_loop_id() -> int | None:
    try:
        return id(asyncio.get_running_loop())
    except RuntimeError:
        return None


def get_async_engine() -> AsyncEngine:
    global _async_engine, _async_session_maker, _engine_loop_id
    current_loop_id = _current_loop_id()
    if (
        _async_engine is not None
        and _engine_loop_id is not None
        and current_loop_id is not None
        and _engine_loop_id != current_loop_id
    ):
        # All async DB backends (asyncpg AND aiosqlite) are loop-bound; recycle the
        # cached engine/session maker whenever the event loop changes.  This is
        # critical in Celery fork-pool workers where each asyncio.run() call creates
        # a fresh event loop — without recycling here the engine holds asyncpg
        # connections bound to the OLD loop, causing:
        #   "Task got Future attached to a different loop"  /  "Event loop is closed"
        _async_engine.sync_engine.dispose()
        _async_engine = None
        _async_session_maker = None
        _engine_loop_id = None
    if _async_engine is None:
        try:
            db_url = _resolve_database_url()
            engine_kwargs = {
                "echo": os.getenv("DATABASE_ECHO", "false").lower() == "true",
                "future": True,
            }
            if db_url.startswith("sqlite+aiosqlite://"):
                # Queue-pool semantics can block aiosqlite-heavy test lifecycles.
                # Keep sqlite test runtime deterministic by disabling pooling.
                engine_kwargs["poolclass"] = NullPool
            else:
                engine_kwargs.update(
                    {
                        "poolclass": AsyncAdaptedQueuePool,
                        "pool_pre_ping": True,
                        "pool_recycle": int(os.getenv("DATABASE_POOL_RECYCLE", "1800")),
                        "pool_size": int(os.getenv("DATABASE_POOL_SIZE", "20")),
                        "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
                        "pool_timeout": int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
                    }
                )
            _async_engine = create_async_engine(db_url, **engine_kwargs)
            _engine_loop_id = current_loop_id
            if db_url.startswith("sqlite+aiosqlite://"):
                # Register PostgreSQL-specific functions that appear in CHECK constraints
                # so that Base.metadata.create_all() works against a SQLite test database.
                # btrim(text) strips leading/trailing whitespace (≡ str.strip).
                # btrim(text, chars) strips specific chars from both ends.
                from sqlalchemy import event as _sa_event  # local import avoids top-level cycle

                @_sa_event.listens_for(_async_engine.sync_engine, "connect")
                def _register_sqlite_pg_compat(dbapi_conn, _conn_record):  # type: ignore[misc]
                    dbapi_conn.create_function("btrim", 1, str.strip)
                    dbapi_conn.create_function("btrim", 2, lambda s, chars="": s.strip(chars))
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"Database driver module missing: {exc.name}. "
                "Install required async DB driver dependencies for configured DATABASE_URL."
            ) from exc
    return _async_engine


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _async_session_maker


async def dispose_async_engine() -> None:
    global _async_engine, _async_session_maker, _engine_loop_id
    if _async_engine is not None:
        await _async_engine.dispose()
    _async_engine = None
    _async_session_maker = None
    _engine_loop_id = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_async_session_maker()
    async with session_maker() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
