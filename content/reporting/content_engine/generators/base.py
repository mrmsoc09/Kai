"""
Base generator class with common functionality.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound


class BaseGenerator(ABC):
    """Abstract base class for all content generators."""
    
    def __init__(
        self, 
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        template_name: Optional[str] = None
    ):
        """
        Initialize the generator.
        
        Args:
            template_dir: Directory containing Jinja2 templates
            output_dir: Directory for output files
            template_name: Default template to use
        """
        self.template_dir = template_dir or Path(__file__).parent.parent / "templates"
        self.output_dir = output_dir or Path("./output")
        self.template_name = template_name
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['format_date'] = self._filter_format_date
        self.env.filters['uppercase'] = lambda x: str(x).upper()
        self.env.filters['classification_banner'] = self._filter_classification_banner
    
    def _filter_format_date(self, value, format_str="%Y-%m-%d"):
        """Date formatting filter."""
        if value is None:
            return ""
        if hasattr(value, 'strftime'):
            return value.strftime(format_str)
        return str(value)
    
    def _filter_classification_banner(self, classification: str) -> str:
        """Generate classification banner."""
        return f"{'=' * 20} {classification.upper()} {'=' * 20}"
    
    def get_template(self, template_name: Optional[str] = None) -> Any:
        """
        Load a Jinja2 template.
        
        Args:
            template_name: Name of the template file
            
        Returns:
            Jinja2 Template object
            
        Raises:
            TemplateNotFound: If template doesn't exist
        """
        name = template_name or self.template_name
        if not name:
            raise ValueError("No template name specified")
        
        try:
            return self.env.get_template(name)
        except TemplateNotFound:
            # Try with default extension
            return self.env.get_template(f"{name}.md.j2")
    
    def render(self, data: Any, template_name: Optional[str] = None) -> str:
        """
        Render content using template.
        
        Args:
            data: Data model or dictionary to render
            template_name: Specific template to use
            
        Returns:
            Rendered string content
        """
        template = self.get_template(template_name)
        
        # Convert pydantic model to dict if needed
        if hasattr(data, 'get_template_context'):
            context = data.get_template_context()
        elif hasattr(data, 'model_dump'):
            context = data.model_dump()
        else:
            context = dict(data)
            
        return template.render(**context)
    
    def render_to_file(
        self, 
        data: Any, 
        output_filename: str,
        template_name: Optional[str] = None
    ) -> Path:
        """
        Render content and save to file.
        
        Args:
            data: Data to render
            output_filename: Output file name
            template_name: Template to use
            
        Returns:
            Path to output file
        """
        content = self.render(data, template_name)
        
        # Ensure filename has extension
        if not output_filename.endswith(('.md', '.txt', '.html', '.json')):
            output_filename = f"{output_filename}.md"
            
        output_path = self.output_dir / output_filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return output_path
    
    @abstractmethod
    def generate(self, data: Any, **kwargs) -> Union[str, Path]:
        """
        Main generation method to be implemented by subclasses.
        
        Args:
            data: Input data model
            **kwargs: Additional generation options
            
        Returns:
            Generated content string or Path to file
        """
        pass
