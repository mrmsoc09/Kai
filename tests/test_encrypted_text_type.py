"""Tests for EncryptedText SQLAlchemy TypeDecorator (Task 41).

Verifies that:
1. Values written through the ORM are stored as opaque ciphertext (not plaintext).
2. Values read back through the ORM are correctly decrypted.
3. Without a key, values are stored and returned as-is (fallback mode).

Uses an in-memory SQLite database so the test runs without any external services.
"""
from __future__ import annotations

import base64
import os
import sqlite3
import tempfile

import pytest
from sqlalchemy import Column, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from apps.backend.src.models.types import EncryptedText


# ---------------------------------------------------------------------------
# Minimal ORM model used only for this test
# ---------------------------------------------------------------------------

class _TestBase(DeclarativeBase):
    pass


class _SecretRecord(_TestBase):
    __tablename__ = "secret_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    secret = Column(EncryptedText, nullable=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(db_path: str):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def _fresh_key() -> str:
    """Return a base64-encoded 32-byte AES-256 key."""
    raw = os.urandom(32)
    return base64.b64encode(raw).decode("utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEncryptedTextWithKey:
    """Encryption enabled (key is set)."""

    def setup_method(self):
        # Use a fresh key per test so tests are independent
        self._key = _fresh_key()
        EncryptedText.set_key(self._key)
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._engine = _make_engine(self._tmp.name)
        _TestBase.metadata.create_all(self._engine)

    def teardown_method(self):
        # Reset key so other tests are not affected
        EncryptedText._encryption_key = None
        self._engine.dispose()
        os.unlink(self._tmp.name)

    def test_orm_roundtrip_returns_plaintext(self):
        """ORM read returns the original plaintext value."""
        with Session(self._engine) as session:
            session.add(_SecretRecord(secret="hunter2"))
            session.commit()

        with Session(self._engine) as session:
            row = session.get(_SecretRecord, 1)
            assert row.secret == "hunter2"

    def test_raw_db_stores_ciphertext_not_plaintext(self):
        """Direct SQLite query must NOT return the plaintext value.

        This is the Task 41 acceptance-criteria check: the stored bytes must be
        opaque ciphertext, not the original string.
        """
        with Session(self._engine) as session:
            session.add(_SecretRecord(secret="hunter2"))
            session.commit()

        # Raw query bypasses the SQLAlchemy TypeDecorator
        con = sqlite3.connect(self._tmp.name)
        raw = con.execute("SELECT secret FROM secret_records WHERE id=1").fetchone()[0]
        con.close()

        # The stored value must not contain the plaintext
        assert raw != "hunter2", "Plaintext found in raw DB — encryption not applied"
        # Must be valid base64 (AES-GCM nonce + ciphertext encoded as b64)
        decoded = base64.b64decode(raw)
        assert len(decoded) > 12, "Stored value too short to contain a valid GCM nonce"

    def test_dict_value_encrypted_and_roundtrips(self):
        """Dict values are JSON-serialised then encrypted."""
        payload = {"user": "alice", "score": 42}
        with Session(self._engine) as session:
            session.add(_SecretRecord(secret=payload))  # type: ignore[arg-type]
            session.commit()

        # Raw value must not leak JSON
        con = sqlite3.connect(self._tmp.name)
        raw = con.execute("SELECT secret FROM secret_records WHERE id=1").fetchone()[0]
        con.close()
        assert "alice" not in raw
        assert "score" not in raw

        # ORM read must reconstruct the dict
        with Session(self._engine) as session:
            row = session.get(_SecretRecord, 1)
            assert row.secret == payload

    def test_none_stored_as_null(self):
        """NULL values survive the round-trip as None."""
        with Session(self._engine) as session:
            session.add(_SecretRecord(secret=None))
            session.commit()

        with Session(self._engine) as session:
            row = session.get(_SecretRecord, 1)
            assert row.secret is None


class TestEncryptedTextWithoutKey:
    """Fallback mode — no encryption key set."""

    def setup_method(self):
        EncryptedText._encryption_key = None
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._engine = _make_engine(self._tmp.name)
        _TestBase.metadata.create_all(self._engine)

    def teardown_method(self):
        self._engine.dispose()
        os.unlink(self._tmp.name)

    def test_fallback_stores_plaintext(self):
        """Without a key values are stored as plaintext (graceful fallback)."""
        with Session(self._engine) as session:
            session.add(_SecretRecord(secret="no-key-value"))
            session.commit()

        con = sqlite3.connect(self._tmp.name)
        raw = con.execute("SELECT secret FROM secret_records WHERE id=1").fetchone()[0]
        con.close()
        assert raw == "no-key-value"

    def test_fallback_roundtrip(self):
        """ORM read still returns the value correctly in fallback mode."""
        with Session(self._engine) as session:
            session.add(_SecretRecord(secret="no-key-value"))
            session.commit()

        with Session(self._engine) as session:
            row = session.get(_SecretRecord, 1)
            assert row.secret == "no-key-value"
