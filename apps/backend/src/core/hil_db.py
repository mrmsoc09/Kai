from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool


DEFAULT_DATABASE_URL = "postgresql://k1:k1pass@localhost:5432/k1"


def _to_async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = _to_async_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))

_async_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        try:
            _async_engine = create_async_engine(
                DATABASE_URL,
                poolclass=AsyncAdaptedQueuePool,
                pool_pre_ping=True,
                pool_size=int(os.getenv("DATABASE_POOL_SIZE", "20")),
                max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
                pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
                echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
                future=True,
            )
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Async PostgreSQL driver missing. Install 'asyncpg>=0.29,<1.0'."
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
    global _async_engine, _async_session_maker
    if _async_engine is not None:
        await _async_engine.dispose()
    _async_engine = None
    _async_session_maker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_async_session_maker()
    async with session_maker() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
