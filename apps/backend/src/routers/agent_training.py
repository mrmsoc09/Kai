"""
Router for K1 Agent Training and Subagent Management
Handles autonomous training requests, HiL approval, skill development, and subagent spawning
"""

from fastapi import APIRouter, HTTPException, WebSocket
from typing import Dict, List, Any, Optional
import asyncio
import json

router = APIRouter(prefix="/api/agents", tags=["agent-training"])

# Global references (set during startup)
training_system = None
autonomous_system = None


def get_systems():
    """Get references to training and autonomous systems"""
    from apps.backend.src.core.agent_training import training_system as ts_ref
    from apps.backend.src.core.autonomous_agent_system import autonomous_system as as_ref

    return ts_ref, as_ref


# ==================== TRAINING REQUESTS (AUTONOMOUS) ====================

@router.post("/{agent_id}/request-training")
async def agent_request_training(
    agent_id: str,
    skill_name: str,
    target_proficiency: float,
    reason: str,
    confidence: float = 0.5,
    estimated_duration: Optional[int] = None
) -> Dict[str, Any]:
    """Agent autonomously requests training"""
    ts_ref, as_ref = get_systems()

    if not ts_ref or not as_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]

    try:
        # Get current proficiency
        current_proficiency = agent.memory.get_skill_level(skill_name) if skill_name in agent.memory.skill_levels else 0.0

        # Auto-estimate duration if not provided
        if estimated_duration is None:
            gap = max(0.01, target_proficiency - current_proficiency)
            estimated_duration = int((gap * 100) / 5)  # 5% per minute rough estimate

        # Create training request
        request = await ts_ref.request_training(
            agent_id=agent_id,
            skill_name=skill_name,
            current_proficiency=current_proficiency,
            target_proficiency=target_proficiency,
            reason=reason,
            confidence=confidence,
            estimated_duration=estimated_duration
        )

        return {
            "request_id": request.request_id,
            "status": request.status.value,
            "agent_id": agent_id,
            "skill_name": skill_name,
            "current_proficiency": current_proficiency,
            "target_proficiency": target_proficiency,
            "estimated_duration": estimated_duration,
            "requested_at": request.requested_at.isoformat(),
            "message": f"Training request submitted. Awaiting human approval."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training/pending-approvals")
async def get_pending_training_approvals() -> Dict[str, Any]:
    """Get all training requests pending human approval"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    pending = await ts_ref.get_pending_approvals()

    return {
        "pending_count": len(pending),
        "requests": [r.to_dict() for r in pending]
    }


@router.post("/training/{request_id}/approve")
async def approve_training_request(
    request_id: str,
    approved_by: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Human approves training request"""
    ts_ref, as_ref = get_systems()

    if not ts_ref or not as_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    try:
        request = await ts_ref.approve_training(request_id, approved_by, notes)

        # Start training session automatically
        curriculum_name = f"curriculum_{request.skill_name}"
        curriculum = None

        # Check if curriculum exists
        for curr in ts_ref.curriculums.values():
            if curr.skill_name == request.skill_name:
                curriculum = curr
                break

        # If no curriculum, create default one
        if not curriculum:
            from apps.backend.src.core.agent_training import TrainingType
            curriculum = await ts_ref.create_curriculum(
                skill_name=request.skill_name,
                target_proficiency=request.target_proficiency,
                training_type=TrainingType.PRACTICE,
                description=f"Auto-generated curriculum for {request.skill_name}"
            )

        # Start session
        session = await ts_ref.start_training_session(
            agent_id=request.agent_id,
            curriculum_id=curriculum.curriculum_id,
            skill_name=request.skill_name
        )

        return {
            "request_id": request_id,
            "status": "approved",
            "approved_by": approved_by,
            "approval_notes": notes,
            "training_session_id": session.session_id,
            "message": "Training approved and session started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/{request_id}/reject")
async def reject_training_request(
    request_id: str,
    rejected_by: str,
    reason: str
) -> Dict[str, Any]:
    """Human rejects training request"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    try:
        request = await ts_ref.reject_training(request_id, rejected_by, reason)

        return {
            "request_id": request_id,
            "status": "rejected",
            "rejected_by": rejected_by,
            "rejection_reason": reason,
            "message": "Training request rejected"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TRAINING SESSIONS ====================

@router.get("/training/sessions/active")
async def get_active_training_sessions() -> Dict[str, Any]:
    """Get all active training sessions"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    sessions = [
        session.to_dict()
        for session in ts_ref.active_sessions.values()
    ]

    return {
        "active_sessions": len(sessions),
        "sessions": sessions
    }


