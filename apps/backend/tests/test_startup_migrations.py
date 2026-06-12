from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.backend.src.core import startup_migrations as sm


class _FakeConn:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True


class _FakeEngine:
    def __init__(self):
        self.conn = _FakeConn()

    def connect(self):
        return self.conn

    def dispose(self):
        return None


class _FakeMigrationContext:
    def __init__(self, heads):
        self._heads = tuple(heads)

    def get_current_heads(self):
        return self._heads


class _FakeScript:
    def __init__(self, heads):
        self._heads = tuple(heads)

    def get_heads(self):
        return self._heads

    def get_revision(self, rev):
        return SimpleNamespace(revision=rev) if rev in self._heads else None


def test_startup_migrations_applies_pending_schema(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/kai")
    monkeypatch.setenv("KAI_DB_ENFORCE_MIGRATIONS", "true")
    monkeypatch.setenv("KAI_DB_AUTO_APPLY_MIGRATIONS", "true")
    monkeypatch.setenv("KAI_DB_FAIL_ON_DIRTY_SCHEMA", "true")
    monkeypatch.setattr(sm, "_repo_root", lambda: sm.Path("/tmp"))
    monkeypatch.setattr(sm, "_alembic_config", lambda: SimpleNamespace())
    monkeypatch.setattr(sm, "create_engine", lambda *args, **kwargs: _FakeEngine())
    monkeypatch.setattr(sm, "inspect", lambda conn: SimpleNamespace(get_table_names=lambda: []))
    monkeypatch.setattr(sm, "MigrationContext", SimpleNamespace(configure=lambda conn: _FakeMigrationContext([])))
    monkeypatch.setattr(sm, "ScriptDirectory", SimpleNamespace(from_config=lambda cfg: _FakeScript(["rev-a"])))
    monkeypatch.setattr(sm, "_current_heads", lambda cfg: ("rev-a",))

    applied = {}
    monkeypatch.setattr(sm.command, "upgrade", lambda cfg, target: applied.setdefault("target", target))

    sm.ensure_startup_migrations()
    assert applied["target"] == "heads"


def test_startup_migrations_blocks_dirty_schema(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/kai")
    monkeypatch.setenv("KAI_DB_ENFORCE_MIGRATIONS", "true")
    monkeypatch.setenv("KAI_DB_AUTO_APPLY_MIGRATIONS", "true")
    monkeypatch.setenv("KAI_DB_FAIL_ON_DIRTY_SCHEMA", "true")
    monkeypatch.setattr(sm, "_repo_root", lambda: sm.Path("/tmp"))
    monkeypatch.setattr(sm, "_alembic_config", lambda: SimpleNamespace())
    monkeypatch.setattr(sm, "create_engine", lambda *args, **kwargs: _FakeEngine())
    monkeypatch.setattr(sm, "inspect", lambda conn: SimpleNamespace(get_table_names=lambda: ["users"]))
    monkeypatch.setattr(sm, "MigrationContext", SimpleNamespace(configure=lambda conn: _FakeMigrationContext([])))
    monkeypatch.setattr(sm, "ScriptDirectory", SimpleNamespace(from_config=lambda cfg: _FakeScript(["rev-a"])))
    monkeypatch.setattr(sm.command, "upgrade", lambda cfg, target: None)

    with pytest.raises(RuntimeError, match="unknown schema"):
        sm.ensure_startup_migrations()
