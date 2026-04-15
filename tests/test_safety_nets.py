"""Tests for safety nets system (scope validation, kill switch, rate limits).

Tests coverage:
- Scope validation (sensitive paths, endpoints, domains, ports, IPs)
- Immediate abort on violation
- Rate limit handling and exponential backoff
- Kill switch request and status checking
- API failure graceful degradation
- Immutable violation audit trail
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.backend.src.models.base import Base
from apps.backend.src.models.campaign import Program
from apps.backend.src.models.findings import ScanExecution
from apps.backend.src.models.scope_violations import ScopeViolation
from apps.backend.src.services.api_failure_handler import APIFailureHandler
from apps.backend.src.services.rate_limit_handler import RateLimitHandler
from apps.backend.src.services.scan_kill_switch import ScanKillSwitch
from apps.backend.src.services.scope_enforced_orchestrator import ScopeEnforcedOrchestrator
from apps.backend.src.services.scope_validator import ScopeValidator, ScopeViolationType


@pytest_asyncio.fixture
async def db():
    """Create an in-memory SQLite database for testing."""
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
    """Create a test program with scope configuration."""
    program = Program(
        id=uuid4(),
        name="Test Program",
        status="ACTIVE",
        config_json={
            "opportunity": {"program_url": "https://example.com"},
            "scope": {
                "allowed_domains": ["example.com", "api.example.com"],
                "allowed_ports": [80, 443],
                "allowed_ips": ["192.168.1.1"],
                "allowed_cidrs": ["10.0.0.0/8"],
                "included_endpoints": ["/api/*", "/public/*"],
                "excluded_endpoints": ["/api/admin/*"],
                "excluded_parameters": ["password", "secret"],
            },
        },
    )
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return program


@pytest_asyncio.fixture
async def test_scan(db, test_program):
    """Create a test scan."""
    scan = ScanExecution(
        id=uuid4(),
        program_id=test_program.id,
        scan_name="Test Scan",
        scan_type="comprehensive",
        status="running",
        triggered_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan


class TestScopeValidator:
    """Test real-time scope validation."""

    @pytest.mark.asyncio
    async def test_sensitive_path_blocked(self, db, test_program):
        """Test that sensitive paths are blocked immediately."""
        validator = ScopeValidator(db)

        is_valid, violation_type, reason = await validator.validate_request(
            program_id=test_program.id,
            target_url="https://example.com/admin",
            target_endpoint="/admin",
        )

        assert not is_valid
        assert violation_type == ScopeViolationType.SENSITIVE_PATH
        assert "Sensitive path" in reason

    @pytest.mark.asyncio
    async def test_endpoint_out_of_scope(self, db, test_program):
        """Test that endpoints not in scope are rejected."""
        validator = ScopeValidator(db)

        is_valid, violation_type, reason = await validator.validate_request(
            program_id=test_program.id,
            target_url="https://example.com/other",
            target_endpoint="/other",
        )

        assert not is_valid
        assert violation_type == ScopeViolationType.ENDPOINT_OUT_OF_SCOPE

    @pytest.mark.asyncio
    async def test_endpoint_in_scope(self, db, test_program):
        """Test that in-scope endpoints pass validation."""
        validator = ScopeValidator(db)

        is_valid, violation_type, reason = await validator.validate_request(
            program_id=test_program.id,
            target_url="https://example.com/api/users",
            target_endpoint="/api/users",
        )

        assert is_valid
        assert violation_type is None
        assert reason is None

    @pytest.mark.asyncio
    async def test_domain_out_of_scope(self, db, test_program):
        """Test that unauthorized domains are rejected."""
        validator = ScopeValidator(db)

        is_valid, violation_type, reason = await validator.validate_request(
            program_id=test_program.id,
            target_url="https://evil.com/api/users",
            target_endpoint="/api/users",
        )

        assert not is_valid
        assert violation_type == ScopeViolationType.DOMAIN_OUT_OF_SCOPE

    @pytest.mark.asyncio
    async def test_port_out_of_scope(self, db, test_program):
        """Test that unlisted ports are rejected."""
        validator = ScopeValidator(db)

        is_valid, violation_type, reason = await validator.validate_request(
            program_id=test_program.id,
            target_url="https://example.com:8080/api/users",
            target_endpoint="/api/users",
            target_port=8080,
        )

        assert not is_valid
        assert violation_type == ScopeViolationType.PORT_OUT_OF_SCOPE

    @pytest.mark.asyncio
    async def test_ip_in_scope_cidr(self, db, test_program):
        """Test that IPs in allowed CIDR pass validation."""
        validator = ScopeValidator(db)

        is_valid, violation_type, reason = await validator.validate_request(
            program_id=test_program.id,
            target_url="https://10.1.2.3/api/users",
            target_endpoint="/api/users",
            target_ip="10.1.2.3",
        )

        assert is_valid

    @pytest.mark.asyncio
    async def test_ip_out_of_scope(self, db, test_program):
        """Test that IPs outside allowed ranges are rejected."""
        validator = ScopeValidator(db)

        is_valid, violation_type, reason = await validator.validate_request(
            program_id=test_program.id,
            target_url="https://172.16.0.1/api/users",
            target_endpoint="/api/users",
            target_ip="172.16.0.1",
        )

        assert not is_valid
        assert violation_type == ScopeViolationType.IP_OUT_OF_SCOPE

    @pytest.mark.asyncio
    async def test_scope_violation_logged_immutably(self, db, test_program, test_scan):
        """Test that scope violations are logged immutably to DB."""
        validator = ScopeValidator(db)

        # Trigger violation with endpoint that matches scope but domain doesn't
        await validator.validate_request(
            program_id=test_program.id,
            target_url="https://evil.com/api/users",
            target_endpoint="/api/users",
            scan_id=test_scan.id,
        )

        # Commit to ensure violation is persisted
        await db.commit()

        # Query violations
        from sqlalchemy.future import select

        stmt = select(ScopeViolation).where(ScopeViolation.program_id == test_program.id)
        result = await db.execute(stmt)
        violations = result.scalars().all()

        assert len(violations) > 0
        violation = violations[0]
        assert violation.program_id == test_program.id
        assert violation.violation_type == ScopeViolationType.DOMAIN_OUT_OF_SCOPE

    @pytest.mark.asyncio
    async def test_scope_caching(self, db, test_program):
        """Test that scope config is cached for performance."""
        validator = ScopeValidator(db)

        # First request (DB hit)
        await validator.validate_request(
            program_id=test_program.id,
            target_url="https://example.com/api/users",
            target_endpoint="/api/users",
        )

        # Second request (should use cache)
        await validator.validate_request(
            program_id=test_program.id,
            target_url="https://example.com/api/posts",
            target_endpoint="/api/posts",
        )

        # Check cache stats
        stats = validator.get_stats()
        assert stats["request_count"] == 2
        assert stats["cached_configs"] == 1


class TestScopeEnforcedOrchestrator:
    """Test orchestrator with scope enforcement."""

    @pytest.mark.asyncio
    async def test_orchestrator_aborts_on_violation(self, db, test_program, test_scan):
        """Test that orchestrator aborts immediately on scope violation."""
        validator = ScopeValidator(db)
        orchestrator = ScopeEnforcedOrchestrator(db, validator)

        playbook = {
            "id": "test-playbook",
            "name": "Test Playbook",
            "target_endpoint": "/api/users",
        }

        target_urls = [
            "https://example.com/api/users",  # Valid
            "https://evil.com/api/users",  # Invalid - should abort here
            "https://example.com/api/posts",  # Should not reach here
        ]

        result = await orchestrator.execute_playbook_with_scope_check(
            program_id=test_program.id,
            scan_id=test_scan.id,
            playbook=playbook,
            target_urls=target_urls,
        )

        # Should abort after first violation
        assert result["aborted"]
        assert result["scope_violations"] == 1
        assert result["requests_made"] == 1  # Only first valid request
        assert orchestrator.scan_aborted


class TestRateLimitHandler:
    """Test rate limit detection and backoff."""

    @pytest.mark.asyncio
    async def test_rate_limit_backoff(self):
        """Test that 429 responses trigger exponential backoff and retry."""
        handler = RateLimitHandler()

        class FakeResponse:
            status_code = 429
            headers = {}

        response = FakeResponse()

        # First call should return True (retry)
        should_retry = await handler.handle_response(response)
        assert should_retry
        assert handler.rate_limit_hits == 1

        # Backoff should increase
        initial_backoff = handler.backoff_seconds
        assert initial_backoff > 1.0

    @pytest.mark.asyncio
    async def test_503_backoff(self):
        """Test that 503 responses also trigger backoff."""
        handler = RateLimitHandler()

        class FakeResponse:
            status_code = 503
            headers = {}

        response = FakeResponse()

        should_retry = await handler.handle_response(response)
        assert should_retry
        assert handler.service_unavailable_hits == 1

    @pytest.mark.asyncio
    async def test_normal_response_resets_backoff(self):
        """Test that successful responses reset backoff."""
        handler = RateLimitHandler()

        # Trigger backoff with 429
        class RateLimitResponse:
            status_code = 429
            headers = {}

        await handler.handle_response(RateLimitResponse())
        assert handler.backoff_seconds > 1.0

        # Normal response should reset
        class NormalResponse:
            status_code = 200
            headers = {}

        should_retry = await handler.handle_response(NormalResponse())
        assert not should_retry
        assert handler.backoff_seconds == 1.0


class TestScanKillSwitch:
    """Test emergency kill switch functionality."""

    @pytest.mark.asyncio
    async def test_kill_switch_request_abort(self, db, test_scan):
        """Test that kill switch request sets abort flags."""
        kill_switch = ScanKillSwitch(db)

        result = await kill_switch.request_abort(
            scan_id=test_scan.id,
            reason="Analyst requested abort",
            requested_by="analyst-001",
        )

        assert result["status"] == "kill_switch_activated"

        # Verify DB was updated
        from sqlalchemy.future import select

        stmt = select(ScanExecution).where(ScanExecution.id == test_scan.id)
        result_scan = await db.execute(stmt)
        updated_scan = result_scan.scalars().first()

        assert updated_scan.abort_requested
        assert updated_scan.abort_requested_by == "analyst-001"
        assert updated_scan.abort_reason == "Analyst requested abort"

    @pytest.mark.asyncio
    async def test_kill_switch_is_abort_requested(self, db, test_scan):
        """Test checking if abort has been requested."""
        kill_switch = ScanKillSwitch(db)

        # Initially false
        is_requested = await kill_switch.is_abort_requested(test_scan.id)
        assert not is_requested

        # Request abort
        await kill_switch.request_abort(
            scan_id=test_scan.id,
            reason="Test abort",
            requested_by="analyst-001",
        )

        # Now should be true
        is_requested = await kill_switch.is_abort_requested(test_scan.id)
        assert is_requested

    @pytest.mark.asyncio
    async def test_kill_switch_complete_abort(self, db, test_scan):
        """Test completing the abort (marking scan as aborted)."""
        kill_switch = ScanKillSwitch(db)

        # Request abort
        await kill_switch.request_abort(
            scan_id=test_scan.id,
            reason="Test",
            requested_by="analyst-001",
        )

        # Complete abort
        result = await kill_switch.complete_abort(test_scan.id)
        assert result["status"] == "aborted"

        # Verify scan status
        from sqlalchemy.future import select

        stmt = select(ScanExecution).where(ScanExecution.id == test_scan.id)
        result_scan = await db.execute(stmt)
        updated_scan = result_scan.scalars().first()

        assert updated_scan.status == "cancelled"
        assert updated_scan.completion_status == "kill_switch_activated"


class TestAPIFailureHandler:
    """Test graceful degradation for API failures."""

    def test_vault_down(self):
        """Test handling Vault unavailability."""
        handler = APIFailureHandler()
        result = handler.handle_vault_down()

        assert not result["vault_available"]
        assert result["scanning_modes"] == ["unauthenticated"]

    def test_h1_api_down(self):
        """Test handling H1 API unavailability."""
        handler = APIFailureHandler()
        result = handler.handle_h1_api_down()

        assert not result["h1_available"]
        assert result["queued_findings"]

    def test_intigriti_api_down(self):
        """Test handling Intigriti API unavailability."""
        handler = APIFailureHandler()
        result = handler.handle_intigriti_api_down()

        assert not result["intigriti_available"]
        assert result["queued_findings"]

    @pytest.mark.asyncio
    async def test_safe_call_with_failure(self):
        """Test safe_call returns fallback on error."""
        handler = APIFailureHandler()

        async def failing_coro():
            raise ValueError("Test error")

        result = await handler.safe_call(
            failing_coro(),
            fallback_value={"default": "value"},
            error_context="Test",
        )

        assert result == {"default": "value"}

    @pytest.mark.asyncio
    async def test_safe_call_with_success(self):
        """Test safe_call returns actual result on success."""
        handler = APIFailureHandler()

        async def success_coro():
            return {"actual": "result"}

        result = await handler.safe_call(
            success_coro(),
            fallback_value={"default": "value"},
            error_context="Test",
        )

        assert result == {"actual": "result"}
