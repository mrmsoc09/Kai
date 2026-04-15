"""Tests for report intelligence engine and PDF generation.

Tests coverage:
- Report specification parsing
- Data filtering and querying
- Narrative generation via Claude API
- PDF document building
- Report storage and retrieval
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
from apps.backend.src.models.findings import ScanFinding, ScanExecution
from apps.backend.src.models.report_spec import (
    ReportSpecification,
    ReportType,
    ReportFilters,
)
from apps.backend.src.services.finding_collector import FindingCollector
from apps.backend.src.services.report_intelligence_engine import ReportIntelligenceEngine


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
        status="completed",
        triggered_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        duration_seconds=3600,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan


@pytest_asyncio.fixture
async def test_findings(db, test_program, test_scan):
    """Create test findings for reporting."""
    collector = FindingCollector(db)

    results = [
        {
            "playbook_id": "xss-001",
            "playbook_name": "XSS Tester",
            "vulnerability_type": "XSS",
            "severity": "high",
            "cvss_score": 7.5,
            "endpoint": "/api/page1",
            "parameter_name": "name",
            "http_method": "GET",
            "payload_used": "<script>alert(1)</script>",
            "description": "Stored XSS in user profile",
            "proof_of_concept": "POST profile -> GET profile -> XSS triggered",
            "impact": "Attacker can steal session cookies",
            "remediation": "HTML encode output",
            "ai_confidence": 0.95,
            "scanning_mode": "unauthenticated",
        },
        {
            "playbook_id": "sql-001",
            "playbook_name": "SQL Injection Tester",
            "vulnerability_type": "SQLi",
            "severity": "critical",
            "cvss_score": 9.8,
            "endpoint": "/api/search",
            "parameter_name": "q",
            "http_method": "GET",
            "payload_used": "' OR '1'='1",
            "description": "SQL injection in search parameter",
            "proof_of_concept": "GET /api/search?q=' OR '1'='1",
            "impact": "Attacker can read all database records",
            "remediation": "Use parameterized queries",
            "ai_confidence": 0.99,
            "scanning_mode": "unauthenticated",
        },
    ]

    findings = await collector.bulk_collect_findings(test_program.id, test_scan.id, results)

    # Add payout data for testing
    for finding in findings:
        finding.actual_payout = Decimal("500.00")
        finding.status = "paid"

    await db.commit()
    return findings


class TestReportSpecification:
    """Test report specification models."""

    def test_create_per_program_report_spec(self):
        """Test creating a per-program report specification."""
        spec = ReportSpecification(
            report_type=ReportType.PER_PROGRAM,
            report_title="Q2 2026 Program Analysis",
            filters=ReportFilters(program_ids=["h1-example"], exclude_duplicates=True),
        )

        assert spec.report_type == ReportType.PER_PROGRAM
        assert spec.report_title == "Q2 2026 Program Analysis"
        assert "h1-example" in spec.filters.program_ids

    def test_create_date_range_report_spec(self):
        """Test creating a date range report specification."""
        from apps.backend.src.models.report_spec import DateRange

        spec = ReportSpecification(
            report_type=ReportType.DATE_RANGE,
            report_title="March 2026 Findings",
            filters=ReportFilters(
                date_range=DateRange(
                    start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                    end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
                ),
                severity_levels=["high", "critical"],
            ),
        )

        assert spec.report_type == ReportType.DATE_RANGE
        assert spec.filters.severity_levels == ["high", "critical"]


class TestReportIntelligenceEngine:
    """Test report intelligence engine."""

    @pytest.mark.asyncio
    async def test_query_filtered_data(self, db, test_program, test_scan, test_findings):
        """Test querying filtered data for report."""
        engine = ReportIntelligenceEngine(db)

        spec = ReportSpecification(
            report_type=ReportType.PER_PROGRAM,
            report_title="Test Report",
            filters=ReportFilters(program_ids=[test_program.id]),
        )

        data = await engine._query_filtered_data(spec)

        assert data["total_findings"] == 2
        assert data["unique_findings"] == 2
        assert data["total_payout"] > 0
        assert len(data["vulnerability_types"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_vulnerability_types(self, db, test_program, test_scan, test_findings):
        """Test vulnerability type analysis."""
        engine = ReportIntelligenceEngine(db)

        vuln_types = engine._analyze_vulnerability_types(test_findings)

        assert len(vuln_types) == 2
        assert vuln_types[0][0] in ["XSS", "SQLi"]

    @pytest.mark.asyncio
    async def test_analyze_playbooks(self, db, test_program, test_scan, test_findings):
        """Test playbook analysis."""
        engine = ReportIntelligenceEngine(db)

        playbooks = engine._analyze_playbooks(test_findings)

        assert len(playbooks) >= 1
        assert any("Tester" in p[0] for p in playbooks)

    @pytest.mark.asyncio
    async def test_analyze_date_range(self, db, test_program, test_scan, test_findings):
        """Test date range analysis."""
        engine = ReportIntelligenceEngine(db)

        date_range = engine._analyze_date_range(test_findings)

        assert date_range["start"] is not None
        assert date_range["end"] is not None

    @pytest.mark.asyncio
    async def test_create_visualizations(self, db, test_program, test_scan, test_findings):
        """Test visualization creation."""
        engine = ReportIntelligenceEngine(db)

        data = await engine._query_filtered_data(
            ReportSpecification(
                report_type=ReportType.PER_PROGRAM,
                report_title="Test",
                filters=ReportFilters(program_ids=[test_program.id]),
            )
        )

        visualizations = await engine._create_visualizations(data)

        # Visualizations should be created as BytesIO objects
        assert isinstance(visualizations, dict)

    @pytest.mark.asyncio
    async def test_generate_key_metrics(self, db, test_program, test_scan, test_findings):
        """Test key metrics narrative generation."""
        engine = ReportIntelligenceEngine(db)

        spec = ReportSpecification(
            report_type=ReportType.PER_PROGRAM,
            report_title="Test Report",
        )

        data = await engine._query_filtered_data(spec)
        metrics = await engine._generate_key_metrics(spec, data)

        assert "Key Performance Indicators" in metrics
        assert "Findings Discovered" in metrics
        assert "Total Revenue" in metrics

    @pytest.mark.asyncio
    async def test_build_pdf_document(self, db, test_program, test_scan, test_findings):
        """Test PDF document building (without Claude API)."""
        engine = ReportIntelligenceEngine(db)

        spec = ReportSpecification(
            report_type=ReportType.PER_PROGRAM,
            report_title="Test PDF Report",
            report_description="Testing PDF generation",
        )

        data = await engine._query_filtered_data(spec)

        narratives = {
            "executive_summary": "This is an executive summary.",
            "key_metrics": "Key metrics include findings discovered.",
            "findings_analysis": "Findings analysis paragraph.",
            "playbook_performance": "Playbook analysis paragraph.",
            "recommendations": "Recommendations paragraph.",
        }

        visualizations = {}

        pdf_bytes = await engine._build_pdf_document(
            spec, data, narratives, visualizations
        )

        assert len(pdf_bytes) > 0
        # Check if it's a PDF or text (if reportlab not available)
        is_pdf = pdf_bytes[:4] == b"%PDF"
        is_text = b"Test PDF Report" in pdf_bytes
        assert is_pdf or is_text, "Output should be PDF or text report"


class TestReportSpecificationEdgeCases:
    """Test edge cases in report specifications."""

    def test_report_spec_with_all_filters(self):
        """Test report spec with all possible filters."""
        from apps.backend.src.models.report_spec import DateRange

        spec = ReportSpecification(
            report_type=ReportType.DATE_RANGE,
            report_title="Complex Report",
            filters=ReportFilters(
                program_ids=["prog1", "prog2"],
                platforms=["h1", "intigriti"],
                vulnerability_types=["XSS", "SQLi", "CSRF"],
                severity_levels=["critical", "high"],
                date_range=DateRange(
                    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
                ),
                exclude_duplicates=True,
                min_payout=100,
                max_payout=5000,
            ),
        )

        assert len(spec.filters.program_ids) == 2
        assert len(spec.filters.platforms) == 2
        assert spec.filters.min_payout == 100
        assert spec.filters.max_payout == 5000

    def test_report_spec_with_custom_sections(self):
        """Test report spec with custom section selection."""
        spec = ReportSpecification(
            report_type=ReportType.PER_PROGRAM,
            report_title="Custom Sections Report",
            sections=["executive_summary", "key_metrics", "recommendations"],
        )

        assert len(spec.sections) == 3
        assert "executive_summary" in spec.sections
        assert "playbook_performance" not in spec.sections
