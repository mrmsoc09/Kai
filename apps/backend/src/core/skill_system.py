"""
K1 Agent Skill System
Advanced skill profiling, progression tracking, and mastery certification
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
import json


class SkillCategory(str, Enum):
    """Skill categories for agent specialization"""
    RECONNAISSANCE = "reconnaissance"  # Information gathering
    VALIDATION = "validation"  # Finding verification
    ANALYSIS = "analysis"  # System analysis and mapping
    EXPLOITATION = "exploitation"  # Attack execution
    REPORTING = "reporting"  # Report generation
    LEARNING = "learning"  # Meta-skill: learning ability
    COLLABORATION = "collaboration"  # Team coordination
    PLANNING = "planning"  # Strategy and planning


class ProficiencyLevel(str, Enum):
    """Skill proficiency levels with certification"""
    NOVICE = "novice"  # 0.0-0.2: Just learning
    APPRENTICE = "apprentice"  # 0.2-0.4: Learning with guidance
    JOURNEYMAN = "journeyman"  # 0.4-0.6: Competent, works independently
    EXPERT = "expert"  # 0.6-0.8: Masters skill, teaches others
    MASTER = "master"  # 0.8-1.0: World-class proficiency


@dataclass
class SkillExperience:
    """Single experience point for a skill"""
    timestamp: datetime
    action_type: str  # Type of action taken
    success: bool
    outcome_quality: float  # 0-1 how good the outcome was
    context: Dict[str, Any]  # Context of the experience
    confidence: float  # Agent's confidence in action
    reflection: Optional[str] = None  # Agent's reflection on experience


@dataclass
class SkillProfile:
    """Complete profile for a single skill"""
    skill_name: str
    category: SkillCategory
    proficiency: float = 0.0  # 0.0-1.0
    total_experience: int = 0  # Total times used
    successful_uses: int = 0  # Successful executions
    failure_count: int = 0

    # Learning and progression
    experience_history: List[SkillExperience] = field(default_factory=list)
    learning_rate: float = 0.05  # How quickly skill improves
    plateau_level: float = 0.95  # Natural plateau for this agent

    # Mastery tracking
    certification_level: ProficiencyLevel = ProficiencyLevel.NOVICE
    certified_at: Optional[datetime] = None
    mastery_progress: float = 0.0  # Progress toward next certification
    prerequisites: List[str] = field(default_factory=list)
    teaches_to_proficiency: Optional[float] = None  # Can teach others to this level

    # Skill details
    last_used: Optional[datetime] = None
    days_since_used: int = 0
    degradation_rate: float = 0.01  # How quickly unused skills degrade
    metadata: Dict[str, Any] = field(default_factory=dict)

    def record_experience(self, experience: SkillExperience):
        """Record new experience with skill"""
        self.experience_history.append(experience)
        self.total_experience += 1
        self.last_used = experience.timestamp

        if experience.success:
            self.successful_uses += 1
            # Improve skill based on success
            improvement = self.learning_rate * experience.outcome_quality
            self.proficiency = min(self.plateau_level, self.proficiency + improvement)
        else:
            self.failure_count += 1
            # Minor degradation on failure
            self.proficiency = max(0.0, self.proficiency - 0.02)

        # Update certification level
        self._update_certification()

    def _update_certification(self):
        """Update certification based on proficiency"""
        if self.proficiency < 0.2:
            self.certification_level = ProficiencyLevel.NOVICE
        elif self.proficiency < 0.4:
            self.certification_level = ProficiencyLevel.APPRENTICE
        elif self.proficiency < 0.6:
            self.certification_level = ProficiencyLevel.JOURNEYMAN
        elif self.proficiency < 0.8:
            self.certification_level = ProficiencyLevel.EXPERT
        else:
            self.certification_level = ProficiencyLevel.MASTER

        if self.proficiency >= self.certification_level.value and not self.certified_at:
            self.certified_at = datetime.now(timezone.utc)

    def get_success_rate(self) -> float:
        """Get recent success rate"""
        if self.total_experience == 0:
            return 0.0
        return self.successful_uses / self.total_experience

    def get_proficiency_description(self) -> str:
        """Get human-readable proficiency description"""
        return f"{self.certification_level.value.title()} ({self.proficiency*100:.1f}%)"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "skill_name": self.skill_name,
            "category": self.category.value,
            "proficiency": self.proficiency,
            "proficiency_description": self.get_proficiency_description(),
            "total_experience": self.total_experience,
            "success_rate": self.get_success_rate(),
            "certification_level": self.certification_level.value,
            "certified_at": self.certified_at.isoformat() if self.certified_at else None,
            "learning_rate": self.learning_rate,
            "plateau_level": self.plateau_level,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "can_teach": self.teaches_to_proficiency is not None,
            "teaches_to_proficiency": self.teaches_to_proficiency
        }


@dataclass
class AgentSkillSet:
    """Complete skill set for an agent"""
    agent_id: str
    skills: Dict[str, SkillProfile] = field(default_factory=dict)
    primary_skills: List[str] = field(default_factory=list)  # Agent specializes in these
    learning_preferences: Dict[str, float] = field(default_factory=dict)  # Skill -> preference

    # Skill synergies and relationships
    skill_synergies: Dict[Tuple[str, str], float] = field(default_factory=dict)  # (skill1, skill2) -> synergy_bonus
    skill_dependencies: Dict[str, List[str]] = field(default_factory=dict)  # skill -> prerequisites

    # Overall metrics
    average_proficiency: float = 0.0
    specialization_score: float = 0.0  # How specialized agent is
    learning_velocity: float = 0.0  # How fast improving overall
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_or_update_skill(self, skill_name: str, category: SkillCategory) -> SkillProfile:
        """Add new skill or get existing"""
        if skill_name not in self.skills:
            self.skills[skill_name] = SkillProfile(skill_name, category)
        return self.skills[skill_name]

    def record_skill_experience(self, skill_name: str, experience: SkillExperience):
        """Record experience for a skill"""
        if skill_name not in self.skills:
            raise ValueError(f"Skill {skill_name} not found")

        self.skills[skill_name].record_experience(experience)
        self._update_metrics()

    def _update_metrics(self):
        """Update overall skill set metrics"""
        if not self.skills:
            self.average_proficiency = 0.0
            self.specialization_score = 0.0
            return

        proficiencies = [s.proficiency for s in self.skills.values()]
        self.average_proficiency = sum(proficiencies) / len(proficiencies)

        # Specialization = variance in proficiency (how uneven)
        if len(proficiencies) > 1:
            avg = self.average_proficiency
            variance = sum((p - avg) ** 2 for p in proficiencies) / len(proficiencies)
            self.specialization_score = min(1.0, variance)
        else:
            self.specialization_score = 0.0

        # Learning velocity = average improvement rate across skills
        learning_rates = [s.learning_rate for s in self.skills.values()]
        self.learning_velocity = sum(learning_rates) / len(learning_rates) if learning_rates else 0.0

        self.updated_at = datetime.now(timezone.utc)

    def get_proficient_skills(self, min_proficiency: float = 0.5) -> List[str]:
        """Get skills at or above proficiency threshold"""
        return [
            name for name, skill in self.skills.items()
            if skill.proficiency >= min_proficiency
        ]

    def get_primary_skillset(self) -> Dict[str, float]:
        """Get primary skills with proficiencies"""
        return {
            skill: self.skills[skill].proficiency
            for skill in self.primary_skills
            if skill in self.skills
        }

    def can_teach_skill(self, skill_name: str, target_level: float) -> bool:
        """Check if agent can teach skill to target proficiency"""
        if skill_name not in self.skills:
            return False
        skill = self.skills[skill_name]
        return (skill.teaches_to_proficiency is not None and
                skill.teaches_to_proficiency >= target_level)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "average_proficiency": self.average_proficiency,
            "specialization_score": self.specialization_score,
            "learning_velocity": self.learning_velocity,
            "total_skills": len(self.skills),
            "primary_skills": self.primary_skills,
            "proficient_skills": self.get_proficient_skills(0.5),
            "expert_skills": self.get_proficient_skills(0.6),
            "master_skills": self.get_proficient_skills(0.8),
            "skills": {
                name: skill.to_dict()
                for name, skill in self.skills.items()
            }
        }


@dataclass
class SkillTransfer:
    """Knowledge transfer between agents"""
    teacher_id: str
    student_id: str
    skill_name: str
    session_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    effectiveness: float = 0.0  # 0-1, how well knowledge transferred
    student_progress: float = 0.0  # How much student improved
    teacher_reflection: Optional[str] = None
    techniques_used: List[str] = field(default_factory=list)  # Teaching techniques

    def to_dict(self) -> Dict[str, Any]:
        return {
            "teacher_id": self.teacher_id,
            "student_id": self.student_id,
            "skill_name": self.skill_name,
            "session_id": self.session_id,
            "effectiveness": self.effectiveness,
            "student_progress": self.student_progress,
            "techniques_used": self.techniques_used
        }
