"""
Generator for E-Books.
"""

from pathlib import Path
from typing import Union, Optional, List

from content_engine.generators.base import BaseGenerator
from content_engine.models.ebook import Ebook, EbookFormat


class EbookGenerator(BaseGenerator):
    """Generator for e-books with chapter support."""
    
    def __init__(
        self, 
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ):
        super().__init__(
            template_dir=template_dir,
            output_dir=output_dir,
            template_name="ebook/chapter.md.j2"
        )
    
    def generate(
        self,
        ebook: Ebook,
        output_file: Optional[str] = None,
        format: EbookFormat = EbookFormat.MARKDOWN
    ) -> Union[str, Path]:
        """
        Generate complete e-book.
        
        Args:
            ebook: Ebook model
            output_file: Optional output filename
            format: Output format
            
        Returns:
            Rendered content or file path
        """
        # Update word count
        ebook.metadata.word_count = ebook.calculate_word_count()
        
        # Generate table of contents if not provided
        if not ebook.table_of_contents:
            ebook.table_of_contents = [
                {"number": ch.number, "title": ch.title, "page": i+1}
                for i, ch in enumerate(ebook.chapters)
            ]
        
        if output_file:
            return self.render_to_file(ebook, output_file, "ebook/full_book.md.j2")
        
        return self.render(ebook, "ebook/full_book.md.j2")
    
    def generate_chapter(
        self,
        ebook: Ebook,
        chapter_number: int,
        output_file: Optional[str] = None
    ) -> Union[str, Path]:
        """Generate single chapter."""
        chapter = next(
            (c for c in ebook.chapters if c.number == chapter_number), 
            None
        )
        if not chapter:
            raise ValueError(f"Chapter {chapter_number} not found")
        
        context = {
            "ebook": ebook.model_dump(),
            "chapter": chapter.model_dump(),
            "metadata": ebook.metadata.model_dump()
        }
        
        if output_file:
            path = self.output_dir / output_file
            template = self.env.get_template("ebook/chapter.md.j2")
            content = template.render(**context)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return path
        
        template = self.env.get_template("ebook/chapter.md.j2")
        return template.render(**context)
    
    def generate_toc(self, ebook: Ebook) -> str:
        """Generate table of contents."""
        template = self.env.get_template("ebook/toc.md.j2")
        return template.render(ebook=ebook.model_dump())
