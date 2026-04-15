"""ORM models for findings, scans, and submissions tracking.

This module provides SQLAlchemy models for storing and tracking:
- Findings: Vulnerabilities discovered during scans
- Scans: Scan execution metadata and results
- Submissions: Submissions to bug bounty platforms
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID as PGUUID
from sqlalchemy.orm import relationship

from .base import Base


class ScanExecution(Base):
    """Track metadata about scan executions.

    Links to Program and contains multiple Findings.
    """

    __tablename__ = "scans"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    program_id = Column(PGUUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)

    scan_name = Column(Text, nullable=True)
    scan_type = Column(String(50), nullable=True)  # "quick", "comprehensive", "targeted"
    workflow_template_used = Column(Text, nullable=True)

    requested_by = Column(Text, nullable=True)
    triggered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    available_scanning_modes = Column(JSON, nullable=True)  # ["unauthenticated", "api_key"]
    playbooks_executed = Column(JSON, nullable=True)  # List of playbook IDs
    playbooks_skipped = Column(JSON, nullable=True)  # List of skipped playbooks
    credentials_used = Column(JSON, nullable=True)  # {"user_account": "active", ...}

    total_findings_discovered = Column(Integer, default=0, server_default="0")
    total_findings_submitted = Column(Integer, default=0, server_default="0")
    total_findings_accepted = Column(Integer, default=0, server_default="0")
    total_findings_rejected = Column(Integer, default=0, server_default="0")
    total_payout_received = Column(Numeric(10, 2), default=0, server_default="0")

    status = Column(String(50), nullable=False)  # pending, running, completed, failed, cancelled
    completion_status = Column(String(50), nullable=True)  # success, partial_failure, failure
    error_message = Column(Text, nullable=True)

    total_endpoints_tested = Column(Integer, nullable=True)
    total_requests_made = Column(Integer, nullable=True)
    rate_limit_hits = Column(Integer, nullable=True)

    # Kill switch columns (for emergency abort)
    abort_requested = Column(Boolean, default=False, server_default="false", nullable=False)
    abort_requested_by = Column(Text, nullable=True)
    abort_requested_at = Column(DateTime(timezone=True), nullable=True)
    abort_reason = Column(Text, nullable=True)

    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    last_updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    program = relationship("Program", back_populates="scans")
    findings = relationship("ScanFinding", back_populates="scan", cascade="all, delete-orphan")

    def calculate_duration(self) -> int | None:
        """Calculate scan duration in seconds."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())
            return self.duration_seconds
        return None


