"""Tests for analytics engine including finding collection, submission tracking, and metrics.

Tests coverage:
- Finding collection from playbook results
- Submission tracking and status updates
- Payout recording and accuracy calculation
- Metrics calculation (program, playbook, vulnerability, scan, monthly)
- Analytics API endpoints
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
from apps.backend.src.services.finding_collector import FindingCollector
from apps.backend.src.services.submission_tracker import SubmissionTracker
from apps.backend.src.services.metrics_calculator import MetricsCalculator


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


class TestFindingCollector:
    """Test finding collection service."""

    @pytest.mark.asyncio
    async def test_collect_finding(self, db, test_program, test_scan):
        """Test collecting a single finding."""
        collector = FindingCollector(db)

        playbook_result = {
            "playbook_id": "xss-auth-001",
            "playbook_name": "Authenticated XSS Testing",
            "vulnerability_type": "XSS",
            "endpoint": "/api/users?name={payload}",
            "parameter_name": "name",
            "http_method": "GET",
            "payload_used": "<img src=x onerror='alert(1)'>",
            "severity": "high",
            "cvss_score": 7.2,
            "description": "Reflected XSS in user search",
            "proof_of_concept": "GET /api/users?name=<img...>",
            "impact": "Attacker can steal session cookies",
            "remediation": "Use HTML entity encoding",
            "ai_confidence": 0.95,
            "scanning_mode": "user_account",
        }

        finding = await collector.collect_finding_from_playbook(
            test_program.id, test_scan.id, playbook_result
        )

        assert finding.id is not None
        assert finding.vulnerability_type == "XSS"
        assert finding.severity == "high"
        assert finding.cvss_score == Decimal("7.2")
        assert finding.status == "discovered"
        assert finding.is_duplicate is False
        assert finding.estimated_payout is not None

    @pytest.mark.asyncio
    async def test_payout_estimation(self, db, test_program, test_scan):
        """Test payout estimation based on severity."""
        collector = FindingCollector(db)

        # Test critical finding
        critical_result = {
            "playbook_id": "sql-injection-001",
            "playbook_name": "SQL Injection Testing",
            "vulnerability_type": "SQLi",
            "severity": "critical",
            "endpoint": "/api/search",
            "parameter_name": "q",
            "http_method": "GET",
            "payload_used": "' OR '1'='1",
            "description": "SQL Injection vulnerability",
            "ai_confidence": 0.99,
            "scanning_mode": "unauthenticated",
        }

        critical_finding = await collector.collect_finding_from_playbook(
            test_program.id, test_scan.id, critical_result
        )

        # Critical should have high estimate
        assert critical_finding.estimated_payout >= Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_bulk_collect_findings(self, db, test_program, test_scan):
        """Test collecting multiple findings in bulk."""
        collector = FindingCollector(db)

        results = [
            {
                "playbook_id": "xss-001",
                "playbook_name": "XSS Tester",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/page1",
                "parameter_name": "param1",
                "http_method": "GET",
                "payload_used": "<script>alert(1)</script>",
                "description": "XSS 1",
                "ai_confidence": 0.9,
                "scanning_mode": "unauthenticated",
            },
            {
                "playbook_id": "xss-001",
                "playbook_name": "XSS Tester",
                "vulnerability_type": "XSS",
                "severity": "medium",
                "endpoint": "/page2",
                "parameter_name": "param2",
                "http_method": "POST",
                "payload_used": "<svg onload=alert(1)>",
                "description": "XSS 2",
                "ai_confidence": 0.85,
                "scanning_mode": "unauthenticated",
            },
        ]

        findings = await collector.bulk_collect_findings(
            test_program.id, test_scan.id, results
        )

        assert len(findings) == 2
        assert findings[0].vulnerability_type == "XSS"
        assert findings[1].severity == "medium"


class TestSubmissionTracker:
    """Test submission tracking service."""

    @pytest.mark.asyncio
    async def test_record_submission(self, db, test_program, test_scan):
        """Test recording a submission."""
        collector = FindingCollector(db)
        tracker = SubmissionTracker(db)

        # Create a finding
        playbook_result = {
            "playbook_id": "test-001",
            "playbook_name": "Test Playbook",
            "vulnerability_type": "XSS",
            "severity": "high",
            "endpoint": "/test",
            "parameter_name": "test",
            "http_method": "GET",
            "payload_used": "<script>",
            "description": "Test",
            "ai_confidence": 0.9,
            "scanning_mode": "unauthenticated",
        }
        finding = await collector.collect_finding_from_playbook(
            test_program.id, test_scan.id, playbook_result
        )
        finding.validation_status = "approved_for_submission"
        await db.commit()

        # Record submission
        submission = await tracker.record_submission(
            finding.id,
            "h1",
            "h1-123456",
            "https://hackerone.com/reports/123456",
        )

        assert submission.finding_id == finding.id
        assert submission.submitted_to_platform == "h1"
        assert submission.current_status == "pending"
        assert len(submission.status_history) == 1

    @pytest.mark.asyncio
    async def test_update_submission_status(self, db, test_program, test_scan):
        """Test updating submission status."""
        collector = FindingCollector(db)
        tracker = SubmissionTracker(db)

        # Create finding and submission
        playbook_result = {
            "playbook_id": "test-001",
            "playbook_name": "Test",
            "vulnerability_type": "XSS",
            "severity": "high",
            "endpoint": "/test",
            "parameter_name": "test",
            "http_method": "GET",
            "payload_used": "<script>",
            "description": "Test",
            "ai_confidence": 0.9,
            "scanning_mode": "unauthenticated",
        }
        finding = await collector.collect_finding_from_playbook(
            test_program.id, test_scan.id, playbook_result
        )
        finding.validation_status = "approved_for_submission"
        await db.commit()

        submission = await tracker.record_submission(
            finding.id, "h1", "h1-123456"
        )
        await db.commit()

        # Update status
        updated = await tracker.update_submission_status(
            finding.id, "h1", "accepted", "Great report!"
        )
        # Refresh after update to ensure all changes are loaded
        await db.refresh(updated)

        assert updated.current_status == "accepted"
        assert len(updated.status_history) == 2
        assert updated.status_history[1]["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_record_payout(self, db, test_program, test_scan):
        """Test recording payout."""
        collector = FindingCollector(db)
        tracker = SubmissionTracker(db)

        # Create finding
        playbook_result = {
            "playbook_id": "test-001",
            "playbook_name": "Test",
            "vulnerability_type": "XSS",
            "severity": "high",
            "endpoint": "/test",
            "parameter_name": "test",
            "http_method": "GET",
            "payload_used": "<script>",
            "description": "Test",
            "ai_confidence": 0.9,
            "scanning_mode": "unauthenticated",
        }
        finding = await collector.collect_finding_from_playbook(
            test_program.id, test_scan.id, playbook_result
        )
        finding.validation_status = "approved_for_submission"
        await db.commit()

        submission = await tracker.record_submission(finding.id, "h1", "h1-123")
        await db.commit()

        # Record payout
        updated_finding, updated_submission = await tracker.record_payout(
            finding.id, "h1", Decimal("1500.00")
        )
        await db.commit()

        assert updated_finding.actual_payout == Decimal("1500.00")
        assert updated_finding.status == "paid"
        assert updated_finding.payout_received_at is not None
        # Check accuracy (estimated was $500 (high severity), actual was $1500, so 300%)
        assert updated_finding.payout_accuracy_percentage == Decimal("300.00")


class TestMetricsCalculator:
    """Test metrics calculation service."""

    @pytest.mark.asyncio
    async def test_calculate_program_metrics(self, db, test_program, test_scan):
        """Test program metrics calculation."""
        collector = FindingCollector(db)
        calculator = MetricsCalculator(db)

        # Create findings
        results = [
            {
                "playbook_id": "xss-001",
                "playbook_name": "XSS",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/page1",
                "parameter_name": "p1",
                "http_method": "GET",
                "payload_used": "<img>",
                "description": "XSS 1",
                "ai_confidence": 0.95,
                "scanning_mode": "unauthenticated",
            },
            {
                "playbook_id": "xss-001",
                "playbook_name": "XSS",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/page2",
                "parameter_name": "p2",
                "http_method": "GET",
                "payload_used": "<svg>",
                "description": "XSS 2",
                "ai_confidence": 0.90,
                "scanning_mode": "unauthenticated",
            },
        ]
        await collector.bulk_collect_findings(test_program.id, test_scan.id, results)
        await db.commit()

        # Calculate metrics
        metrics = await calculator.calculate_program_metrics(test_program.id)

        assert metrics["metrics"]["total_findings"] == 2
        assert metrics["metrics"]["unique_findings"] == 2
        assert metrics["metrics"]["duplicate_findings"] == 0
        assert metrics["metrics"]["average_ai_confidence"] > 0

    @pytest.mark.asyncio
    async def test_calculate_playbook_performance(self, db, test_program, test_scan):
        """Test playbook performance calculation."""
        collector = FindingCollector(db)
        calculator = MetricsCalculator(db)

        # Create findings from different playbooks
        await collector.collect_finding_from_playbook(
            test_program.id,
            test_scan.id,
            {
                "playbook_id": "xss-001",
                "playbook_name": "XSS Tester",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/a",
                "parameter_name": "p",
                "http_method": "GET",
                "payload_used": "<img>",
                "description": "XSS",
                "ai_confidence": 0.95,
                "scanning_mode": "unauthenticated",
            },
        )
        await db.commit()

        performance = await calculator.calculate_playbook_performance()

        assert len(performance) > 0
        assert performance[0]["playbook_id"] == "xss-001"
        assert performance[0]["total_findings"] >= 1

    @pytest.mark.asyncio
    async def test_calculate_vulnerability_distribution(
        self, db, test_program, test_scan
    ):
        """Test vulnerability distribution calculation."""
        collector = FindingCollector(db)
        calculator = MetricsCalculator(db)

        # Create different vuln types
        results = [
            {
                "playbook_id": "xss-001",
                "playbook_name": "XSS",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/a",
                "parameter_name": "p",
                "http_method": "GET",
                "payload_used": "<img>",
                "description": "XSS",
                "ai_confidence": 0.95,
                "scanning_mode": "unauthenticated",
            },
            {
                "playbook_id": "sql-001",
                "playbook_name": "SQL",
                "vulnerability_type": "SQLi",
                "severity": "critical",
                "endpoint": "/b",
                "parameter_name": "q",
                "http_method": "GET",
                "payload_used": "' OR '1'='1",
                "description": "SQLi",
                "ai_confidence": 0.99,
                "scanning_mode": "unauthenticated",
            },
        ]
        await collector.bulk_collect_findings(test_program.id, test_scan.id, results)
        await db.commit()

        distribution = await calculator.calculate_vulnerability_distribution()

        assert len(distribution["vulnerability_distribution"]) == 2
        types = {d["vulnerability_type"] for d in distribution["vulnerability_distribution"]}
        assert "XSS" in types
        assert "SQLi" in types

    @pytest.mark.asyncio
    async def test_calculate_scan_effectiveness(self, db, test_program, test_scan):
        """Test scan effectiveness calculation."""
        collector = FindingCollector(db)
        calculator = MetricsCalculator(db)

        # Complete the scan
        test_scan.completed_at = datetime.now(timezone.utc)
        test_scan.duration_seconds = 3600
        await db.flush()

        # Add findings
        await collector.collect_finding_from_playbook(
            test_program.id,
            test_scan.id,
            {
                "playbook_id": "test-001",
                "playbook_name": "Test",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/test",
                "parameter_name": "p",
                "http_method": "GET",
                "payload_used": "<img>",
                "description": "Test",
                "ai_confidence": 0.95,
                "scanning_mode": "unauthenticated",
            },
        )
        await db.commit()

        effectiveness = await calculator.calculate_scan_effectiveness(test_scan.id)

        assert effectiveness["metrics"]["total_findings"] == 1
        assert effectiveness["metrics"]["scan_duration_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_calculate_monthly_summary(self, db, test_program, test_scan):
        """Test monthly summary calculation."""
        collector = FindingCollector(db)
        calculator = MetricsCalculator(db)

        # Add findings
        await collector.collect_finding_from_playbook(
            test_program.id,
            test_scan.id,
            {
                "playbook_id": "test-001",
                "playbook_name": "Test",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/test",
                "parameter_name": "p",
                "http_method": "GET",
                "payload_used": "<img>",
                "description": "Test",
                "ai_confidence": 0.95,
                "scanning_mode": "unauthenticated",
            },
        )
        await db.commit()

        summary = await calculator.calculate_monthly_summary()

        assert "monthly_trends" in summary
        assert len(summary["monthly_trends"]) > 0

    @pytest.mark.asyncio
    async def test_get_top_programs_by_payout(
        self, db, test_program, test_scan
    ):
        """Test getting top programs by payout."""
        collector = FindingCollector(db)
        calculator = MetricsCalculator(db)

        # Create finding and record payout
        finding = await collector.collect_finding_from_playbook(
            test_program.id,
            test_scan.id,
            {
                "playbook_id": "test-001",
                "playbook_name": "Test",
                "vulnerability_type": "XSS",
                "severity": "high",
                "endpoint": "/test",
                "parameter_name": "p",
                "http_method": "GET",
                "payload_used": "<img>",
                "description": "Test",
                "ai_confidence": 0.95,
                "scanning_mode": "unauthenticated",
            },
        )
        await db.commit()

        # Update with payout
        finding.actual_payout = Decimal("2000.00")
        finding.status = "paid"
        await db.flush()
        await db.commit()

        top = await calculator.get_top_programs_by_payout(10)

        assert len(top) > 0
        assert top[0]["program_id"] == str(test_program.id)