@router.get("/training/sessions/{session_id}")
async def get_training_session(session_id: str) -> Dict[str, Any]:
    """Get details of specific training session"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    if session_id not in ts_ref.active_sessions:
        if any(s.session_id == session_id for s in ts_ref.completed_sessions):
            # Find in completed
            session = next(s for s in ts_ref.completed_sessions if s.session_id == session_id)
            return session.to_dict()
        raise HTTPException(status_code=404, detail="Training session not found")

    return ts_ref.active_sessions[session_id].to_dict()


@router.post("/training/sessions/{session_id}/record-task")
async def record_task_completion(
    session_id: str,
    task_id: str,
    success: bool,
    quality_score: float,
    proficiency_gain: float,
    feedback: Optional[str] = None
) -> Dict[str, Any]:
    """Record completion of training task"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    try:
        session = await ts_ref.record_task_completion(
            session_id=session_id,
            task_id=task_id,
            success=success,
            quality_score=quality_score,
            proficiency_gain=proficiency_gain,
            feedback=feedback
        )

        return {
            "session_id": session_id,
            "tasks_completed": session.tasks_completed,
            "overall_progress": session.overall_progress,
            "new_proficiency": session.learning_curve[-1] if session.learning_curve else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/sessions/{session_id}/complete")
async def complete_training_session(
    session_id: str,
    final_proficiency: float,
    quality_score: float
) -> Dict[str, Any]:
    """Complete training session"""
    ts_ref, as_ref = get_systems()

    if not ts_ref or not as_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    try:
        session = await ts_ref.complete_training_session(
            session_id=session_id,
            final_proficiency=final_proficiency,
            quality_score=quality_score
        )

        # Update agent skill if using new skill system
        agent = as_ref.agents.get(session.agent_id)
        if agent and agent.skill_set:
            if session.skill_name in agent.skill_set.skills:
                agent.skill_set.skills[session.skill_name].proficiency = final_proficiency

        return {
            "session_id": session_id,
            "agent_id": session.agent_id,
            "status": "completed",
            "final_proficiency": final_proficiency,
            "completion_quality": quality_score,
            "efficiency_score": session.efficiency_score,
            "elapsed_time": session.get_elapsed_time(),
            "message": "Training session completed successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AGENT SKILLS ====================

@router.get("/{agent_id}/skills")
async def get_agent_skills(agent_id: str) -> Dict[str, Any]:
    """Get agent's skill profile"""
    _, as_ref = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]

    if agent.skill_set is None:
        agent.initialize_skills()

    return agent.get_skill_profile()


@router.get("/{agent_id}/skills/{skill_name}")
async def get_agent_skill(agent_id: str, skill_name: str) -> Dict[str, Any]:
    """Get specific skill profile"""
    _, as_ref = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]

    if agent.skill_set is None:
        agent.initialize_skills()

    return agent.get_skill_profile(skill_name)


