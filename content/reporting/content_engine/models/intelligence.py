"""
Models for Intelligence Reports.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator

from content_engine.models.base import BaseContent, ContentMetadata, Classification


class IntelligenceType(str, Enum):
    HUMINT = "HUMINT"
    SIGINT = "SIGINT"
    GEOINT = "GEOINT"
    OSINT = "OSINT"
    CYBERINT = "CYBERINT"
    FININT = "FININT"
    TECHINT = "TECHINT"


class Source(BaseModel):
    """Intelligence source information."""
    
    name: str
    reliability: str = Field(default="A", pattern="^[A-F]$")
    credibility: str = Field(default="1", pattern="^[1-6]$")
    description: Optional[str] = None
    date_acquired: Optional[datetime] = None


class IntelligenceMetadata(ContentMetadata):
    """Extended metadata for intelligence reports."""
    
    intel_type: IntelligenceType = Field(default=IntelligenceType.OSINT)
    classification: Classification = Field(default=Classification.UNCLASSIFIED)
    report_date: datetime = Field(default_factory=datetime.utcnow)
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    countries_mentioned: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


class IntelligenceReport(BaseContent):
    """Intelligence report model."""
    
    metadata: IntelligenceMetadata
    sources: List[Source] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    assessment: str = Field(default="")
    confidence_level: str = Field(default="Medium", pattern="^(Low|Medium|High|Very High)$")
    handling_instructions: Optional[str] = None
    annexes: List[Dict[str, Any]] = Field(default_factory=list)
    
    @field_validator("key_findings")
    @classmethod
    def validate_findings(cls, v: List[str]) -> List[str]:
        if not v:
            return []
        return [f.strip() for f in v if f.strip()]
