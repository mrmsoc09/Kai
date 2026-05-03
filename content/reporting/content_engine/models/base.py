"""
Base models for all content types.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class Classification(str, Enum):
    """Standard classification levels."""
    UNCLASSIFIED = "UNCLASSIFIED"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"
    TOP_SECRET = "TOP SECRET"
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"


class ContentMetadata(BaseModel):
    """Common metadata for all content types."""
    
    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field(default="Content Engine")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    version: str = Field(default="1.0")
    classification: Classification = Field(default=Classification.UNCLASSIFIED)
    distribution: str = Field(default="Distribution Statement A")
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("updated_at")
    @classmethod
    def set_updated(cls, v: Optional[datetime], info) -> datetime:
        if v is None:
            return info.data.get("created_at", datetime.utcnow())
        return v


class BaseContent(BaseModel):
    """Abstract base class for all content types."""
    
    id: UUID = Field(default_factory=uuid4)
    metadata: ContentMetadata
    content_body: str = Field(default="")
    summary: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
        
    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary for template rendering."""
        return self.model_dump()
    
    def get_template_context(self) -> Dict[str, Any]:
        """Get context dictionary for Jinja2 templates."""
        context = self.to_dict()
        context["generated_at"] = datetime.utcnow().isoformat()
        return context
