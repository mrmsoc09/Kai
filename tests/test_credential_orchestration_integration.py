"""Integration tests for credential management and scanning mode detection with workflow orchestration."""
from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.backend.src.core.bugbounty_workflow_engine import (
    WORKFLOW_TEMPLATES,
    build_phase_specs_for_template,
)
from apps.backend.src.core.credentials_manager import CredentialsManager
from apps.backend.src.core.opportunity_credentials_vault import OpportunityCredentialsVault
from apps.backend.src.core.scope_guardrails import ScopePolicy
from apps.backend.src.models.base import Base
from apps.backend.src.models.campaign import Program
from apps.backend.src.models.opportunity_credentials import (
    OpportunityAccessMetadata,
    OpportunityCredential,
)


class MockVaultClient:
    """Mock Vault client for testing without external services."""

    def __init__(self):
        self.storage = {}

    def write_secret(self, path: str, secret: dict, overwrite: bool = True) -> None:
        """Store a secret in the mock Vault."""
        if path in self.storage and not overwrite:
            raise Exception(f"Secret already exists at {path}")
        self.storage[path] = secret

    def read_secret(self, path: str) -> dict:
        """Retrieve a secret from the mock Vault."""
        if path not in self.storage:
            raise Exception(f"Secret not found: {path}")
        return self.storage[path]

    def delete_secret(self, path: str) -> None:
        """Delete a secret from the mock Vault."""
        if path in self.storage:
            del self.storage[path]


@pytest_asyncio.fixture
async def db():
    """Create an in-memory SQLite database for testing."""
    from sqlalchemy import event as sa_event
    from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Register btrim function for SQLite compatibility
    @sa_event.listens_for(engine.sync_engine, "connect")
    def register_sqlite_pg_compat(dbapi_conn, _conn_record):
        dbapi_conn.create_function("btrim", 1, str.strip)
        dbapi_conn.create_function("btrim", 2, lambda s, chars="": s.strip(chars))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = AsyncSessionClass(
        bind=engine, expire_on_commit=False, autoflush=False, autocommit=False
    )
    yield async_session_maker
    await async_session_maker.close()


@pytest_asyncio.fixture
async def test_program(db):
    """Create a test program."""
    program = Program(
        id=uuid4(),
        name="Test Program",
        status="ACTIVE",
        config_json={"opportunity": {"program_url": "https://example.com"}},
    )
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return program


@pytest.fixture
def scope_policy() -> ScopePolicy:
    """Create a permissive scope policy for testing."""
    return ScopePolicy(
        allowlist=[],
        denylist=[],
        strict_allowlist=False,
        safe_mode_default=False,
    )


@pytest_asyncio.fixture
async def credentials_manager(db):
    """Create a credentials manager with mock Vault."""
    vault = OpportunityCredentialsVault(vault_client=MockVaultClient())
    return CredentialsManager(db, vault)


