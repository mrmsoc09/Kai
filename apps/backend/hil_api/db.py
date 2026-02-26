from apps.backend.src.core.hil_db import (
    DATABASE_URL,
    dispose_async_engine,
    get_async_engine,
    get_async_session_maker,
    get_db,
)

# Backward-compatible aliases
engine = get_async_engine
SessionLocal = get_async_session_maker
AsyncSessionLocal = get_async_session_maker

__all__ = [
    "DATABASE_URL",
    "get_async_engine",
    "get_async_session_maker",
    "dispose_async_engine",
    "engine",
    "SessionLocal",
    "AsyncSessionLocal",
    "get_db",
]
