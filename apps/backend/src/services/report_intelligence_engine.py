"""Intelligence engine for generating intelligent PDF reports.

Uses Claude API for narrative generation and reportlab/matplotlib
for professional PDF creation with charts and visualizations.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from anthropic import Anthropic

# Optional matplotlib for visualizations
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Optional reportlab for PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
        Image,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    # Dummy implementations for type hints
    colors = None
    letter = None
    inch = None
    SimpleDocTemplate = None
    Paragraph = None
    Spacer = None
    Table = None
    TableStyle = None
    PageBreak = None
    Image = None
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.findings import ScanFinding, FindingSubmission
from ..models.report_spec import ReportSpecification
from ..models.generated_reports import GeneratedReport

logger = logging.getLogger(__name__)


class ReportIntelligenceEngine:
    """Generates intelligent PDF reports using Claude API and professional formatting."""

    def __init__(self, db: AsyncSession, claude_client: Optional[Anthropic] = None):
        self.db = db
        self.claude = claude_client or Anthropic()
        self.logger = logging.getLogger(__name__)

    async def generate_report(self, specification: ReportSpecification) -> bytes:
        """Generate a professional PDF report based on specification.

        Args:
            specification: ReportSpecification with analyst's requirements

        Returns:
            PDF as bytes (can be saved to file or streamed to user)
        """
        self.logger.info(
            f"Generating {specification.report_type} report: {specification.report_title}"
        )

        # STEP 1: Query database for filtered data
        data = await self._query_filtered_data(specification)
        self.logger.debug(f"Queried data: {data['total_findings']} findings")

        # STEP 2: Generate intelligent narratives using Claude
        narratives = await self._generate_narratives(specification, data)
        self.logger.debug(f"Generated {len(narratives)} narrative sections")

        # STEP 3: Create visualizations (charts, tables)
        visualizations = await self._create_visualizations(data)
        self.logger.debug(f"Created {len(visualizations)} visualizations")

        # STEP 4: Build PDF document
        pdf_bytes = await self._build_pdf_document(
            specification, data, narratives, visualizations
        )
        self.logger.info(f"PDF generated: {len(pdf_bytes)} bytes")

        # STEP 5: Store report in database (immutable record)
        await self._store_report_record(specification, pdf_bytes)

        return pdf_bytes

    async def _query_filtered_data(self, spec: ReportSpecification) -> dict[str, Any]:
        """Query database for findings matching analyst's filter specification."""
        from uuid import UUID

        query = select(ScanFinding)

        # Apply filters from specification
        if spec.filters.program_ids:
            # Convert strings to UUIDs if necessary
            program_uuids = [
                UUID(pid) if isinstance(pid, str) else pid
                for pid in spec.filters.program_ids
            ]
            query = query.where(ScanFinding.program_id.in_(program_uuids))

        if spec.filters.platforms:
            query = query.where(
                ScanFinding.submitted_to_platform.in_(spec.filters.platforms)
            )

        if spec.filters.vulnerability_types:
            query = query.where(
                ScanFinding.vulnerability_type.in_(spec.filters.vulnerability_types)
            )

        if spec.filters.severity_levels:
            query = query.where(
                ScanFinding.severity.in_(spec.filters.severity_levels)
            )

        if spec.filters.exclude_duplicates:
            query = query.where(ScanFinding.is_duplicate == False)

        if spec.filters.min_payout:
            query = query.where(ScanFinding.actual_payout >= spec.filters.min_payout)

        if spec.filters.max_payout:
            query = query.where(ScanFinding.actual_payout <= spec.filters.max_payout)

        if spec.filters.date_range and spec.filters.date_range.start_date:
            query = query.where(
                ScanFinding.discovered_at >= spec.filters.date_range.start_date
            )

        if spec.filters.date_range and spec.filters.date_range.end_date:
            query = query.where(
                ScanFinding.discovered_at <= spec.filters.date_range.end_date
            )

        # Execute query
        result = await self.db.scalars(query)
        findings = list(result.all())

        # Aggregate data for report
        data = {
            "findings": findings,
            "total_findings": len(findings),
            "unique_findings": len([f for f in findings if not f.is_duplicate]),
            "total_payout": sum(f.actual_payout or 0 for f in findings),
            "vulnerability_types": self._analyze_vulnerability_types(findings),
            "playbooks": self._analyze_playbooks(findings),
            "platforms": self._analyze_platforms(findings),
            "date_range": self._analyze_date_range(findings),
        }

        return data

    def _analyze_vulnerability_types(
        self, findings: list[ScanFinding]
    ) -> list[tuple[str, int, float]]:
        """Analyze vulnerability types in findings."""
        from decimal import Decimal

        vuln_map: dict[str, tuple[int, Decimal]] = {}

        for finding in findings:
            if finding.vulnerability_type not in vuln_map:
                vuln_map[finding.vulnerability_type] = (0, Decimal("0.00"))
            count, payout = vuln_map[finding.vulnerability_type]
            actual_payout = Decimal(str(finding.actual_payout or 0))
            vuln_map[finding.vulnerability_type] = (
                count + 1,
                payout + actual_payout,
            )

        result = [
            (vtype, count, payout)
            for vtype, (count, payout) in sorted(
                vuln_map.items(), key=lambda x: x[1][1], reverse=True
            )
        ]
        return result

    def _analyze_playbooks(self, findings: list[ScanFinding]) -> list[tuple[str, int]]:
        """Analyze playbook usage in findings."""
        playbook_map: dict[str, int] = {}

        for finding in findings:
            if finding.playbook_name:
                playbook_map[finding.playbook_name] = playbook_map.get(
                    finding.playbook_name, 0
                ) + 1

        result = [
            (name, count)
            for name, count in sorted(
                playbook_map.items(), key=lambda x: x[1], reverse=True
            )
        ]
        return result

    def _analyze_platforms(self, findings: list[ScanFinding]) -> dict[str, int]:
        """Analyze platform distribution."""
        platform_map: dict[str, int] = {}

        for finding in findings:
            if finding.submitted_to_platform:
                platform_map[finding.submitted_to_platform] = platform_map.get(
                    finding.submitted_to_platform, 0
                ) + 1

        return platform_map

    def _analyze_date_range(
        self, findings: list[ScanFinding]
    ) -> dict[str, Optional[datetime]]:
        """Analyze date range of findings."""
        if not findings:
            return {"start": None, "end": None}

        dates = [f.discovered_at for f in findings if f.discovered_at]
        if not dates:
            return {"start": None, "end": None}

        return {"start": min(dates), "end": max(dates)}

    async def _generate_narratives(
        self, spec: ReportSpecification, data: dict[str, Any]
    ) -> dict[str, str]:
        """Use Claude API to generate intelligent narratives for each section."""
        narratives = {}

        # Executive Summary
        if "executive_summary" in spec.sections:
            narratives["executive_summary"] = (
                await self._generate_executive_summary(spec, data)
            )

        # Key Metrics (text summary)
        if "key_metrics" in spec.sections:
            narratives["key_metrics"] = await self._generate_key_metrics(spec, data)

        # Findings Analysis
        if "findings_analysis" in spec.sections:
            narratives["findings_analysis"] = (
                await self._generate_findings_analysis(spec, data)
            )

        # Playbook Performance
        if "playbook_performance" in spec.sections:
            narratives["playbook_performance"] = (
                await self._generate_playbook_analysis(spec, data)
            )

        # Recommendations
        if "recommendations" in spec.sections:
            narratives["recommendations"] = (
                await self._generate_recommendations(spec, data)
            )

        return narratives

    async def _generate_executive_summary(
        self, spec: ReportSpecification, data: dict[str, Any]
    ) -> str:
        """Use Claude to generate executive summary narrative."""
        prompt = f"""Generate a professional executive summary (300-500 words) for a bug bounty scanning report.

Report Type: {spec.report_type.value}
Report Title: {spec.report_title}

Data Summary:
- Total Findings: {data['total_findings']}
- Unique Findings: {data['unique_findings']}
- Total Payout Received: ${data['total_payout']:,.2f}
- Vulnerability Types Found: {', '.join([v[0] for v in data['vulnerability_types'][:5]])}
- Playbooks Used: {', '.join([p[0] for p in data['playbooks'][:5]])}

Write a compelling executive summary that:
1. Highlights key achievements and metrics
2. Summarizes scanning effectiveness
3. Notes most impactful findings
4. Provides high-level ROI assessment
5. Sets context for detailed analysis below

Use professional business language suitable for stakeholder review."""

        try:
            response = await self.claude.messages.create(
                model="claude-opus-4-20250805",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            return "Executive summary generation failed. Please try again."

    async def _generate_findings_analysis(
        self, spec: ReportSpecification, data: dict[str, Any]
    ) -> str:
        """Analyze vulnerability findings discovered."""
        vuln_summary = "\n".join(
            [f"- {vtype}: {count} findings (${payout:,.2f})"
             for vtype, count, payout in data["vulnerability_types"][:10]]
        )

        prompt = f"""Generate a detailed findings analysis section (1000-1500 words) for a bug bounty report.

Vulnerability Breakdown:
{vuln_summary}

Write an analysis that:
1. Discusses vulnerability patterns discovered
2. Highlights the most severe/impactful findings
3. Explains the significance of top vulnerabilities
4. Relates findings to overall security posture
5. Notes any unusual patterns or trends

Use technical language but remain accessible to non-security stakeholders."""

        try:
            response = await self.claude.messages.create(
                model="claude-opus-4-20250805",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            return "Findings analysis generation failed. Please try again."

    async def _generate_playbook_analysis(
        self, spec: ReportSpecification, data: dict[str, Any]
    ) -> str:
        """Analyze playbook effectiveness."""
        playbook_summary = "\n".join(
            [f"- {name}: {count} findings" for name, count in data["playbooks"][:10]]
        )

        prompt = f"""Generate an analysis of playbook effectiveness (600-1000 words).

Playbook Results:
{playbook_summary}

Discuss:
1. Which playbooks were most effective
2. Which found the most valuable findings
3. Recommendations for playbook selection
4. Patterns in playbook success"""

        try:
            response = await self.claude.messages.create(
                model="claude-opus-4-20250805",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            return "Playbook analysis generation failed. Please try again."

    async def _generate_key_metrics(
        self, spec: ReportSpecification, data: dict[str, Any]
    ) -> str:
        """Generate key metrics narrative."""
        return f"""Key Performance Indicators:

Findings Discovered: {data['total_findings']} total, {data['unique_findings']} unique
Total Revenue: ${data['total_payout']:,.2f}
Average Finding Value: ${data['total_payout'] / max(data['total_findings'], 1):,.2f}
Vulnerability Distribution: {len(data['vulnerability_types'])} types identified
Top Vulnerability: {data['vulnerability_types'][0][0] if data['vulnerability_types'] else 'N/A'}"""

    async def _generate_recommendations(
        self, spec: ReportSpecification, data: dict[str, Any]
    ) -> str:
        """Generate actionable recommendations."""
        prompt = f"""Generate actionable recommendations (800-1200 words) for improving bug bounty ROI.

Findings Summary:
- Total Vulnerabilities: {data['total_findings']}
- Top Vulnerability Type: {data['vulnerability_types'][0][0] if data['vulnerability_types'] else 'N/A'}
- Total Revenue: ${data['total_payout']:,.2f}
- Most Effective Playbooks: {', '.join([p[0] for p in data['playbooks'][:3]])}

Provide recommendations that:
1. Address the most impactful vulnerabilities
2. Suggest improvements to scanning strategy
3. Recommend which playbooks to prioritize
4. Propose next steps for security improvement
5. Suggest ways to increase bug bounty ROI

Make recommendations specific, measurable, and actionable."""

        try:
            response = await self.claude.messages.create(
                model="claude-opus-4-20250805",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            return "Recommendations generation failed. Please try again."

    async def _create_visualizations(
        self, data: dict[str, Any]
    ) -> dict[str, io.BytesIO]:
        """Create charts and visualizations for the report."""
        visualizations = {}

        # Skip visualizations if matplotlib is not available
        if not MATPLOTLIB_AVAILABLE:
            self.logger.info("Matplotlib not available, skipping visualizations")
            return visualizations

        # Chart 1: Vulnerability Type Distribution (pie chart)
        if data["vulnerability_types"]:
            try:
                fig, ax = plt.subplots(figsize=(8, 6))
                types = [v[0] for v in data["vulnerability_types"][:8]]
                counts = [v[1] for v in data["vulnerability_types"][:8]]
                ax.pie(counts, labels=types, autopct="%1.1f%%", startangle=90)
                ax.set_title("Vulnerability Type Distribution")

                img_buffer = io.BytesIO()
                fig.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
                img_buffer.seek(0)
                visualizations["vulnerability_distribution"] = img_buffer
                plt.close(fig)
            except Exception as e:
                self.logger.warning(f"Visualization error: {e}")

        return visualizations

    async def _build_pdf_document(
        self,
        spec: ReportSpecification,
        data: dict[str, Any],
        narratives: dict[str, str],
        visualizations: dict[str, io.BytesIO],
    ) -> bytes:
        """Build professional PDF document with all content."""
        if not REPORTLAB_AVAILABLE:
            # Return a simple text-based PDF-like document
            self.logger.warning("reportlab not available, returning text report")
            content = f"""
{spec.report_title}
{'=' * len(spec.report_title)}

{spec.report_description or ''}

Generated: {datetime.now(timezone.utc).isoformat()}

EXECUTIVE SUMMARY
{narratives.get('executive_summary', 'No summary available')}

KEY METRICS
{narratives.get('key_metrics', 'No metrics available')}

RECOMMENDATIONS
{narratives.get('recommendations', 'No recommendations available')}
"""
            return content.encode('utf-8')

        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build story (content)
        story = []

        # Title page
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=getSampleStyleSheet()["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1f77b4"),
            spaceAfter=12,
            alignment=1,  # Center
        )

        story.append(Paragraph(spec.report_title, title_style))
        story.append(Spacer(1, 0.3 * inch))

        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=12,
            textColor=colors.grey,
            spaceAfter=6,
            alignment=1,
        )

        story.append(Paragraph(spec.report_description or "", subtitle_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(
            Paragraph(
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                subtitle_style,
            )
        )
        story.append(PageBreak())

        # Sections
        heading_style = ParagraphStyle(
            "SectionHeading",
            parent=getSampleStyleSheet()["Heading2"],
            fontSize=16,
            textColor=colors.HexColor("#1f77b4"),
            spaceAfter=12,
            spaceBefore=12,
        )

        body_style = getSampleStyleSheet()["BodyText"]

        # Executive Summary
        if "executive_summary" in narratives:
            story.append(Paragraph("Executive Summary", heading_style))
            story.append(Paragraph(narratives["executive_summary"], body_style))
            story.append(Spacer(1, 0.2 * inch))

        # Key Metrics (table)
        if "key_metrics" in narratives:
            story.append(Paragraph("Key Metrics", heading_style))
            story.append(Paragraph(narratives["key_metrics"], body_style))
            story.append(Spacer(1, 0.2 * inch))

        # Visualizations
        if "vulnerability_distribution" in visualizations:
            story.append(Paragraph("Vulnerability Distribution", heading_style))
            img = Image(
                visualizations["vulnerability_distribution"],
                width=4.5 * inch,
                height=3 * inch,
            )
            story.append(img)
            story.append(Spacer(1, 0.2 * inch))

        # Findings Analysis
        if "findings_analysis" in narratives:
            story.append(Paragraph("Detailed Findings Analysis", heading_style))
            story.append(Paragraph(narratives["findings_analysis"], body_style))
            story.append(Spacer(1, 0.2 * inch))

        # Playbook Performance
        if "playbook_performance" in narratives:
            story.append(Paragraph("Playbook Performance", heading_style))
            story.append(Paragraph(narratives["playbook_performance"], body_style))
            story.append(Spacer(1, 0.2 * inch))

        # Recommendations
        if "recommendations" in narratives:
            story.append(PageBreak())
            story.append(
                Paragraph("Recommendations & Next Steps", heading_style)
            )
            story.append(Paragraph(narratives["recommendations"], body_style))

        # Build PDF
        doc.build(story)
        pdf_bytes = pdf_buffer.getvalue()

        return pdf_bytes

    async def _store_report_record(
        self, spec: ReportSpecification, pdf_bytes: bytes
    ) -> None:
        """Store generated report in database (immutable record)."""
        from uuid import uuid4

        # Estimate word count (rough approximation)
        word_count = len(pdf_bytes) // 4

        report_record = GeneratedReport(
            id=uuid4(),
            report_type=spec.report_type.value,
            report_title=spec.report_title,
            report_description=spec.report_description,
            filters=spec.filters.dict(),
            pdf_content=pdf_bytes,
            word_count=word_count,
            page_count=len(pdf_bytes) // 5000,  # Rough estimate
            file_size_bytes=len(pdf_bytes),
            generated_by=spec.requested_by or "unknown",
        )

        self.db.add(report_record)
        await self.db.commit()

        self.logger.info(f"Report stored: {spec.report_title} ({report_record.id})")
