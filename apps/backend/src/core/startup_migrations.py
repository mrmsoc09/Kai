from __future__ import annotations

import logging
import os
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect

try:
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
except ImportError:  # pragma: no cover - test/runtime environments without alembic
    command = SimpleNamespace(upgrade=None)  # type: ignore[assignment]
    Config = object  # type: ignore[assignment]
    MigrationContext = object  # type: ignore[assignment]
    ScriptDirectory = object  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured; cannot run startup migrations.")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _alembic_config() -> Config:
    if getattr(command, "upgrade", None) is None:
        raise RuntimeError("alembic is not installed; cannot run startup migrations.")
    ini_path = _repo_root() / "alembic.ini"
    if not ini_path.exists():
        raise RuntimeError(f"Alembic configuration not found at {ini_path}")
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", _database_url())
    return cfg


def _migration_flags() -> tuple[bool, bool, bool]:
    enforce = _env_bool("KAI_DB_ENFORCE_MIGRATIONS", True)
    auto_apply_default = os.getenv("ENVIRONMENT", "development").strip().lower() != "production"
    auto_apply = _env_bool("KAI_DB_AUTO_APPLY_MIGRATIONS", auto_apply_default)
    fail_on_dirty = _env_bool("KAI_DB_FAIL_ON_DIRTY_SCHEMA", True)
    return enforce, auto_apply, fail_on_dirty


def _current_heads(config: Config) -> tuple[str, ...]:
    if getattr(command, "upgrade", None) is None:
        raise RuntimeError("alembic is not installed; cannot run startup migrations.")
    engine = create_engine(_database_url(), future=True)
    try:
        with engine.connect() as conn:
            migration_context = MigrationContext.configure(conn)
            return tuple(migration_context.get_current_heads())
    finally:
        engine.dispose()


def ensure_startup_migrations() -> None:
    """Ensure the configured database schema matches the current Alembic heads."""
    if getattr(command, "upgrade", None) is None:
        logger.info("Startup migrations skipped because alembic is unavailable.")
        return
    enforce, auto_apply, fail_on_dirty = _migration_flags()
    if not enforce:
        logger.info("Startup migrations disabled by configuration.")
        return

    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    known_heads = tuple(script.get_heads())

    engine = create_engine(_database_url(), future=True)
    try:
        with engine.connect() as conn:
            migration_context = MigrationContext.configure(conn)
            current_heads = tuple(migration_context.get_current_heads())
            inspector = inspect(conn)
            table_names = {name for name in inspector.get_table_names() if name != "alembic_version"}
            unknown_heads = [head for head in current_heads if script.get_revision(head) is None]

            logger.info(
                "Database migration state: current_heads=%s known_heads=%s tables=%s",
                ",".join(current_heads) or "<none>",
                ",".join(known_heads) or "<none>",
                len(table_names),
            )

            if unknown_heads:
                raise RuntimeError(
                    "Database migration state is unknown or divergent: "
                    + ", ".join(unknown_heads)
                )

            if not current_heads and table_names and fail_on_dirty:
                raise RuntimeError(
                    "Database schema exists but alembic_version is empty; "
                    "refusing to boot against an unknown schema."
                )

            if current_heads and set(current_heads) == set(known_heads):
                logger.info("Database schema is current at revision(s): %s", ", ".join(current_heads))
                return

            if not auto_apply:
                raise RuntimeError(
                    "Database migrations are pending but auto-apply is disabled. "
                    f"Current={','.join(current_heads) or '<none>'} expected={','.join(known_heads) or '<none>'}."
                )
    finally:
        engine.dispose()

    logger.info("Applying Alembic migrations to heads...")
    command.upgrade(cfg, "heads")

    refreshed_heads = _current_heads(cfg)
    if set(refreshed_heads) != set(known_heads):
        raise RuntimeError(
            "Alembic migration upgrade completed but the schema did not reach the expected heads. "
            f"Current={','.join(refreshed_heads) or '<none>'} expected={','.join(known_heads) or '<none>'}."
        )
    logger.info("Database migrations applied successfully: %s", ", ".join(refreshed_heads))
from types import SimpleNamespace