@router.post("/{agent_id}/skills/{skill_name}/record-experience")
async def record_skill_experience(
    agent_id: str,
    skill_name: str,
    success: bool,
    quality_score: float,
    confidence: float,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Record skill experience for learning"""
    _, as_ref = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]

    try:
        if agent.skill_set is None:
            agent.initialize_skills()

        agent.record_skill_experience(skill_name, success, quality_score, confidence, context)

        updated_skill = agent.get_skill_profile(skill_name)

        return {
            "agent_id": agent_id,
            "skill_name": skill_name,
            "recorded": True,
            "new_proficiency": updated_skill.get("proficiency", 0),
            "success_rate": updated_skill.get("success_rate", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SUBAGENTS ====================

@router.post("/{agent_id}/spawn-subagent")
async def spawn_subagent(
    agent_id: str,
    name: str,
    objective: str,
    inherit_skills: bool = True
) -> Dict[str, Any]:
    """Parent agent spawns a subagent"""
    _, as_ref = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Parent agent not found")

    parent_agent = as_ref.agents[agent_id]

    try:
        from apps.backend.src.core.autonomous_agent_system import AgentObjective

        objective_enum = AgentObjective[objective.upper()]
        subagent = await parent_agent.spawn_subagent(name, objective_enum, inherit_skills)

        # Register subagent in orchestrator
        as_ref.agents[subagent.agent_id] = subagent

        return {
            "parent_id": agent_id,
            "subagent_id": subagent.agent_id,
            "name": subagent.name,
            "objective": subagent.primary_objective.value,
            "autonomy_level": subagent.autonomy_level,
            "inherits_skills": inherit_skills,
            "message": f"Subagent '{name}' spawned successfully"
        }
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown objective: {objective}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/subagents")
async def get_subagents(agent_id: str) -> Dict[str, Any]:
    """Get subagent hierarchy for agent"""
    _, as_ref = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]
    return agent.get_subagent_hierarchy()


@router.post("/{agent_id}/teach-subagent/{subagent_id}")
async def teach_subagent(
    agent_id: str,
    subagent_id: str,
    skill_name: str,
    target_proficiency: float,
    session_duration: int
) -> Dict[str, Any]:
    """Parent agent teaches skill to subagent"""
    _, as_ref = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Parent agent not found")

    agent = as_ref.agents[agent_id]

    try:
        # Ensure agent has skill system
        if agent.skill_set is None:
            agent.initialize_skills()

        result = await agent.teach_subagent(
            subagent_id=subagent_id,
            skill_name=skill_name,
            target_proficiency=target_proficiency,
            session_duration=session_duration
        )

        return {
            "teacher_id": agent_id,
            "student_id": subagent_id,
            "skill_name": skill_name,
            "transfer_efficiency": result["transfer_efficiency"],
            "proficiency_gain": result["proficiency_gain"],
            "new_student_proficiency": result["student_new_proficiency"],
            "teaching_successful": result["teaching_successful"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TRAINING ANALYTICS ====================

@router.get("/{agent_id}/training-history")
async def get_training_history(agent_id: str) -> Dict[str, Any]:
    """Get training history for agent"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    history = ts_ref.get_agent_training_history(agent_id)
    stats = ts_ref.get_training_statistics(agent_id)

    return {
        "agent_id": agent_id,
        "statistics": stats,
        "sessions": [s.to_dict() for s in history]
    }


@router.post("/{agent_id}/identify-training-needs")
async def identify_training_needs(
    agent_id: str,
    min_gap: float = 0.2
) -> Dict[str, Any]:
    """Autonomously identify agent's training needs"""
    ts_ref, as_ref = get_systems()

    if not ts_ref or not as_ref:
        raise HTTPException(status_code=503, detail="Systems not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]

    # Get current skills
    current_skills = agent.memory.skill_levels

    try:
        # Identify needs
        recommendations = await ts_ref.identify_training_needs(agent_id, current_skills)

        return {
            "agent_id": agent_id,
            "current_skills": current_skills,
            "recommendations": recommendations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/generate-training-plan")
async def generate_training_plan(
    agent_id: str,
    skill_name: str,
    current_proficiency: float,
    target_proficiency: float
) -> Dict[str, Any]:
    """Generate personalized training plan"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    try:
        plan = await ts_ref.generate_training_plan(
            agent_id=agent_id,
            skill_name=skill_name,
            current_proficiency=current_proficiency,
            target_proficiency=target_proficiency
        )

        return {
            "agent_id": agent_id,
            "skill_name": skill_name,
            "training_plan": plan
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SYSTEM STATUS ====================

@router.get("/training/status")
async def get_training_system_status() -> Dict[str, Any]:
    """Get training system status"""
    ts_ref, _ = get_systems()

    if not ts_ref:
        raise HTTPException(status_code=503, detail="Training system not initialized")

    return {
        "system": ts_ref.to_dict(),
        "pending_approvals": len(ts_ref.pending_approvals),
        "active_sessions": len(ts_ref.active_sessions),
        "completed_sessions": len(ts_ref.completed_sessions),
        "curriculums_available": len(ts_ref.curriculums)
    }
