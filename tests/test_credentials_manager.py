"""Tests for CredentialsManager and Vault integration.

Tests cover:
- Store/retrieve/delete credentials
- Credential validation (login/API ping)
- Scanning modes detection
- Access metadata management
- Vault integration + audit logging
"""
from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import StaticPool, create_engine, event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.backend.src.core.credentials_manager import CredentialsManager
from apps.backend.src.core.opportunity_credentials_vault import OpportunityCredentialsVault
from apps.backend.src.core.vault_client import VaultClient, SecretNotFoundError, VaultConnectionError
from apps.backend.src.models.base import Base
from apps.backend.src.models.campaign import Program
from apps.backend.src.models.opportunity_credentials import (
    OpportunityAccessMetadata,
    OpportunityCredential,
)


# ============================================================================
# Mock Vault Client for Testing
# ============================================================================


class MockVaultClient(VaultClient):
    """Mock Vault client that stores secrets in memory."""

    def __init__(self):
        self.secrets: dict[str, dict] = {}

    def write_secret(self, secret_path: str, secret_data: dict, overwrite: bool = False) -> bool:
        """Store a secret in memory."""
        if secret_path in self.secrets and not overwrite:
            from apps.backend.src.core.vault_client import VaultPermissionError
            raise VaultPermissionError(f"Secret already exists at {secret_path}")
        self.secrets[secret_path] = secret_data.copy()
        return True

    def read_secret(self, secret_path: str) -> dict:
        """Retrieve a secret from memory."""
        if secret_path not in self.secrets:
            raise SecretNotFoundError(f"Secret not found at {secret_path}")
        return self.secrets[secret_path].copy()

    def delete_secret(self, secret_path: str) -> bool:
        """Delete a secret from memory."""
        if secret_path not in self.secrets:
            raise SecretNotFoundError(f"Secret not found at {secret_path}")
        del self.secrets[secret_path]
        return True

    def list_secrets(self, secret_prefix: str) -> list[str]:
        """List secrets under a prefix."""
        return [k for k in self.secrets.keys() if k.startswith(secret_prefix)]


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def async_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Register SQLite compat functions
    @event.listens_for(engine.sync_engine, "connect")
    def register_compat(dbapi_conn, _):
        dbapi_conn.create_function("btrim", 1, str.strip)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine


