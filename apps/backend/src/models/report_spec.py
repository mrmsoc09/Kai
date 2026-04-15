"""Report specification models for flexible PDF report generation.

Allows analysts to specify exactly what they want in a report:
- Report type and scope
- Data filtering constraints
- Content sections
- Target word count
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReportType(str, Enum):
    """Types of reports supported."""

    PER_SCAN = "per_scan"  # Single scan deep dive
    PER_PROGRAM = "per_program"  # Program summary
    PER_PLATFORM = "per_platform"  # Platform (H1/Intigriti) analysis
    DATE_RANGE = "date_range"  # Historical trend analysis
    PLAYBOOK_PERFORMANCE = "playbook_performance"  # Which playbooks work best
    EXECUTIVE_SUMMARY = "executive_summary"  # High-level overview for leadership


class DateRange(BaseModel):
    """Date range specification."""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ReportFilters(BaseModel):
    """Data filtering constraints for reports."""

    program_ids: Optional[List[Union[str, UUID]]] = Field(
        None, description="Specific programs (optional - all if not specified)"
    )
    platforms: Optional[List[str]] = Field(
        None, description="Platforms (h1, intigriti, bugcrowd)"
    )
    vulnerability_types: Optional[List[str]] = Field(
        None, description="Vulnerability types (XSS, SQLi, CSRF, etc.)"
    )
    severity_levels: Optional[List[str]] = Field(
        None, description="Severity levels (critical, high, medium, low)"
    )
    date_range: Optional[DateRange] = Field(
        None, description="Custom date range for report"
    )
    scan_id: Optional[Union[str, UUID]] = Field(None, description="For per_scan reports")
    program_id: Optional[Union[str, UUID]] = Field(None, description="For per_program reports")
    platform: Optional[str] = Field(None, description="For per_platform reports")
    playbook_ids: Optional[List[str]] = Field(
        None, description="For playbook_performance reports"
    )
    exclude_duplicates: bool = Field(
        True, description="Only count unique findings"
    )
    exclude_unpaid: bool = Field(False, description="Include unpaid findings")
    min_payout: Optional[float] = Field(
        None, description="Only findings with payout >= this"
    )
    max_payout: Optional[float] = Field(
        None, description="Only findings with payout <= this"
    )

    @field_validator("program_ids", mode="before")
    @classmethod
    def convert_uuid_list(cls, v):
        """Convert UUID objects to strings."""
        if v is None:
            return None
        return [str(item) if isinstance(item, UUID) else item for item in v]

    @field_validator("scan_id", "program_id", mode="before")
    @classmethod
    def convert_uuid(cls, v):
        """Convert UUID object to string."""
        if v is None:
            return None
        return str(v) if isinstance(v, UUID) else v


class ReportSpecification(BaseModel):
    """
    What the analyst wants in the report.
    Analyst specifies constraints, engine generates intelligent report.
    """

    # Basic report definition
    report_type: ReportType = Field(..., description="Type of report to generate")
    report_title: str = Field(..., description="Custom report title")
    report_description: Optional[str] = Field(
        None, description="Optional report description"
    )

    # Data filtering
    filters: ReportFilters = Field(
        default_factory=ReportFilters, description="Data filtering constraints"
    )

    # Report customization
    include_charts: bool = Field(True, description="Include visualizations")
    include_tables: bool = Field(True, description="Include data tables")
    include_recommendations: bool = Field(True, description="Include actionable insights")

    # Content control
    target_word_count_min: int = Field(5000, description="Minimum word count")
    target_word_count_max: int = Field(10000, description="Maximum word count")

    # Sections to include
    sections: List[str] = Field(
        default=[
            "executive_summary",
            "key_metrics",
            "findings_analysis",
            "playbook_performance",
            "program_analysis",
            "platform_comparison",
            "payout_analysis",
            "trends",
            "recommendations",
        ],
        description="Sections to include in report",
    )

    # Output
    output_format: str = Field("pdf", description="Output format (pdf)")

    # Metadata
    requested_by: Optional[str] = Field(None, description="Analyst ID")
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When report was requested",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "report_type": "per_program",
                "report_title": "Q2 2026 HackerOne Analysis",
                "report_description": "Comprehensive analysis of HackerOne program performance",
                "filters": {
                    "program_ids": ["h1-example-com"],
                    "platforms": ["h1"],
                    "exclude_duplicates": True,
                    "min_payout": 100,
                },
                "include_charts": True,
                "target_word_count_min": 5000,
                "target_word_count_max": 10000,
                "requested_by": "analyst-001",
            }
        }
