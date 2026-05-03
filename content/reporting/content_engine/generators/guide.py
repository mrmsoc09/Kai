"""
Generator for Guides, Tutorials, and Playbooks.
"""

from pathlib import Path
from typing import Union, Optional

from content_engine.generators.base import BaseGenerator
from content_engine.models.guide import Guide, Playbook, Tutorial


class GuideGenerator(BaseGenerator):
    """Generator for instructional content."""
    
    def __init__(
        self, 
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ):
        super().__init__(
            template_dir=template_dir,
            output_dir=output_dir,
            template_name="guide/step_by_step.md.j2"
        )
    
    def generate(
        self,
        guide: Guide,
        output_file: Optional[str] = None,
        include_checklists: bool = True
    ) -> Union[str, Path]:
        """
        Generate guide document.
        
        Args:
            guide: Guide model (or subclass)
            output_file: Optional output filename
            include_checklists: Include completion checkboxes
            
        Returns:
            Rendered content or file path
        """
        context = guide.get_template_context()
        context['include_checklists'] = include_checklists
        
        # Select template based on type
        if isinstance(guide, Playbook):
            template_name = "guide/playbook.md.j2"
        elif isinstance(guide, Tutorial):
            template_name = "guide/tutorial.md.j2"
        else:
            template_name = "guide/step_by_step.md.j2"
        
        if output_file:
            return self.render_to_file(guide, output_file, template_name)
        
        return self.render(guide, template_name)
    
    def generate_quick_reference(
        self,
        guide: Guide,
        output_file: Optional[str] = None
    ) -> Union[str, Path]:
        """Generate a quick reference card/cheat sheet."""
        if output_file:
            return self.render_to_file(
                guide, 
                output_file, 
                "guide/quick_reference.md.j2"
            )
        return self.render(guide, "guide/quick_reference.md.j2")
    
    def generate_checklist(self, guide: Guide) -> str:
        """Extract just the checklist from steps."""
        template = self.env.get_template("guide/checklist_only.md.j2")
        return template.render(**guide.get_template_context())
