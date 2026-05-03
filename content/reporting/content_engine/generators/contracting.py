"""
Generator for Government Contracting documents.
"""

from pathlib import Path
from typing import Union, Optional

from content_engine.generators.base import BaseGenerator
from content_engine.models.contracting import ContractingOpportunity


class ContractingGenerator(BaseGenerator):
    """Generator for RFP responses and contracting documents."""
    
    def __init__(
        self, 
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ):
        super().__init__(
            template_dir=template_dir,
            output_dir=output_dir,
            template_name="contracting/rfp_response.md.j2"
        )
    
    def generate(
        self,
        opportunity: ContractingOpportunity,
        output_file: Optional[str] = None,
        sections: Optional[list] = None
    ) -> Union[str, Path]:
        """
        Generate contracting document.
        
        Args:
            opportunity: ContractingOpportunity model
            output_file: Optional output filename
            sections: Specific sections to include
            
        Returns:
            Rendered content or file path
        """
        context = opportunity.get_template_context()
        context['selected_sections'] = sections or []
        
        template_name = self._select_template(opportunity.solicitation_type)
        
        if output_file:
            return self.render_to_file(opportunity, output_file, template_name)
        
        return self.render(opportunity, template_name)
    
    def _select_template(self, sol_type: str) -> str:
        """Select template based on solicitation type."""
        mapping = {
            "RFP": "contracting/rfp_response.md.j2",
            "RFQ": "contracting/rfq_response.md.j2",
            "Sources Sought": "contracting/capabilities_statement.md.j2"
        }
        return mapping.get(str(sol_type), "contracting/rfp_response.md.j2")
    
    def generate_capability_statement(
        self,
        company_info: dict,
        past_performance: list
    ) -> str:
        """Generate a capabilities statement."""
        template = self.env.get_template("contracting/capabilities_statement.md.j2")
        return template.render(
            company=company_info,
            past_performance=past_performance
        )
