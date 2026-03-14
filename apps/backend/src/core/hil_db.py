from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool


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
        and str(_async_engine.url).startswith("sqlite+aiosqlite://")
    ):
        # aiosqlite connections are loop-bound; recycle cached engine/session maker
        # when tests/runtime cross event-loop boundaries.
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
                        "pool_size": int(os.getenv("DATABASE_POOL_SIZE", "20")),
                        "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
                        "pool_timeout": int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
                    }
                )
            _async_engine = create_async_engine(db_url, **engine_kwargs)
            _engine_loop_id = current_loop_id
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
