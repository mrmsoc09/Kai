"""
K1 Agent Training System
Autonomous training, skill development, and Human-in-the-Loop (HiL) approval
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import json
import uuid


class TrainingStatus(str, Enum):
    """Status of training session"""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    PAUSED = "paused"


class TrainingType(str, Enum):
    """Types of training available"""
    SUPERVISED = "supervised"  # Learn from examples
    PRACTICE = "practice"  # Practice on tasks
    MENTORING = "mentoring"  # Learn from expert agent
    SIMULATION = "simulation"  # Simulated scenarios
    SELF_STUDY = "self_study"  # Self-directed learning


@dataclass
class TrainingTask:
    """Single training task or exercise"""
    task_id: str
    skill_name: str
    difficulty: float  # 0-1, training difficulty
    description: str
    estimated_duration: int  # Minutes
    success_criteria: List[str]
    learning_objectives: List[str]
    prerequisites: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)  # URLs, files, tools
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingCurriculum:
    """Structured training plan for skill development"""
    curriculum_id: str
    skill_name: str
    target_proficiency: float  # Goal proficiency (0-1)
    training_type: TrainingType
    tasks: List[TrainingTask] = field(default_factory=list)
    total_estimated_time: int = 0  # Minutes
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"  # Who created curriculum
    description: str = ""
    prerequisites: List[str] = field(default_factory=list)

    def get_total_duration(self) -> int:
        """Calculate total estimated training time"""
        return sum(t.estimated_duration for t in self.tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "curriculum_id": self.curriculum_id,
            "skill_name": self.skill_name,
            "target_proficiency": self.target_proficiency,
            "training_type": self.training_type.value,
            "task_count": len(self.tasks),
            "total_estimated_time": self.get_total_duration(),
            "description": self.description
        }


@dataclass
class TrainingRequest:
    """Request for training, submitted by agent"""
    request_id: str
    agent_id: str
    skill_name: str
    current_proficiency: float
    target_proficiency: float
    estimated_duration: int  # Minutes
    requested_at: datetime
    reason: str  # Why agent wants to train
    confidence_in_success: float  # Agent's confidence (0-1)
    required_resources: List[str] = field(default_factory=list)
    status: TrainingStatus = TrainingStatus.PENDING_APPROVAL
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None  # Human approver
    approval_notes: Optional[str] = None
    rejected_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "skill_name": self.skill_name,
            "current_proficiency": self.current_proficiency,
            "target_proficiency": self.target_proficiency,
            "estimated_duration": self.estimated_duration,
            "requested_at": self.requested_at.isoformat(),
            "reason": self.reason,
            "confidence_in_success": self.confidence_in_success,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approval_notes": self.approval_notes
        }


@dataclass
class TrainingSession:
    """Active training session"""
    session_id: str
    agent_id: str
    curriculum_id: str
    skill_name: str
    training_type: TrainingType
    started_at: datetime
    scheduled_end: datetime
    current_task_index: int = 0
    tasks_completed: int = 0
    overall_progress: float = 0.0
    efficiency_score: float = 0.0  # How efficiently training is happening

    # Performance tracking
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    proficiency_gains: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, gain)
    learning_curve: List[float] = field(default_factory=list)  # Proficiency over time

    # Status
    status: TrainingStatus = TrainingStatus.IN_PROGRESS
    completed_at: Optional[datetime] = None
    final_proficiency: Optional[float] = None
    completion_quality: float = 0.0  # 0-1

    def get_elapsed_time(self) -> int:
        """Get elapsed time in minutes"""
        if self.completed_at:
            elapsed = self.completed_at - self.started_at
        else:
            elapsed = datetime.utcnow() - self.started_at
        return int(elapsed.total_seconds() / 60)

    def get_time_remaining(self) -> int:
        """Get estimated remaining time"""
        elapsed = self.get_elapsed_time()
        scheduled_minutes = int((self.scheduled_end - self.started_at).total_seconds() / 60)
        remaining = max(0, scheduled_minutes - elapsed)
        return remaining

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "skill_name": self.skill_name,
            "training_type": self.training_type.value,
            "progress": self.overall_progress,
            "tasks_completed": self.tasks_completed,
            "status": self.status.value,
            "elapsed_time": self.get_elapsed_time(),
            "time_remaining": self.get_time_remaining(),
            "efficiency_score": self.efficiency_score,
            "completion_quality": self.completion_quality,
            "final_proficiency": self.final_proficiency
        }


@dataclass
class TrainingSchedule:
    """Training schedule for an agent"""
    schedule_id: str
    agent_id: str
    created_at: datetime
    skill_development_plan: Dict[str, List[TrainingCurriculum]] = field(default_factory=dict)
    active_sessions: Dict[str, TrainingSession] = field(default_factory=dict)
    completed_sessions: List[TrainingSession] = field(default_factory=list)
    total_training_hours: float = 0.0
    next_training_in: Optional[int] = None  # Minutes until next training

    def get_recommended_trainings(self, agent_skills: Dict[str, float]) -> List[str]:
        """Get recommended training based on skill gaps"""
        recommendations = []
        for skill_name, proficiency in agent_skills.items():
            if proficiency < 0.8:  # Skills below expert level
                gap = 0.8 - proficiency
                if gap > 0.2:  # Significant gap
                    recommendations.append(skill_name)
        return recommendations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "agent_id": self.agent_id,
            "active_sessions": len(self.active_sessions),
            "completed_sessions": len(self.completed_sessions),
            "total_training_hours": self.total_training_hours,
            "next_training_in": self.next_training_in
        }


class AgentTrainingSystem:
    """Manages autonomous agent training with HiL approval"""

    def __init__(self, llm_complete_fn: Callable):
        self.llm_complete_fn = llm_complete_fn

        # Training requests and approval
        self.training_requests: Dict[str, TrainingRequest] = {}
        self.pending_approvals: List[str] = []  # Request IDs awaiting approval

        # Curriculums and training content
        self.curriculums: Dict[str, TrainingCurriculum] = {}
        self.training_tasks: Dict[str, TrainingTask] = {}

        # Active training sessions
        self.active_sessions: Dict[str, TrainingSession] = {}
        self.training_schedules: Dict[str, TrainingSchedule] = {}

        # Historical data
        self.completed_sessions: List[TrainingSession] = []
        self.training_history: Dict[str, List[TrainingSession]] = {}  # agent_id -> sessions

    async def request_training(
        self,
        agent_id: str,
        skill_name: str,
        current_proficiency: float,
        target_proficiency: float,
        reason: str,
        confidence: float,
        estimated_duration: int
    ) -> TrainingRequest:
        """Agent autonomously requests training"""

        request = TrainingRequest(
            request_id=f"train_req_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            skill_name=skill_name,
            current_proficiency=current_proficiency,
            target_proficiency=target_proficiency,
            estimated_duration=estimated_duration,
            requested_at=datetime.utcnow(),
            reason=reason,
            confidence_in_success=confidence,
            status=TrainingStatus.PENDING_APPROVAL
        )

        self.training_requests[request.request_id] = request
        self.pending_approvals.append(request.request_id)

        return request

    async def get_pending_approvals(self) -> List[TrainingRequest]:
        """Get all training requests pending human approval"""
        return [
            self.training_requests[req_id]
            for req_id in self.pending_approvals
            if req_id in self.training_requests
        ]

    async def approve_training(
        self,
        request_id: str,
        approved_by: str,
        notes: Optional[str] = None
    ) -> TrainingRequest:
        """Human approves training request"""

        if request_id not in self.training_requests:
            raise ValueError(f"Training request {request_id} not found")

        request = self.training_requests[request_id]
        request.status = TrainingStatus.APPROVED
        request.approved_at = datetime.utcnow()
        request.approved_by = approved_by
        request.approval_notes = notes

        if request_id in self.pending_approvals:
            self.pending_approvals.remove(request_id)

        return request

    async def reject_training(
        self,
        request_id: str,
        rejected_by: str,
        reason: str
    ) -> TrainingRequest:
        """Human rejects training request"""

        if request_id not in self.training_requests:
            raise ValueError(f"Training request {request_id} not found")

        request = self.training_requests[request_id]
        request.status = TrainingStatus.REJECTED
        request.approved_by = rejected_by
        request.rejected_reason = reason

        if request_id in self.pending_approvals:
            self.pending_approvals.remove(request_id)

        return request

    async def create_curriculum(
        self,
        skill_name: str,
        target_proficiency: float,
        training_type: TrainingType,
        description: str
    ) -> TrainingCurriculum:
        """Create training curriculum for skill"""

        curriculum = TrainingCurriculum(
            curriculum_id=f"curr_{uuid.uuid4().hex[:8]}",
            skill_name=skill_name,
            target_proficiency=target_proficiency,
            training_type=training_type,
            description=description
        )

        self.curriculums[curriculum.curriculum_id] = curriculum
        return curriculum

    async def add_task_to_curriculum(
        self,
        curriculum_id: str,
        skill_name: str,
        difficulty: float,
        description: str,
        estimated_duration: int,
        success_criteria: List[str],
        learning_objectives: List[str]
    ) -> TrainingTask:
        """Add training task to curriculum"""

        if curriculum_id not in self.curriculums:
            raise ValueError(f"Curriculum {curriculum_id} not found")

        task = TrainingTask(
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            skill_name=skill_name,
            difficulty=difficulty,
            description=description,
            estimated_duration=estimated_duration,
            success_criteria=success_criteria,
            learning_objectives=learning_objectives
        )

        self.training_tasks[task.task_id] = task
        self.curriculums[curriculum_id].tasks.append(task)

        return task

    async def start_training_session(
        self,
        agent_id: str,
        curriculum_id: str,
        skill_name: str
    ) -> TrainingSession:
        """Start approved training session"""

        if curriculum_id not in self.curriculums:
            raise ValueError(f"Curriculum {curriculum_id} not found")

        curriculum = self.curriculums[curriculum_id]

        session = TrainingSession(
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            curriculum_id=curriculum_id,
            skill_name=skill_name,
            training_type=curriculum.training_type,
            started_at=datetime.utcnow(),
            scheduled_end=datetime.utcnow() + timedelta(minutes=curriculum.get_total_duration()),
            status=TrainingStatus.IN_PROGRESS
        )

        self.active_sessions[session.session_id] = session

        if agent_id not in self.training_history:
            self.training_history[agent_id] = []

        return session

    async def record_task_completion(
        self,
        session_id: str,
        task_id: str,
        success: bool,
        quality_score: float,
        proficiency_gain: float,
        feedback: Optional[str] = None
    ) -> TrainingSession:
        """Record completion of training task"""

        if session_id not in self.active_sessions:
            raise ValueError(f"Training session {session_id} not found")

        session = self.active_sessions[session_id]
        session.tasks_completed += 1
        session.proficiency_gains.append((datetime.utcnow().timestamp(), proficiency_gain))
        session.learning_curve.append(session.overall_progress + proficiency_gain)

        session.task_results.append({
            "task_id": task_id,
            "success": success,
            "quality_score": quality_score,
            "proficiency_gain": proficiency_gain,
            "feedback": feedback,
            "completed_at": datetime.utcnow().isoformat()
        })

        # Update overall progress
        if session.tasks_completed > 0 and session.curriculum_id in self.curriculums:
            curriculum = self.curriculums[session.curriculum_id]
            session.overall_progress = session.tasks_completed / len(curriculum.tasks)

        return session

    async def complete_training_session(
        self,
        session_id: str,
        final_proficiency: float,
        quality_score: float
    ) -> TrainingSession:
        """Complete training session"""

        if session_id not in self.active_sessions:
            raise ValueError(f"Training session {session_id} not found")

        session = self.active_sessions[session_id]
        session.status = TrainingStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        session.final_proficiency = final_proficiency
        session.completion_quality = quality_score

        # Calculate efficiency
        elapsed_minutes = session.get_elapsed_time()
        if elapsed_minutes > 0:
            session.efficiency_score = (session.overall_progress * quality_score) / (elapsed_minutes / 60)

        # Move to completed
        self.completed_sessions.append(session)
        self.training_history[session.agent_id].append(session)
        del self.active_sessions[session_id]

        return session

    async def identify_training_needs(
        self,
        agent_id: str,
        current_skills: Dict[str, float]
    ) -> Dict[str, Any]:
        """Autonomously identify training needs for agent"""

        prompt = f"""
        Agent {agent_id} current skills:
        {json.dumps(current_skills, indent=2)}

        Analyze the agent's skills and identify:
        1. Skills with gaps (< 0.6 proficiency)
        2. Skills that could be specialized (0.6-0.8 range)
        3. Complementary skills to develop
        4. Recommended training order
        5. Estimated priority (low/medium/high)

        Provide detailed training recommendations.
        Format as JSON with skill_name, gap_size, priority, estimated_hours, recommendation.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You analyze agent skills and recommend autonomous training programs."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except:
            return {
                "recommendations": [],
                "message": "Unable to analyze training needs"
            }

    async def generate_training_plan(
        self,
        agent_id: str,
        skill_name: str,
        current_proficiency: float,
        target_proficiency: float
    ) -> Dict[str, Any]:
        """Generate personalized training plan for agent"""

        prompt = f"""
        Create a training plan for agent {agent_id} to develop {skill_name} skill.

        Current proficiency: {current_proficiency}
        Target proficiency: {target_proficiency}
        Proficiency gap: {target_proficiency - current_proficiency}

        Plan should include:
        1. Learning stages with milestones
        2. Estimated duration per stage
        3. Recommended training methods (supervised, practice, mentoring, simulation)
        4. Resources and prerequisites
        5. Success metrics for each stage
        6. Risk factors and mitigation strategies

        Return as JSON with structured training plan.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You design comprehensive agent training plans and learning paths."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except:
            return {
                "stages": [],
                "total_estimated_duration": 0,
                "message": "Unable to generate training plan"
            }

    def get_agent_training_history(self, agent_id: str) -> List[TrainingSession]:
        """Get all training sessions for agent"""
        return self.training_history.get(agent_id, [])

    def get_training_statistics(self, agent_id: str) -> Dict[str, Any]:
        """Get training statistics for agent"""
        sessions = self.get_agent_training_history(agent_id)

        if not sessions:
            return {
                "agent_id": agent_id,
                "total_sessions": 0,
                "total_training_hours": 0.0,
                "average_completion_quality": 0.0,
                "skills_trained": []
            }

        total_hours = sum(s.get_elapsed_time() / 60 for s in sessions)
        avg_quality = sum(s.completion_quality for s in sessions) / len(sessions) if sessions else 0
        skills = list(set(s.skill_name for s in sessions))

        return {
            "agent_id": agent_id,
            "total_sessions": len(sessions),
            "total_training_hours": round(total_hours, 2),
            "average_completion_quality": round(avg_quality, 3),
            "average_efficiency_score": round(
                sum(s.efficiency_score for s in sessions) / len(sessions), 3
            ) if sessions else 0,
            "skills_trained": skills,
            "last_training": sessions[-1].completed_at.isoformat() if sessions else None
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert training system state to dictionary"""
        return {
            "pending_approvals": len(self.pending_approvals),
            "active_sessions": len(self.active_sessions),
            "completed_sessions": len(self.completed_sessions),
            "total_curriculums": len(self.curriculums),
            "agents_in_training": len(self.training_history)
        }


# Global instance
training_system = None


def initialize_training_system(llm_complete_fn: Callable) -> AgentTrainingSystem:
    """Initialize agent training system"""
    global training_system

    training_system = AgentTrainingSystem(llm_complete_fn)
    print("✓ Agent training system initialized")

    return training_system
