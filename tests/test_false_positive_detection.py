"""Tests for false positive detection and analyst override system.

Tests coverage:
- False positive detection heuristics
- Manual override decisions
- Validation queue management
- Immutable audit trail
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.backend.src.models.base import Base
from apps.backend.src.models.campaign import Program
from apps.backend.src.models.findings import ScanExecution, ScanFinding
from apps.backend.src.models.finding_overrides import FindingOverride
from apps.backend.src.services.false_positive_detector import (
    FalsePositiveDetector,
    FalsePositiveReason,
)
from apps.backend.src.services.finding_override_service import FindingOverrideService
from apps.backend.src.services.validation_queue_manager import ValidationQueueManager


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


@pytest_asyncio.fixture
async def test_finding(db, test_program, test_scan):
    """Create a test finding."""
    finding = ScanFinding(
        id=uuid4(),
        finding_identifier=f"finding-{uuid4()}",
        program_id=test_program.id,
        scan_id=test_scan.id,
        vulnerability_type="XSS",
        severity="high",
        cvss_score=Decimal("7.5"),
        endpoint="/api/users",
        parameter_name="name",
        http_method="GET",
        payload_used="<script>alert(1)</script>",
        description="Stored XSS in user profile",
        proof_of_concept="POST profile -> GET profile -> XSS triggered",
        impact_description="Attacker can steal session cookies",
        remediation_guidance="HTML encode output",
        ai_confidence_score=Decimal("0.95"),
        status="discovered",
        validation_status="pending_analyst_review",
    )
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return finding


class TestFalsePositiveDetector:
    """Test false positive detection heuristics."""

    @pytest.mark.asyncio
    async def test_fp_not_reproducible(self):
        """Test detection of non-reproducible findings."""
        detector = FalsePositiveDetector()

        # Finding dict without PoC
        finding_dict = {
            "vulnerability_type": "XSS",
            "endpoint": "/api/users",
            "description": "Potential XSS",
            "proof_of_concept": None,  # No PoC
            "payload_used": None,  # No payload
        }

        fp_score, reason = await detector.analyze_finding_for_false_positive(
            "test-id", finding_dict
        )

        assert fp_score > 0.0
        assert reason == FalsePositiveReason.NOT_REPRODUCIBLE.value

    @pytest.mark.asyncio
    async def test_fp_expected_behavior(self):
        """Test detection of expected behavior false positives."""
        detector = FalsePositiveDetector()

        finding_dict = {
            "vulnerability_type": "XSS",
            "endpoint": "/error",
            "description": "XSS in error message displaying user input",
            "proof_of_concept": "Test",
            "payload_used": "<script>alert(1)</script>",
        }

        fp_score, reason = await detector.analyze_finding_for_false_positive(
            "test-id", finding_dict
        )

        assert fp_score > 0.0
        assert reason == FalsePositiveReason.EXPECTED_BEHAVIOR.value

    @pytest.mark.asyncio
    async def test_fp_input_validation(self):
        """Test detection of input validation false positives."""
        detector = FalsePositiveDetector()

        finding_dict = {
            "vulnerability_type": "XSS",
            "endpoint": "/api/comments",
            "description": "Input is HTML encoded before display, reducing XSS risk",
            "proof_of_concept": "Test",
            "payload_used": "<script>alert(1)</script>",
        }

        fp_score, reason = await detector.analyze_finding_for_false_positive(
            "test-id", finding_dict
        )

        assert fp_score > 0.0
        assert reason == FalsePositiveReason.INPUT_VALIDATION.value

    @pytest.mark.asyncio
    async def test_fp_mitigating_controls(self):
        """Test detection of mitigated findings."""
        detector = FalsePositiveDetector()

        finding_dict = {
            "vulnerability_type": "XSS",
            "endpoint": "/api/search",
            "description": "XSS detected, but WAF blocks execution",
            "proof_of_concept": "Test",
            "payload_used": "<script>alert(1)</script>",
        }

        fp_score, reason = await detector.analyze_finding_for_false_positive(
            "test-id", finding_dict
        )

        assert fp_score > 0.0

    @pytest.mark.asyncio
    async def test_fp_third_party(self):
        """Test detection of third-party code vulnerabilities."""
        detector = FalsePositiveDetector()

        finding_dict = {
            "vulnerability_type": "Known Vulnerability",
            "endpoint": "/vendor/jquery-2.0.js",
            "description": "jQuery 2.0 XSS vulnerability in vendor code",
            "proof_of_concept": "Known jQuery vuln",
            "payload_used": "<script>alert(1)</script>",
        }

        fp_score, reason = await detector.analyze_finding_for_false_positive(
            "test-id", finding_dict
        )

        assert fp_score > 0.0
        assert reason == FalsePositiveReason.THIRD_PARTY_CODE.value

    @pytest.mark.asyncio
    async def test_fp_real_finding(self):
        """Test that real findings get low FP score."""
        detector = FalsePositiveDetector()

        finding_dict = {
            "vulnerability_type": "XSS",
            "endpoint": "/api/users",
            "description": "Stored XSS in user profile",
            "proof_of_concept": "POST profile -> GET profile -> XSS triggered",
            "payload_used": "<script>alert(1)</script>",
        }

        fp_score, reason = await detector.analyze_finding_for_false_positive(
            "test-id", finding_dict
        )

        # Real finding with full PoC should have low FP score
        assert fp_score == 0.0
        assert reason is None


class TestFindingOverrideService:
    """Test analyst override decisions."""

    @pytest.mark.asyncio
    async def test_exclude_finding(self, db, test_program, test_scan, test_finding):
        """Test excluding a finding."""
        override_service = FindingOverrideService(db)

        result = await override_service.exclude_finding(
            finding_id=test_finding.id,
            reason="Expected behavior in error page",
            analyst_notes="Analyst reviewed and confirmed expected behavior",
            analyst_id="analyst-001",
        )

        assert result["status"] == "success"
        assert result["decision"] == "excluded"

        # Verify finding was updated
        from sqlalchemy.future import select

        stmt = select(ScanFinding).where(ScanFinding.id == test_finding.id)
        result_scan = await db.execute(stmt)
        updated_finding = result_scan.scalars().first()

        assert updated_finding.validation_status == "excluded"
        assert updated_finding.finding_state == "false_positive"

    @pytest.mark.asyncio
    async def test_batch_approve_findings(self, db, test_program, test_scan):
        """Test batch approving multiple findings."""
        override_service = FindingOverrideService(db)

        # Create 5 findings
        finding_ids = []
        for i in range(5):
            finding = ScanFinding(
                id=uuid4(),
                finding_identifier=f"finding-{uuid4()}",
                program_id=test_program.id,
                scan_id=test_scan.id,
                vulnerability_type="XSS",
                severity="high",
                cvss_score=Decimal("7.5"),
                endpoint=f"/api/endpoint{i}",
                parameter_name="test",
                http_method="GET",
                payload_used="<script>",
                description="Test finding",
                proof_of_concept="Test",
                status="discovered",
                validation_status="pending_analyst_review",
            )
            db.add(finding)
            finding_ids.append(finding.id)

        await db.commit()

        result = await override_service.batch_approve_findings(
            finding_ids=finding_ids,
            analyst_id="analyst-001",
        )

        assert result["approved"] == 5
        assert result["failed"] == 0


class TestValidationQueueManager:
    """Test validation queue management."""

    @pytest.mark.asyncio
    async def test_get_validation_queue(self, db, test_program, test_scan, test_finding):
        """Test getting findings in validation queue."""
        queue_mgr = ValidationQueueManager(db)

        queue = await queue_mgr.get_validation_queue(analyst_id="analyst-001")

        assert "queue_size" in queue
        assert "findings" in queue
        assert queue["queue_size"] >= 1

    @pytest.mark.asyncio
    async def test_queue_stats(self, db, test_program, test_scan):
        """Test queue statistics."""
        pending = ScanFinding(
            id=uuid4(),
            finding_identifier=f"finding-{uuid4()}",
            program_id=test_program.id,
            scan_id=test_scan.id,
            vulnerability_type="Test",
            severity="high",
            cvss_score=Decimal("7.5"),
            endpoint="/api/test1",
            parameter_name="test",
            http_method="GET",
            payload_used="test",
            description="Test",
            proof_of_concept="Test",
            status="discovered",
            validation_status="pending_analyst_review",
        )

        approved = ScanFinding(
            id=uuid4(),
            finding_identifier=f"finding-{uuid4()}",
            program_id=test_program.id,
            scan_id=test_scan.id,
            vulnerability_type="Test",
            severity="high",
            cvss_score=Decimal("7.5"),
            endpoint="/api/test2",
            parameter_name="test",
            http_method="GET",
            payload_used="test",
            description="Test",
            proof_of_concept="Test",
            status="discovered",
            validation_status="approved_for_submission",
        )

        excluded = ScanFinding(
            id=uuid4(),
            finding_identifier=f"finding-{uuid4()}",
            program_id=test_program.id,
            scan_id=test_scan.id,
            vulnerability_type="Test",
            severity="low",
            cvss_score=Decimal("3.0"),
            endpoint="/api/test3",
            parameter_name="test",
            http_method="GET",
            payload_used="test",
            description="Test",
            proof_of_concept="Test",
            status="discovered",
            validation_status="excluded",
        )

        db.add_all([pending, approved, excluded])
        await db.commit()

        queue_mgr = ValidationQueueManager(db)
        stats = await queue_mgr.get_queue_stats()

        assert stats["pending_review"] >= 1
        assert stats["approved_for_submission"] >= 1
        assert stats["excluded"] >= 1
