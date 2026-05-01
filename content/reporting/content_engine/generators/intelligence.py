"""
Generator for Intelligence Reports.
"""

from pathlib import Path
from typing import Union, Optional

from content_engine.generators.base import BaseGenerator
from content_engine.models.intelligence import IntelligenceReport


class IntelligenceReportGenerator(BaseGenerator):
    """Generator for classified intelligence reports."""
    
    def __init__(
        self, 
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ):
        super().__init__(
            template_dir=template_dir,
            output_dir=output_dir,
            template_name="intelligence/standard_report.md.j2"
        )
    
    def generate(
        self, 
        report: IntelligenceReport, 
        output_file: Optional[str] = None,
        include_annexes: bool = True,
        format: str = "markdown"
    ) -> Union[str, Path]:
        """
        Generate an intelligence report.
        
        Args:
            report: IntelligenceReport model
            output_file: Optional filename to save to
            include_annexes: Whether to include annexes
            format: Output format (markdown, html)
            
        Returns:
            Rendered content or file path
        """
        # Pre-process data
        context = report.get_template_context()
        context['include_annexes'] = include_annexes
        
        # Select template based on classification
        template_name = self._select_template(report.metadata.classification)
        
        if output_file:
            return self.render_to_file(report, output_file, template_name)
        
        return self.render(report, template_name)
    
    def _select_template(self, classification: str) -> str:
        """Select appropriate template based on classification."""
        # Could have different templates for different classification levels
        return "intelligence/classified_report.md.j2"
    
    def generate_executive_summary(
        self, 
        report: IntelligenceReport
    ) -> str:
        """Generate just the executive summary."""
        template = self.env.get_template("intelligence/executive_summary.md.j2")
        return template.render(**report.get_template_context())
