"""Multi-format export system for vulnerability reports (markdown, HTML, PDF, JSON)."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, Literal, Union
from datetime import datetime
import json
import logging
from .report_formats import render_report, get_format
from .pdf_generator import markdown_to_html, generate_pdf_from_markdown

logger = logging.getLogger(__name__)

FormatType = Literal["markdown", "html", "pdf", "json"]


class ReportExporter:
    """Export vulnerability reports in multiple formats."""

    SUPPORTED_FORMATS = ["markdown", "html", "pdf", "json"]

    def __init__(self, format_id: str = "google_vrp", stakeholder: str = "google_vrp"):
        """
        Initialize report exporter.

        Args:
            format_id: Report format ID (e.g., 'google_vrp', 'hackerone')
            stakeholder: Stakeholder name
        """
        self.format_id = format_id
        self.stakeholder = stakeholder
        try:
            self.format_config = get_format(format_id)
        except FileNotFoundError:
            logger.warning(f"Format {format_id} not found, using default")
            self.format_config = {}

        self.export_history = []

    def export(
        self,
        finding: Dict[str, Any],
        evidence: Dict[str, Any],
        mitigation: Dict[str, Any],
        format_type: FormatType = "markdown",
        output_path: Optional[Path] = None,
        report_id: Optional[str] = None
    ) -> Union[str, bytes]:
        """
        Export report in specified format.

        Args:
            finding: Finding data
            evidence: Evidence data
            mitigation: Mitigation data
            format_type: Output format (markdown, html, pdf, json)
            output_path: Optional path to save file
            report_id: Optional report ID

        Returns:
            Report content. `bytes` for PDF, `str` for markdown/html/json.
        """
        try:
            if format_type not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {format_type}")

            report_id = report_id or f"REPORT_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

            if format_type == "markdown":
                content = self._export_markdown(finding, evidence, mitigation, report_id)
            elif format_type == "html":
                content = self._export_html(finding, evidence, mitigation, report_id)
            elif format_type == "pdf":
                content = self._export_pdf(finding, evidence, mitigation, report_id)
            elif format_type == "json":
                content = self._export_json(finding, evidence, mitigation, report_id)
            else:
                raise ValueError(f"Unsupported format: {format_type}")

            # Save to file if path provided
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    output_path.write_bytes(content)
                else:
                    output_path.write_text(content, encoding='utf-8')
                logger.info(f"Report exported to {output_path}")

            # Track export
            self.export_history.append({
                'format': format_type,
                'timestamp': datetime.utcnow().isoformat(),
                'report_id': report_id,
                'path': str(output_path) if output_path else None,
                'size': len(content) if isinstance(content, bytes) else len(content.encode())
            })

            return content

        except Exception as e:
            logger.error(f"Export to {format_type} failed: {str(e)}")
            raise

    def export_all(
        self,
        finding: Dict[str, Any],
        evidence: Dict[str, Any],
        mitigation: Dict[str, Any],
        output_dir: Optional[Path] = None,
        report_id: Optional[str] = None
    ) -> Dict[str, Optional[Union[str, bytes]]]:
        """
        Export report in all supported formats.

        Args:
            finding: Finding data
            evidence: Evidence data
            mitigation: Mitigation data
            output_dir: Optional directory to save files
            report_id: Optional report ID

        Returns:
            Dictionary mapping format types to report content.
        """
        report_id = report_id or f"REPORT_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        exports = {}

        for fmt in self.SUPPORTED_FORMATS:
            try:
                output_path = None
                if output_dir:
                    ext = fmt if fmt != "json" else "json"
                    if fmt == "pdf":
                        ext = "pdf"
                    elif fmt == "html":
                        ext = "html"
                    elif fmt == "json":
                        ext = "json"
                    else:
                        ext = "md"

                    output_path = output_dir / f"{report_id}.{ext}"

                exports[fmt] = self.export(finding, evidence, mitigation, fmt, output_path, report_id)
                logger.info(f"Exported {fmt} format successfully")

            except Exception as e:
                logger.error(f"Failed to export {fmt} format: {str(e)}")
                exports[fmt] = None

        return exports

    def _export_markdown(
        self,
        finding: Dict[str, Any],
        evidence: Dict[str, Any],
        mitigation: Dict[str, Any],
        report_id: str
    ) -> str:
        """Export report as markdown."""
        markdown_content = render_report(
            self.format_config,
            finding,
            evidence,
            mitigation,
            report_id
        )
        return markdown_content

    def _export_html(
        self,
        finding: Dict[str, Any],
        evidence: Dict[str, Any],
        mitigation: Dict[str, Any],
        report_id: str
    ) -> str:
        """Export report as HTML."""
        # First render as markdown
        markdown_content = self._export_markdown(finding, evidence, mitigation, report_id)

        # Convert markdown to HTML
        html_content = markdown_to_html(markdown_content, self.stakeholder)
        return html_content

    def _export_pdf(
        self,
        finding: Dict[str, Any],
        evidence: Dict[str, Any],
        mitigation: Dict[str, Any],
        report_id: str
    ) -> bytes:
        """Export report as PDF."""
        # First render as markdown
        markdown_content = self._export_markdown(finding, evidence, mitigation, report_id)

        # Convert markdown to PDF
        pdf_bytes = generate_pdf_from_markdown(markdown_content, None, self.stakeholder)
        return pdf_bytes

    def _export_json(
        self,
        finding: Dict[str, Any],
        evidence: Dict[str, Any],
        mitigation: Dict[str, Any],
        report_id: str
    ) -> str:
        """Export report as JSON with structured data."""
        # Create structured JSON representation
        json_report = {
            "report_id": report_id,
            "format": self.format_id,
            "stakeholder": self.stakeholder,
            "generated_at": datetime.utcnow().isoformat(),
            "finding": {
                "id": finding.get('id', 'N/A'),
                "title": finding.get('title', 'N/A'),
                "description": finding.get('summary', ''),
                "vulnerability_type": finding.get('vulnerability_type', 'N/A'),
                "severity": finding.get('severity', 'N/A'),
                "cvss_score": finding.get('cvss', 'N/A'),
                "cwe": finding.get('cwe', 'N/A'),
                "cve": finding.get('cve_id'),
                "impact": finding.get('impact', ''),
                "affected_scope": finding.get('scope', ''),
                "references": finding.get('references', []),
            },
            "evidence": {
                "reproduction": evidence.get('repro', ''),
                "artifacts": evidence.get('artifacts', {}),
                "screenshots": evidence.get('screenshots', []),
                "network_captures": evidence.get('network_captures', []),
                "proof_of_concept": evidence.get('poc_code'),
            },
            "mitigation": {
                "plan": mitigation.get('plan', ''),
                "timeline": mitigation.get('timeline', ''),
                "effort_hours": mitigation.get('effort_hours'),
                "priority": mitigation.get('priority', 'normal'),
            },
            "metadata": {
                "format_sections": self.format_config.get('required_sections', []),
                "export_formats": self.SUPPORTED_FORMATS,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        return json.dumps(json_report, indent=2)

    def get_export_stats(self) -> Dict[str, Any]:
        """Get statistics about exports performed."""
        return {
            'total_exports': len(self.export_history),
            'by_format': self._count_by_format(),
            'latest_export': self.export_history[-1] if self.export_history else None,
            'average_size_kb': self._calculate_average_size(),
        }

    def _count_by_format(self) -> Dict[str, int]:
        """Count exports by format."""
        counts = {fmt: 0 for fmt in self.SUPPORTED_FORMATS}
        for export in self.export_history:
            fmt = export.get('format')
            if fmt in counts:
                counts[fmt] += 1
        return counts

    def _calculate_average_size(self) -> float:
        """Calculate average export size in KB."""
        if not self.export_history:
            return 0.0
        total_size = sum(e['size'] for e in self.export_history)
        return round((total_size / len(self.export_history)) / 1024, 2)


def create_exporter(format_id: str = "google_vrp", stakeholder: str = None) -> ReportExporter:
    """
    Factory function to create report exporter.

    Args:
        format_id: Report format ID
        stakeholder: Stakeholder name (defaults to format_id if not provided)

    Returns:
        ReportExporter instance
    """
    if stakeholder is None:
        # Try to get stakeholder from format config
        try:
            fmt_config = get_format(format_id)
            stakeholder = fmt_config.get('stakeholder', format_id)
        except Exception:
            stakeholder = format_id

    return ReportExporter(format_id, stakeholder)