class TestScanningModeDetectionInWorkflow:
    """Test scanning mode detection integrated with workflow building."""

    @pytest.mark.asyncio
    async def test_workflow_with_no_available_credentials(
        self, test_program: Program, credentials_manager: CredentialsManager, db: AsyncSession, scope_policy: ScopePolicy
    ):
        """Test that workflow skips credential-required steps when no credentials available."""
        # Set up access metadata (all available, but no credentials stored)
        for access_type in ["unauthenticated", "user_account", "api_key", "hunter_account"]:
            meta = OpportunityAccessMetadata(
                id=uuid4(),
                program_id=test_program.id,
                access_type=access_type,
                enabled=True,
                signup_url=f"https://example.com/signup/{access_type}" if access_type != "unauthenticated" else None,
            )
            db.add(meta)
        await db.commit()

        # Get available modes (should only be unauthenticated since no credentials stored)
        modes = await credentials_manager.get_scanning_modes(test_program.id)
        assert modes["available_modes"] == ["unauthenticated"]
        assert len(modes["warnings"]) == 3  # user_account, api_key, hunter_account

        # Build workflow with only unauthenticated mode
        phase_specs, metadata = build_phase_specs_for_template(
            template_name="workflow_web_attack_surface",
            target="example.com",
            safe_mode=False,
            scope_policy=scope_policy,
            available_modes=modes["available_modes"],
        )

        # waymore step requires api_key, so it should be skipped
        phase_names = [spec.phase_name for spec in phase_specs]
        assert "endpoint_discovery__waymore" not in phase_names
        assert "steps_skipped_due_to_credentials" in metadata
        assert any("waymore" in skip for skip in metadata["steps_skipped_due_to_credentials"])

    @pytest.mark.asyncio
    async def test_workflow_with_api_key_credential(
        self, test_program: Program, credentials_manager: CredentialsManager, db: AsyncSession, scope_policy: ScopePolicy
    ):
        """Test that workflow includes api_key-required steps when api_key credential available."""
        # Set up metadata
        for access_type in ["unauthenticated", "user_account", "api_key", "hunter_account"]:
            meta = OpportunityAccessMetadata(
                id=uuid4(),
                program_id=test_program.id,
                access_type=access_type,
                enabled=True,
                signup_url=f"https://example.com/signup/{access_type}" if access_type != "unauthenticated" else None,
            )
            db.add(meta)
        await db.commit()

        # Store an API key credential
        await credentials_manager.store_credential(
            program_id=test_program.id,
            access_type="api_key",
            credentials={"api_key": "test-api-key"},
            username="api_user",
            user_id="analyst1",
        )

        # Get available modes (should include api_key)
        modes = await credentials_manager.get_scanning_modes(test_program.id)
        assert "api_key" in modes["available_modes"]
        assert "unauthenticated" in modes["available_modes"]

        # Build workflow with api_key mode
        phase_specs, metadata = build_phase_specs_for_template(
            template_name="workflow_web_attack_surface",
            target="example.com",
            safe_mode=False,
            scope_policy=scope_policy,
            available_modes=modes["available_modes"],
        )

        # waymore step (requires api_key) should be included
        phase_names = [spec.phase_name for spec in phase_specs]
        assert "endpoint_discovery__waymore" in phase_names

    @pytest.mark.asyncio
    async def test_readiness_evaluation_with_credentials(
        self, test_program: Program, credentials_manager: CredentialsManager, db: AsyncSession
    ):
        """Test readiness evaluation includes scanning mode information."""
        # Set up metadata
        meta = OpportunityAccessMetadata(
            id=uuid4(),
            program_id=test_program.id,
            access_type="unauthenticated",
            enabled=True,
        )
        db.add(meta)
        await db.commit()

        # Get scanning modes for readiness check
        modes = await credentials_manager.get_scanning_modes(test_program.id)

        # Verify structure for readiness response
        assert "available_modes" in modes
        assert "warnings" in modes
        assert modes["available_modes"] == ["unauthenticated"]

    @pytest.mark.asyncio
    async def test_multiple_templates_with_different_requirements(
        self, test_program: Program, credentials_manager: CredentialsManager, db: AsyncSession, scope_policy: ScopePolicy
    ):
        """Test that different templates handle credentials correctly."""
        # Set up metadata and credentials
        meta = OpportunityAccessMetadata(
            id=uuid4(),
            program_id=test_program.id,
            access_type="unauthenticated",
            enabled=True,
        )
        db.add(meta)
        await db.commit()

        modes = await credentials_manager.get_scanning_modes(test_program.id)

        # Test recon_surface_map (all public)
        phase_specs, metadata = build_phase_specs_for_template(
            template_name="workflow_recon_surface_map",
            target="example.com",
            safe_mode=False,
            scope_policy=scope_policy,
            available_modes=modes["available_modes"],
        )
        assert len(phase_specs) > 0
        assert metadata["steps_enabled"] == len(phase_specs)
        assert len(metadata["steps_skipped_due_to_credentials"]) == 0

        # Test secret_scan (all public)
        phase_specs, metadata = build_phase_specs_for_template(
            template_name="workflow_secret_exposure_scan",
            target="https://github.com/example/repo",
            safe_mode=False,
            scope_policy=scope_policy,
            available_modes=modes["available_modes"],
        )
        assert len(phase_specs) > 0
        assert len(metadata["steps_skipped_due_to_credentials"]) == 0

    @pytest.mark.asyncio
    async def test_workflow_metadata_includes_scanning_modes(
        self, test_program: Program, credentials_manager: CredentialsManager, db: AsyncSession, scope_policy: ScopePolicy
    ):
        """Test that workflow metadata includes available_scanning_modes."""
        meta = OpportunityAccessMetadata(
            id=uuid4(),
            program_id=test_program.id,
            access_type="unauthenticated",
            enabled=True,
        )
        db.add(meta)
        await db.commit()

        modes = await credentials_manager.get_scanning_modes(test_program.id)

        phase_specs, metadata = build_phase_specs_for_template(
            template_name="workflow_recon_surface_map",
            target="example.com",
            safe_mode=False,
            scope_policy=scope_policy,
            available_modes=modes["available_modes"],
        )

        assert "available_scanning_modes" in metadata
        assert metadata["available_scanning_modes"] == ["unauthenticated"]
        assert "steps_skipped_due_to_credentials" in metadata

    @pytest.mark.asyncio
    async def test_credential_access_tracking_during_workflow(
        self, test_program: Program, credentials_manager: CredentialsManager, db: AsyncSession
    ):
        """Test that accessing credentials updates access tracking."""
        # Set up metadata and credential
        meta = OpportunityAccessMetadata(
            id=uuid4(),
            program_id=test_program.id,
            access_type="api_key",
            enabled=True,
        )
        db.add(meta)
        await db.commit()

        # Store credential
        cred = await credentials_manager.store_credential(
            program_id=test_program.id,
            access_type="api_key",
            credentials={"api_key": "test-key"},
            username="api_user",
            user_id="analyst1",
        )

        assert cred.access_count == 0

        # Access the credential (simulating workflow retrieval)
        retrieved = await credentials_manager.get_credential(
            program_id=test_program.id,
            access_type="api_key",
        )

        # Verify access tracking updated
        db.expire(cred)
        await db.refresh(cred)
        assert cred.access_count == 1
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_all_templates_defined_with_requires_mode(self):
        """Test that all workflow template steps have requires_mode defined."""
        for template_name, template in WORKFLOW_TEMPLATES.items():
            for step in template.steps:
                assert hasattr(step, "requires_mode"), (
                    f"Step {step.tool} in {template_name} missing requires_mode attribute"
                )
                assert step.requires_mode in [None, "user_account", "api_key", "hunter_account"], (
                    f"Invalid requires_mode '{step.requires_mode}' in {template_name}/{step.tool}"
                )
