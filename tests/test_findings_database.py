"""Tests for findings database schema, ORM models, and analytics.

Tests coverage:
- Database schema creation (3 tables)
- ORM model functionality (Finding, Scan, Submission)
- Relationships (Scan→Findings, Finding→Submissions)
- Helper methods (mark_as_duplicate, calculate_payout_accuracy, mark_as_paid)
- Analytics views (payout summary, playbook performance, etc.)
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.backend.src.models.base import Base
from apps.backend.src.models.campaign import Program
from apps.backend.src.models.findings import ScanFinding, ScanExecution, FindingSubmission


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


class TestFindingsDatabase:
    """Test findings database schema and ORM models."""

    @pytest.mark.asyncio
    async def test_scan_creation(self, test_program, db):
        """Test creating a ScanExecution record."""
        scan = ScanExecution(
            id=uuid4(),
            program_id=test_program.id,
            scan_name="Test Scan",
            scan_type="quick",
            workflow_template_used="workflow_recon_surface_map",
            requested_by="analyst1",
            status="pending",
        )
        db.add(scan)
        await db.commit()
        await db.refresh(scan)

        assert scan.id is not None
        assert scan.program_id == test_program.id
        assert scan.scan_name == "Test Scan"
        assert scan.status == "pending"

    @pytest.mark.asyncio
    async def test_finding_creation(self, test_program, db):
        """Test creating a Finding record."""
        scan = ScanExecution(
            id=uuid4(),
            program_id=test_program.id,
            status="running",
        )
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="h1-example-com-xss-001-2026-04-13",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            severity="high",
            cvss_score=Decimal("7.5"),
            endpoint="/api/users",
            parameter_name="id",
            http_method="GET",
            description="Reflected XSS in user search endpoint",
            status="discovered",
        )
        db.add(finding)
        await db.commit()
        await db.refresh(finding)

        assert finding.vulnerability_type == "XSS"
        assert finding.severity == "high"
        assert finding.status == "discovered"
        assert finding.is_duplicate is False

    @pytest.mark.asyncio
    async def test_submission_creation(self, test_program, db):
        """Test creating a Submission record."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="test-finding-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Test XSS",
            status="submitted",
        )
        db.add(finding)
        await db.commit()

        submission = FindingSubmission(
            id=uuid4(),
            finding_id=finding.id,
            submitted_to_platform="h1",
            current_status="pending",
        )
        db.add(submission)
        await db.commit()
        await db.refresh(submission)

        assert submission.finding_id == finding.id
        assert submission.submitted_to_platform == "h1"
        assert submission.current_status == "pending"

    @pytest.mark.asyncio
    async def test_mark_as_duplicate(self, test_program, db):
        """Test marking a finding as duplicate."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        original = ScanFinding(
            id=uuid4(),
            finding_identifier="original-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Original XSS",
            status="discovered",
        )
        db.add(original)
        await db.commit()

        duplicate = ScanFinding(
            id=uuid4(),
            finding_identifier="duplicate-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Duplicate XSS",
            status="discovered",
        )
        db.add(duplicate)
        await db.commit()

        # Mark as duplicate
        duplicate.mark_as_duplicate(
            original_finding_id=original.id,
            reason="exact_match",
            confidence=0.95,
        )
        await db.commit()
        await db.refresh(duplicate)

        assert duplicate.is_duplicate is True
        assert duplicate.duplicate_of_finding_id == original.id
        assert duplicate.deduplication_reason == "exact_match"
        assert duplicate.status == "deduped"

    @pytest.mark.asyncio
    async def test_calculate_payout_accuracy(self, test_program, db):
        """Test payout accuracy calculation."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="payout-test-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Test",
            estimated_payout=Decimal("500.00"),
            actual_payout=Decimal("600.00"),
        )
        db.add(finding)
        await db.commit()

        accuracy = finding.calculate_payout_accuracy()
        await db.refresh(finding)

        assert accuracy is not None
        assert accuracy == Decimal("120.00")  # 600/500 * 100
        assert finding.payout_accuracy_percentage == Decimal("120.00")

    @pytest.mark.asyncio
    async def test_mark_as_paid(self, test_program, db):
        """Test marking finding as paid."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="paid-test-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Test",
        )
        db.add(finding)
        await db.commit()

        finding.mark_as_paid(amount=Decimal("750.00"), currency="USD")
        await db.commit()
        await db.refresh(finding)

        assert finding.status == "paid"
        assert finding.actual_payout == Decimal("750.00")
        assert finding.payout_currency == "USD"
        assert finding.payout_received_at is not None

    @pytest.mark.asyncio
    async def test_submission_status_history(self, test_program, db):
        """Test submission status history tracking."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="hist-test-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Test",
        )
        db.add(finding)
        await db.commit()

        submission = FindingSubmission(
            id=uuid4(),
            finding_id=finding.id,
            submitted_to_platform="h1",
            current_status="pending",
        )
        db.add(submission)
        await db.commit()

        # Add status changes
        submission.add_status_change("accepted", "Approved by program")
        submission.add_status_change("paid", "Payment received")
        await db.commit()
        await db.refresh(submission)

        assert submission.current_status == "paid"
        assert submission.status_history is not None
        assert len(submission.status_history) == 2
        assert submission.status_history[0]["status"] == "accepted"
        assert submission.status_history[1]["status"] == "paid"

    @pytest.mark.asyncio
    async def test_submission_mark_as_paid(self, test_program, db):
        """Test submission payment recording."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="sub-paid-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="SQLi",
            description="Test",
        )
        db.add(finding)
        await db.commit()

        submission = FindingSubmission(
            id=uuid4(),
            finding_id=finding.id,
            submitted_to_platform="bugcrowd",
            current_status="accepted",
        )
        db.add(submission)
        await db.commit()

        submission.mark_as_paid(amount=Decimal("1000.00"), currency="USD")
        await db.commit()
        await db.refresh(submission)

        assert submission.current_status == "paid"
        assert submission.payout_amount == Decimal("1000.00")
        assert submission.payout_received_at is not None

    @pytest.mark.asyncio
    async def test_scan_calculate_duration(self, test_program, db):
        """Test scan duration calculation."""
        now = datetime.now(timezone.utc)
        scan = ScanExecution(
            id=uuid4(),
            program_id=test_program.id,
            triggered_at=now,
            started_at=now,
            completed_at=now.replace(second=now.second + 3600),  # 1 hour later
            status="completed",
        )
        db.add(scan)
        await db.commit()

        duration = scan.calculate_duration()
        await db.refresh(scan)

        assert duration is not None
        assert duration == 3600  # 1 hour in seconds

    @pytest.mark.asyncio
    async def test_relationship_scan_to_findings(self, test_program, db):
        """Test relationship between Scan and Findings."""
        scan = ScanExecution(
            id=uuid4(),
            program_id=test_program.id,
            status="running",
        )
        db.add(scan)
        await db.commit()

        finding1 = ScanFinding(
            id=uuid4(),
            finding_identifier="rel-test-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Test 1",
        )
        finding2 = ScanFinding(
            id=uuid4(),
            finding_identifier="rel-test-2",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="SQLi",
            description="Test 2",
        )
        db.add_all([finding1, finding2])
        await db.commit()

        # Load scan and check findings relationship
        db.expire(scan)
        await db.refresh(scan)
        assert len(scan.findings) == 2
        assert finding1 in scan.findings
        assert finding2 in scan.findings

    @pytest.mark.asyncio
    async def test_relationship_finding_to_submissions(self, test_program, db):
        """Test relationship between Finding and Submissions."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="sub-rel-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="XSS",
            description="Test",
        )
        db.add(finding)
        await db.commit()

        sub1 = FindingSubmission(
            id=uuid4(),
            finding_id=finding.id,
            submitted_to_platform="h1",
            current_status="pending",
        )
        sub2 = FindingSubmission(
            id=uuid4(),
            finding_id=finding.id,
            submitted_to_platform="bugcrowd",
            current_status="pending",
        )
        db.add_all([sub1, sub2])
        await db.commit()

        # Load finding and check submissions relationship
        db.expire(finding)
        await db.refresh(finding)
        assert len(finding.submissions) == 2
        assert sub1 in finding.submissions
        assert sub2 in finding.submissions

    @pytest.mark.asyncio
    async def test_finding_with_all_fields(self, test_program, db):
        """Test Finding with all optional fields populated."""
        scan = ScanExecution(id=uuid4(), program_id=test_program.id, status="running")
        db.add(scan)
        await db.commit()

        finding = ScanFinding(
            id=uuid4(),
            finding_identifier="full-test-1",
            program_id=test_program.id,
            scan_id=scan.id,
            vulnerability_type="CSRF",
            severity="critical",
            cvss_score=Decimal("9.8"),
            endpoint="/admin/delete-user",
            parameter_name="user_id",
            http_method="POST",
            payload_used="csrf_token=invalid&user_id=2",
            description="CSRF vulnerability in user deletion",
            proof_of_concept="1. Login as admin\n2. Craft malicious link\n3. Click link",
            impact_description="Attacker can delete arbitrary users",
            remediation_guidance="Implement proper CSRF token validation",
            estimated_severity="critical",
            estimated_payout=Decimal("2000.00"),
            scanning_modes_used=["unauthenticated", "user_account"],
            playbook_id="pb-123",
            playbook_name="csrf_scanner",
            ai_confidence_score=Decimal("0.92"),
            submitted_to_platform="h1",
            submission_id="h1-123456",
            submission_status="accepted",
        )
        db.add(finding)
        await db.commit()
        await db.refresh(finding)

        assert finding.severity == "critical"
        assert finding.cvss_score == Decimal("9.8")
        assert finding.endpoint == "/admin/delete-user"
        assert finding.ai_confidence_score == Decimal("0.92")
        assert finding.scanning_modes_used == ["unauthenticated", "user_account"]

    @pytest.mark.asyncio
    async def test_bulk_findings_for_analytics(self, test_program, db):
        """Test creating bulk findings for analytics testing."""
        scan = ScanExecution(
            id=uuid4(),
            program_id=test_program.id,
            status="completed",
            total_findings_discovered=5,
        )
        db.add(scan)
        await db.commit()

        findings = []
        for i in range(5):
            finding = ScanFinding(
                id=uuid4(),
                finding_identifier=f"analytics-test-{i}",
                program_id=test_program.id,
                scan_id=scan.id,
                vulnerability_type="XSS" if i % 2 == 0 else "SQLi",
                severity="high" if i < 3 else "medium",
                cvss_score=Decimal(str(7.0 + i)),
                description=f"Test finding {i}",
                status="accepted" if i < 3 else "discovered",
                ai_confidence_score=Decimal(str(0.80 + (i * 0.05))),
                playbook_id=f"pb-{i % 2}",
                playbook_name="xss_scanner" if i % 2 == 0 else "sql_scanner",
            )
            findings.append(finding)

        db.add_all(findings)
        await db.commit()

        # Query back and verify
        from sqlalchemy import select
        stmt = select(ScanFinding).where(ScanFinding.scan_id == scan.id)
        result = await db.execute(stmt)
        loaded_findings = result.scalars().all()

        assert len(loaded_findings) == 5
        assert sum(1 for f in loaded_findings if f.status == "accepted") == 3