@pytest_asyncio.fixture
async def db_session(async_engine):
    """Create a test database session."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
def mock_vault():
    """Create a mock Vault client."""
    return MockVaultClient()


@pytest_asyncio.fixture
def credentials_manager(db_session, mock_vault):
    """Create a CredentialsManager with mock Vault."""
    vault = OpportunityCredentialsVault(vault_client=mock_vault)
    return CredentialsManager(db_session, vault=vault)


@pytest_asyncio.fixture
async def test_program(db_session):
    """Create a test program."""
    program = Program(
        id=uuid4(),
        name="Test Program",
        platform="test",
        handle="test_handle",
        status="ACTIVE",
        config_json={
            "opportunity": {
                "program_url": "https://example.com",
            }
        },
    )
    db_session.add(program)
    await db_session.commit()
    return program


# ============================================================================
# Tests: Store Credential
# ============================================================================


@pytest.mark.asyncio
async def test_store_credential_creates_db_record(credentials_manager, test_program, mock_vault):
    """Test that storing a credential creates both Vault and DB entries."""
    creds = {"username": "testuser", "password": "testpass"}

    result = await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        creds,
        username="testuser@example.com",
        notes="Test account",
        user_id="analyst-1",
    )

    assert result.program_id == test_program.id
    assert result.access_type == "user_account"
    assert result.status == "active"
    assert result.credential_username == "testuser@example.com"
    assert result.notes == "Test account"
    assert result.created_by == "analyst-1"
    assert result.access_count == 0

    # Verify Vault secret was created
    assert len(mock_vault.secrets) == 1
    vault_path = f"secret/opportunities/{test_program.id}/credentials/user_account"
    assert vault_path in mock_vault.secrets
    assert mock_vault.secrets[vault_path]["username"] == "testuser"


@pytest.mark.asyncio
async def test_store_credential_overwrites_existing(credentials_manager, test_program):
    """Test that storing a credential twice updates the existing one."""
    creds1 = {"username": "user1", "password": "pass1"}
    creds2 = {"username": "user2", "password": "pass2"}

    result1 = await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        creds1,
        username="user1@example.com",
    )

    result2 = await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        creds2,
        username="user2@example.com",
    )

    # Should be the same record ID (updated, not new)
    assert result1.id == result2.id
    assert result2.credential_username == "user2@example.com"


# ============================================================================
# Tests: Get Credential
# ============================================================================


@pytest.mark.asyncio
async def test_get_credential_retrieves_from_vault(credentials_manager, test_program, mock_vault):
    """Test that retrieving a credential fetches from Vault."""
    creds = {"username": "testuser", "password": "secretpass"}

    await credentials_manager.store_credential(
        test_program.id,
        "api_key",
        creds,
        username="api_user",
    )

    retrieved = await credentials_manager.get_credential(
        test_program.id,
        "api_key",
        user_id="analyst-2",
    )

    assert retrieved["username"] == "testuser"
    assert retrieved["password"] == "secretpass"


@pytest.mark.asyncio
async def test_get_credential_updates_access_tracking(credentials_manager, test_program, db_session):
    """Test that accessing a credential updates access tracking."""
    creds = {"api_key": "secret-key-123"}

    await credentials_manager.store_credential(
        test_program.id,
        "api_key",
        creds,
        username="api_user",
    )

    # Retrieve credential
    await credentials_manager.get_credential(test_program.id, "api_key", user_id="analyst-3")

    # Check DB record was updated
    stmt = select(OpportunityCredential).where(
        (OpportunityCredential.program_id == test_program.id)
        & (OpportunityCredential.access_type == "api_key")
    )
    result = await db_session.execute(stmt)
    cred = result.scalars().first()

    assert cred.access_count == 1
    assert cred.last_accessed_by == "analyst-3"
    assert cred.last_accessed_at is not None


@pytest.mark.asyncio
async def test_get_credential_returns_none_if_not_found(credentials_manager, test_program):
    """Test that getting a non-existent credential returns None."""
    result = await credentials_manager.get_credential(
        test_program.id,
        "hunter_account",
    )
    assert result is None


# ============================================================================
# Tests: Delete Credential
# ============================================================================


@pytest.mark.asyncio
async def test_delete_credential_removes_from_vault_and_db(
    credentials_manager, test_program, db_session, mock_vault
):
    """Test that deleting a credential removes it from both Vault and DB."""
    creds = {"username": "to_delete", "password": "pass"}

    await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        creds,
        username="to_delete@example.com",
    )

    assert len(mock_vault.secrets) == 1

    # Delete it
    await credentials_manager.delete_credential(test_program.id, "user_account")

    # Verify removed from Vault
    assert len(mock_vault.secrets) == 0

    # Verify removed from DB
    stmt = select(OpportunityCredential).where(
        (OpportunityCredential.program_id == test_program.id)
        & (OpportunityCredential.access_type == "user_account")
    )
    result = await db_session.execute(stmt)
    assert result.scalars().first() is None


# ============================================================================
# Tests: Validate Credential
# ============================================================================


@pytest.mark.asyncio
async def test_validate_credential_missing_fields(credentials_manager, test_program):
    """Test validation with missing required fields."""
    creds = {"api_key": "test"}  # Missing username/password for user_account validation

    await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        creds,
    )

    result = await credentials_manager.validate_credential(test_program.id, "user_account")

    assert result["valid"] is False
    assert "missing username or password" in result["reason"].lower()


@pytest.mark.asyncio
async def test_validate_credential_no_program_url(credentials_manager, test_program):
    """Test validation when program has no base_url configured."""
    # Create program without base_url
    program = Program(
        id=uuid4(),
        name="No URL Program",
        platform="test",
        status="ACTIVE",
        config_json={},
    )
    credentials_manager.db.add(program)
    await credentials_manager.db.commit()

    creds = {"username": "user", "password": "pass"}

    await credentials_manager.store_credential(
        program.id,
        "user_account",
        creds,
    )

    result = await credentials_manager.validate_credential(program.id, "user_account")

    assert result["valid"] is False
    assert "base url" in result["reason"].lower()


# ============================================================================
# Tests: Access Metadata
# ============================================================================


@pytest.mark.asyncio
async def test_upsert_access_metadata_creates_record(credentials_manager, test_program, db_session):
    """Test creating access metadata."""
    meta = await credentials_manager.upsert_access_metadata(
        test_program.id,
        "user_account",
        enabled=True,
        signup_url="https://example.com/signup",
        signup_instructions="Create an account",
        requires_email=True,
    )

    assert meta.program_id == test_program.id
    assert meta.access_type == "user_account"
    assert meta.enabled is True
    assert meta.signup_url == "https://example.com/signup"
    assert meta.requires_email is True


@pytest.mark.asyncio
async def test_upsert_access_metadata_updates_existing(credentials_manager, test_program):
    """Test updating access metadata."""
    # Create
    meta1 = await credentials_manager.upsert_access_metadata(
        test_program.id,
        "api_key",
        enabled=True,
        rate_limits="100/min",
    )

    # Update
    meta2 = await credentials_manager.upsert_access_metadata(
        test_program.id,
        "api_key",
        enabled=True,
        rate_limits="1000/min",
    )

    assert meta1.id == meta2.id
    assert meta2.rate_limits == "1000/min"


# ============================================================================
# Tests: Scanning Modes Detection
# ============================================================================


@pytest.mark.asyncio
async def test_get_scanning_modes_all_unavailable(credentials_manager, test_program):
    """Test scanning modes when no credentials are stored."""
    # Enable unauthenticated access
    await credentials_manager.upsert_access_metadata(
        test_program.id,
        "unauthenticated",
        enabled=True,
    )

    modes = await credentials_manager.get_scanning_modes(test_program.id)

    assert "unauthenticated" in modes["available_modes"]
    # Only unauthenticated should be available without credentials
    assert modes["available_modes"] == ["unauthenticated"]
    assert len(modes["warnings"]) == 0  # No warnings when unauthenticated is the only option


@pytest.mark.asyncio
async def test_get_scanning_modes_with_user_account(credentials_manager, test_program):
    """Test scanning modes with user account stored."""
    # Set metadata to enable user_account
    await credentials_manager.upsert_access_metadata(
        test_program.id,
        "user_account",
        enabled=True,
        signup_url="https://example.com/signup",
    )

    # Store credential
    await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        {"username": "user", "password": "pass"},
    )

    modes = await credentials_manager.get_scanning_modes(test_program.id)

    assert "user_account" in modes["available_modes"]
    # Warnings should not include user_account since it's stored
    warnings_types = {w["access_type"] for w in modes["warnings"]}
    assert "user_account" not in warnings_types


@pytest.mark.asyncio
async def test_get_scanning_modes_missing_credentials_warning(credentials_manager, test_program):
    """Test that missing credentials generate warnings."""
    # Set metadata to enable api_key but don't store it
    await credentials_manager.upsert_access_metadata(
        test_program.id,
        "api_key",
        enabled=True,
        signup_url="https://example.com/api/keys",
        rate_limits="100/min",
    )

    modes = await credentials_manager.get_scanning_modes(test_program.id)

    # Should have warning about missing api_key
    api_key_warnings = [w for w in modes["warnings"] if w["access_type"] == "api_key"]
    assert len(api_key_warnings) > 0
    assert api_key_warnings[0]["type"] == "MISSING_CREDENTIALS"
    assert "api" in api_key_warnings[0]["message"].lower()  # Check for "api" since message has "API key"


@pytest.mark.asyncio
async def test_get_scanning_modes_multiple_modes_available(credentials_manager, test_program):
    """Test scanning modes with multiple credentials stored."""
    # Enable and store user_account
    await credentials_manager.upsert_access_metadata(
        test_program.id,
        "user_account",
        enabled=True,
    )
    await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        {"username": "user", "password": "pass"},
    )

    # Enable and store api_key
    await credentials_manager.upsert_access_metadata(
        test_program.id,
        "api_key",
        enabled=True,
    )
    await credentials_manager.store_credential(
        test_program.id,
        "api_key",
        {"api_key": "secret-key"},
    )

    modes = await credentials_manager.get_scanning_modes(test_program.id)

    assert "user_account" in modes["available_modes"]
    assert "api_key" in modes["available_modes"]
    assert len(modes["warnings"]) == 0  # No warnings when all credentials stored


# ============================================================================
# Tests: List Credentials
# ============================================================================


@pytest.mark.asyncio
async def test_list_credentials_for_program(credentials_manager, test_program):
    """Test listing all credentials for a program."""
    # Store multiple credentials
    await credentials_manager.store_credential(
        test_program.id,
        "user_account",
        {"username": "user", "password": "pass"},
        username="user@example.com",
    )

    await credentials_manager.store_credential(
        test_program.id,
        "api_key",
        {"api_key": "key123"},
        username="api_user",
    )

    creds = await credentials_manager.list_credentials_for_program(test_program.id)

    assert len(creds) == 2
    access_types = {c.access_type for c in creds}
    assert access_types == {"user_account", "api_key"}
