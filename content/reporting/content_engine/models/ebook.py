"""
Models for E-Book generation.
"""

from datetime import date
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, HttpUrl

from content_engine.models.base import BaseContent, ContentMetadata


class EbookFormat(str, Enum):
    PDF = "pdf"
    EPUB = "epub"
    MOBI = "mobi"
    HTML = "html"
    MARKDOWN = "markdown"


class Chapter(BaseModel):
    """E-book chapter model."""
    
    number: int
    title: str
    content: str = Field(default="")
    summary: Optional[str] = None
    word_count: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    references: List[Dict[str, str]] = Field(default_factory=list)


class EbookMetadata(ContentMetadata):
    """Extended metadata for e-books."""
    
    subtitle: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[date] = None
    edition: str = Field(default="1st Edition")
    language: str = Field(default="en")
    cover_image: Optional[str] = None
    target_audience: Optional[str] = None
    genre: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None


class Ebook(BaseContent):
    """E-book container model."""
    
    metadata: EbookMetadata
    chapters: List[Chapter] = Field(default_factory=list)
    front_matter: Dict[str, str] = Field(default_factory=dict)  # dedication, foreword, etc.
    back_matter: Dict[str, str] = Field(default_factory=dict)  # appendix, index, etc.
    table_of_contents: List[Dict[str, Any]] = Field(default_factory=list)
    formats_available: List[EbookFormat] = Field(default=[EbookFormat.PDF])
    
    def calculate_word_count(self) -> int:
        """Calculate total word count across all chapters."""
        total = 0
        for chapter in self.chapters:
            if chapter.word_count:
                total += chapter.word_count
            else:
                # Rough estimate
                total += len(chapter.content.split())
        return total
