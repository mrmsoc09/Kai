"""PDF report generation from markdown and HTML content."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import markdown
from weasyprint import HTML, CSS
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

# CSS for professional PDF styling
PDF_STYLESHEET = """
:root {
    --color-primary: #1a73e8;
    --color-secondary: #34a853;
    --color-danger: #d33b27;
    --color-warning: #fbbc04;
    --color-text: #202124;
    --color-light-bg: #f8f9fa;
}

@page {
    size: A4;
    margin: 2cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 10pt;
        color: #999;
    }
}

body {
    font-family: "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: var(--color-text);
    text-align: justify;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--color-primary);
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    font-weight: 600;
    page-break-after: avoid;
}

h1 {
    font-size: 24pt;
    border-bottom: 3px solid var(--color-primary);
    padding-bottom: 0.3em;
}

h2 {
    font-size: 18pt;
    border-bottom: 2px solid var(--color-primary);
    padding-bottom: 0.2em;
}

h3 {
    font-size: 14pt;
}

h4, h5, h6 {
    font-size: 12pt;
}

p {
    margin-bottom: 0.8em;
}

strong {
    color: var(--color-primary);
    font-weight: 600;
}

em {
    font-style: italic;
}

a {
    color: var(--color-primary);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

code {
    background-color: var(--color-light-bg);
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 2px 4px;
    font-family: "Courier New", Courier, monospace;
    font-size: 10pt;
}

pre {
    background-color: var(--color-light-bg);
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    padding: 1em;
    overflow-x: auto;
    margin: 1em 0;
    page-break-inside: avoid;
}

pre code {
    background-color: transparent;
    border: none;
    padding: 0;
}

blockquote {
    border-left: 4px solid var(--color-primary);
    padding-left: 1em;
    margin-left: 0;
    color: #666;
}

ul, ol {
    margin-bottom: 1em;
    padding-left: 2em;
}

li {
    margin-bottom: 0.3em;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    page-break-inside: avoid;
}

th {
    background-color: var(--color-primary);
    color: white;
    padding: 0.5em;
    text-align: left;
    font-weight: 600;
}

td {
    border: 1px solid #ddd;
    padding: 0.5em;
}

tr:nth-child(even) {
    background-color: var(--color-light-bg);
}

.severity-critical {
    color: var(--color-danger);
    font-weight: 600;
}

.severity-high {
    color: var(--color-warning);
    font-weight: 600;
}

.severity-medium {
    color: var(--color-primary);
    font-weight: 600;
}

.severity-low {
    color: var(--color-secondary);
    font-weight: 600;
}

.metadata {
    background-color: var(--color-light-bg);
    border: 1px solid #ddd;
    border-radius: 3px;
    padding: 1em;
    margin: 1em 0;
    font-size: 10pt;
}

.report-header {
    text-align: center;
    border-bottom: 2px solid var(--color-primary);
    padding-bottom: 1em;
    margin-bottom: 2em;
    page-break-after: avoid;
}

.report-footer {
    text-align: center;
    font-size: 9pt;
    color: #999;
    margin-top: 3em;
    border-top: 1px solid #ddd;
    padding-top: 1em;
}

.page-break {
    page-break-after: always;
}

.avoid-break {
    page-break-inside: avoid;
}

img {
    max-width: 100%;
    height: auto;
    margin: 1em 0;
}

.evidence-image {
    border: 1px solid #ddd;
    border-radius: 3px;
    padding: 0.5em;
    margin: 0.5em 0;
}
"""

# Parse CSS once; reusing it materially speeds up repeated PDF generation.
_PDF_CSS = CSS(string=PDF_STYLESHEET)


def markdown_to_html(markdown_content: str, stakeholder: str = "default") -> str:
    """
    Convert markdown content to HTML with proper styling.

    Args:
        markdown_content: Markdown-formatted content
        stakeholder: Stakeholder identifier for custom styling

    Returns:
        HTML string with embedded styles
    """
    try:
        # Convert markdown to HTML
        html_body = markdown.markdown(
            markdown_content,
            extensions=['tables', 'fenced_code', 'toc']
        )

        # Add report header and footer
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Vulnerability Report</title>
            <style>
            {PDF_STYLESHEET}
            </style>
        </head>
        <body>
            <div class="report-header">
                <h1>Vulnerability Report</h1>
                <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p>Stakeholder: {stakeholder}</p>
            </div>

            <div class="report-content">
            {html_body}
            </div>

            <div class="report-footer">
                <p>This report is confidential and intended for authorized use only.</p>
                <p>Generated by K1 - Autonomous Vulnerability Hunting Platform</p>
            </div>
        </body>
        </html>
        """

        return html

    except Exception as e:
        logger.error(f"Markdown to HTML conversion failed: {str(e)}")
        raise


def generate_pdf(
    html_content: str,
    output_path: Optional[Path] = None,
    stakeholder: str = "default"
) -> bytes:
    """
    Generate PDF from HTML content.

    Args:
        html_content: HTML content (can be raw HTML or markdown converted to HTML)
        output_path: Optional path to save PDF file
        stakeholder: Stakeholder identifier for custom headers/footers

    Returns:
        PDF content as bytes
    """
    try:
        # If output_path not provided, use BytesIO for in-memory generation
        if output_path is None:
            output_buffer = BytesIO()
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_buffer = output_path

        # Generate PDF from HTML
        HTML(string=html_content).write_pdf(
            output_buffer,
            stylesheets=[_PDF_CSS]
        )

        # Return bytes if in-memory
        if isinstance(output_buffer, BytesIO):
            return output_buffer.getvalue()
        else:
            with open(output_buffer, 'rb') as f:
                return f.read()

    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise


def generate_pdf_from_markdown(
    markdown_content: str,
    output_path: Optional[Path] = None,
    stakeholder: str = "default"
) -> bytes:
    """
    Generate PDF directly from markdown content.

    Args:
        markdown_content: Markdown-formatted content
        output_path: Optional path to save PDF file
        stakeholder: Stakeholder identifier

    Returns:
        PDF content as bytes
    """
    try:
        # Convert markdown to HTML
        html_content = markdown_to_html(markdown_content, stakeholder)

        # Generate PDF from HTML
        return generate_pdf(html_content, output_path, stakeholder)

    except Exception as e:
        logger.error(f"Markdown to PDF conversion failed: {str(e)}")
        raise


def add_watermark(pdf_bytes: bytes, watermark_text: str) -> bytes:
    """
    Add watermark to PDF (placeholder - watermarking requires more complex PDF manipulation).

    This is a placeholder for future enhancement using PyPDF2 or similar.

    Args:
        pdf_bytes: PDF content as bytes
        watermark_text: Text to add as watermark

    Returns:
        Modified PDF bytes
    """
    # Placeholder: In production, would use PyPDF2 or similar to add watermark
    logger.warning(f"Watermarking not yet implemented. Requested: {watermark_text}")
    return pdf_bytes


def get_pdf_metadata(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extract metadata from PDF bytes (placeholder).

    Args:
        pdf_bytes: PDF content as bytes

    Returns:
        Dictionary with PDF metadata
    """
    try:
        # Placeholder: In production, would use PyPDF2 to extract metadata
        return {
            'size_bytes': len(pdf_bytes),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'pages_estimated': max(1, len(pdf_bytes) // 5000),  # Rough estimate
        }
    except Exception as e:
        logger.error(f"Failed to extract PDF metadata: {str(e)}")
        return {'error': str(e)}
