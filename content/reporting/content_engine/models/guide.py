"""
Models for Guides, Tutorials, and Playbooks.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from content_engine.models.base import BaseContent, ContentMetadata


class DifficultyLevel(str, Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"


class Step(BaseModel):
    """Individual step in a guide or playbook."""
    
    number: int
    title: str
    description: str
    instructions: str
    expected_outcome: Optional[str] = None
    duration_minutes: Optional[int] = None
    tools_required: List[str] = Field(default_factory=list)
    commands: List[str] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    tips: List[str] = Field(default_factory=list)


class GuideMetadata(ContentMetadata):
    """Metadata for guides and tutorials."""
    
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.INTERMEDIATE)
    estimated_duration: Optional[str] = None  # e.g., "2 hours"
    prerequisites: List[str] = Field(default_factory=list)
    learning_objectives: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    target_audience: Optional[str] = None
    completion_criteria: Optional[str] = None


class Guide(BaseContent):
    """Standard guide or tutorial."""
    
    metadata: GuideMetadata
    introduction: str = Field(default="")
    steps: List[Step] = Field(default_factory=list)
    conclusion: str = Field(default="")
    resources: List[Dict[str, str]] = Field(default_factory=list)
    faq: List[Dict[str, str]] = Field(default_factory=list)


class Playbook(Guide):
    """Operational playbook (extends Guide with specific fields)."""
    
    trigger_conditions: List[str] = Field(default_factory=list)
    escalation_paths: List[Dict[str, str]] = Field(default_factory=list)
    roles_responsibilities: Dict[str, str] = Field(default_factory=dict)
    success_metrics: List[str] = Field(default_factory=list)
    rollback_procedure: Optional[str] = None
    communication_plan: Optional[str] = None


class Tutorial(Guide):
    """Educational tutorial (extends Guide)."""
    
    exercises: List[Dict[str, Any]] = Field(default_factory=list)
    quiz_questions: List[Dict[str, Any]] = Field(default_factory=list)
    certification_available: bool = Field(default=False)
    skill_level_progression: Optional[str] = None