class ScanFinding(Base):
    """Store vulnerability findings discovered during scans.

    Links to ScanExecution and Program, can have multiple FindingSubmissions.
    """

    __tablename__ = "scan_findings"
    __table_args__ = (
        UniqueConstraint("finding_identifier", name="uq_findings_identifier"),
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    finding_identifier = Column(Text, unique=True, nullable=False)

    program_id = Column(PGUUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    scan_id = Column(PGUUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)

    # Vulnerability basics
    vulnerability_type = Column(Text, nullable=False)  # XSS, SQLi, CSRF, etc.
    severity = Column(String(50), nullable=True)  # critical, high, medium, low
    cvss_score = Column(Numeric(3, 1), nullable=True)  # 0.0-10.0

    # Location and technical details
    endpoint = Column(Text, nullable=True)  # /api/users?id={id}
    parameter_name = Column(Text, nullable=True)  # id
    http_method = Column(String(10), nullable=True)  # GET, POST, etc.
    payload_used = Column(Text, nullable=True)

    # Description and remediation
    description = Column(Text, nullable=False)
    proof_of_concept = Column(Text, nullable=True)
    impact_description = Column(Text, nullable=True)
    remediation_guidance = Column(Text, nullable=True)

    # Evidence
    screenshot_url = Column(Text, nullable=True)
    video_recording_url = Column(Text, nullable=True)
    logs_or_evidence = Column(JSON, nullable=True)  # Request/response logs, etc.

    # Estimation vs reality
    estimated_severity = Column(String(50), nullable=True)
    estimated_payout = Column(Numeric(10, 2), nullable=True)
    actual_severity = Column(String(50), nullable=True)
    actual_payout = Column(Numeric(10, 2), nullable=True)
    payout_currency = Column(String(10), default="USD", server_default="USD")
    payout_accuracy_percentage = Column(Numeric(5, 2), nullable=True)

    # Finding status
    status = Column(String(50), default="discovered", server_default="discovered")
    # discovered, deduped, submitted, accepted, rejected, paid
    finding_state = Column(String(50), nullable=True)  # valid, false_positive, duplicate, out_of_scope
    validation_status = Column(
        String(50),
        nullable=False,
        default="pending_analyst_review",
        server_default="pending_analyst_review",
    )
    # pending_analyst_review, approved_for_submission, excluded

    # Scanning context
    scanning_modes_used = Column(JSON, nullable=True)  # ["unauthenticated", "api_key"]
    playbook_id = Column(Text, nullable=True)
    playbook_name = Column(Text, nullable=True)
    ai_confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00-1.00

    # Submission tracking
    submitted_to_platform = Column(String(50), nullable=True)  # h1, intigriti, bugcrowd
    submission_id = Column(Text, nullable=True)
    submission_status = Column(String(50), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    platform_response_date = Column(DateTime(timezone=True), nullable=True)
    platform_decision_notes = Column(Text, nullable=True)

    # Deduplication
    is_duplicate = Column(Boolean, default=False, server_default="false")
    duplicate_of_finding_id = Column(PGUUID(as_uuid=True), ForeignKey("scan_findings.id", ondelete="SET NULL"), nullable=True)
    deduplication_reason = Column(Text, nullable=True)
    deduplication_confidence = Column(Numeric(3, 2), nullable=True)

    # Timing
    discovered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payout_received_at = Column(DateTime(timezone=True), nullable=True)

    # Audit
    created_by = Column(Text, nullable=True)
    last_updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_by = Column(Text, nullable=True)
    analyst_notes = Column(Text, nullable=True)

    # Relationships
    program = relationship("Program", back_populates="findings")
    scan = relationship("ScanExecution", back_populates="findings")
    submissions = relationship("FindingSubmission", back_populates="finding", cascade="all, delete-orphan")

    def mark_as_duplicate(self, original_finding_id: UUID, reason: str, confidence: Decimal | float) -> None:
        """Mark this finding as a duplicate of another."""
        self.is_duplicate = True
        self.duplicate_of_finding_id = original_finding_id
        self.deduplication_reason = reason
        self.deduplication_confidence = Decimal(str(confidence))
        self.status = "deduped"

    def calculate_payout_accuracy(self) -> Decimal | None:
        """Calculate how accurate our payout estimate was."""
        if not self.estimated_payout or self.estimated_payout == 0:
            return None
        actual = Decimal(str(self.actual_payout or 0))
        estimated = Decimal(str(self.estimated_payout))
        accuracy = (actual / estimated) * 100
        self.payout_accuracy_percentage = accuracy
        return accuracy

    def mark_as_paid(self, amount: Decimal | float, currency: str = "USD") -> None:
        """Mark finding as paid with amount."""
        self.actual_payout = Decimal(str(amount))
        self.payout_currency = currency
        self.payout_received_at = datetime.now(timezone.utc)
        self.status = "paid"
        self.calculate_payout_accuracy()


class FindingSubmission(Base):
    """Track submissions to bug bounty platforms.

    Links to Finding, tracks submission lifecycle and payouts.
    """

    __tablename__ = "submissions"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    finding_id = Column(PGUUID(as_uuid=True), ForeignKey("scan_findings.id", ondelete="CASCADE"), nullable=False)

    # Platform details
    submitted_to_platform = Column(String(50), nullable=False)  # h1, intigriti, bugcrowd, direct
    platform_submission_id = Column(Text, nullable=True)
    submission_url = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Status tracking
    current_status = Column(String(50), nullable=False)  # pending, accepted, rejected, duplicate, out_of_scope, paid
    status_history = Column(JSON, nullable=True)  # Array of {status, timestamp, notes}

    # Platform decision
    platform_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Payout
    payout_amount = Column(Numeric(10, 2), nullable=True)
    payout_currency = Column(String(10), default="USD", server_default="USD")
    payout_received_at = Column(DateTime(timezone=True), nullable=True)

    # Report quality
    report_quality_score = Column(Numeric(3, 2), nullable=True)  # 1.0-5.0
    report_feedback = Column(Text, nullable=True)

    # Audit
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    last_updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    finding = relationship("ScanFinding", back_populates="submissions")

    def add_status_change(self, new_status: str, notes: str = "") -> None:
        """Record a status change in history."""
        if self.status_history is None:
            self.status_history = []
        else:
            self.status_history = list(self.status_history)

        change = {
            "status": new_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        }
        self.status_history.append(change)
        self.current_status = new_status

    def mark_as_paid(self, amount: Decimal | float, currency: str = "USD") -> None:
        """Mark submission as paid."""
        self.payout_amount = Decimal(str(amount))
        self.payout_currency = currency
        self.payout_received_at = datetime.now(timezone.utc)
        self.add_status_change("paid", "Payment received")
