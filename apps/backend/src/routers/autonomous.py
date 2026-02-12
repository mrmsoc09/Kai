"""
Router for K1 Autonomous Multi-Agent Systems
Exposes endpoints for autonomous agent management, reasoning, and swarm coordination
"""

from fastapi import APIRouter, HTTPException, WebSocket
from typing import Dict, List, Any, Optional
import asyncio
import json

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])

# Global references to autonomous systems (set during startup)
autonomous_system = None
reasoning_engine = None
swarm_coordinator = None


def get_systems():
    """Get references to autonomous systems"""
    try:
        # Try to get from module globals first
        from apps.backend.src.core.autonomous_agent_system import (
            autonomous_system as as_ref,
            reasoning_engine as re_ref,
            swarm_coordinator as sc_ref
        )
        if as_ref or re_ref or sc_ref:
            return as_ref, re_ref, sc_ref
    except:
        pass

    # Fall back to router module globals
    return globals().get("autonomous_system"), globals().get("reasoning_engine"), globals().get("swarm_coordinator")


def set_systems(as_ref, re_ref, sc_ref):
    """Set references to autonomous systems (called during startup)"""
    global autonomous_system, reasoning_engine, swarm_coordinator
    autonomous_system = as_ref
    reasoning_engine = re_ref
    swarm_coordinator = sc_ref


# ==================== AUTONOMOUS AGENTS ====================

@router.get("/agents")
async def list_autonomous_agents() -> Dict[str, Any]:
    """List all autonomous agents in the system"""
    as_ref, _, _ = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    agents_info = []
    for agent_id, agent in as_ref.agents.items():
        agents_info.append({
            "agent_id": agent_id,
            "name": agent.name,
            "objective": agent.primary_objective.value if agent.primary_objective else None,
            "autonomy_level": agent.autonomy_level,
            "decision_mode": agent.decision_mode.value if agent.decision_mode else None,
            "status": agent.status,
            "performance": {
                "success_rate": agent.memory.avg_success_rate,
                "success_count": agent.memory.success_count,
                "failure_count": agent.memory.failure_count,
                "improvement_rate": agent.memory.improvement_rate
            },
            "skills": agent.memory.skill_levels,
            "peers": list(agent.peer_agents.keys())
        })

    return {
        "total_agents": len(as_ref.agents),
        "agents": agents_info,
        "team_metrics": {
            "learning_rate": as_ref.team_learning_rate,
            "cooperation_level": as_ref.team_cooperation_level,
            "efficiency_score": as_ref.team_efficiency_score
        }
    }


@router.post("/agents/spawn")
async def spawn_agent(
    objective: str,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """Spawn a new specialist autonomous agent"""
    as_ref, _, _ = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    try:
        from apps.backend.src.core.autonomous_agent_system import AgentObjective

        objective_enum = AgentObjective[objective.upper()]
        agent = await as_ref.spawn_specialist_agent(objective_enum, name)

        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "objective": agent.primary_objective.value,
            "autonomy_level": agent.autonomy_level,
            "status": agent.status
        }
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown objective: {objective}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}")
async def get_agent_details(agent_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific agent"""
    as_ref, _, _ = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]
    return agent.to_dict()


@router.post("/agents/{agent_id}/execute")
async def execute_agent_task(agent_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a task using a specific agent"""
    as_ref, _, _ = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    if agent_id not in as_ref.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = as_ref.agents[agent_id]

    try:
        # Agent thinks autonomously
        action = await agent.think(task, as_ref.llm_complete_fn)

        # Execute action
        result = await agent.execute_action(action, as_ref._execute_tool)

        # Learn from outcome
        agent.memory.record_experience(action, result)

        return {
            "agent_id": agent_id,
            "task": task,
            "action": action,
            "result": result,
            "agent_learning": {
                "new_success_rate": agent.memory.avg_success_rate,
                "improvement_rate": agent.memory.improvement_rate
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AUTONOMOUS REASONING ====================

@router.post("/reasoning/goals")
async def autonomous_goal_setting(
    mission: str,
    capabilities: List[str],
    environment: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Autonomously generate goals based on mission and capabilities"""
    _, re_ref, _ = get_systems()

    if not re_ref:
        raise HTTPException(status_code=503, detail="Reasoning engine not initialized")

    try:
        goals = await re_ref.autonomous_goal_setting(
            mission=mission,
            agent_capabilities=capabilities,
            environment=environment or {}
        )

        return {
            "mission": mission,
            "goals_generated": len(goals),
            "goals": [
                {
                    "id": g.goal_id,
                    "description": g.description,
                    "type": g.objective_type,
                    "priority": g.priority,
                    "success_criteria": g.success_criteria
                }
                for g in goals
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reasoning/decompose")
async def decompose_problem(
    problem: str,
    max_depth: int = 3
) -> Dict[str, Any]:
    """Decompose complex problem into sub-problems"""
    _, re_ref, _ = get_systems()

    if not re_ref:
        raise HTTPException(status_code=503, detail="Reasoning engine not initialized")

    try:
        decomposition = await re_ref.decompose_complex_problem(
            problem=problem,
            max_depth=max_depth
        )
        return decomposition
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reasoning/chain-of-thought")
async def chain_of_thought(
    problem: str,
    max_steps: int = 5
) -> Dict[str, Any]:
    """Perform chain-of-thought reasoning"""
    _, re_ref, _ = get_systems()

    if not re_ref:
        raise HTTPException(status_code=503, detail="Reasoning engine not initialized")

    try:
        conclusion, trace = await re_ref.chain_of_thought_reasoning(
            problem=problem,
            max_steps=max_steps
        )

        return {
            "problem": problem,
            "conclusion": conclusion,
            "reasoning_trace": trace.to_dict(),
            "steps": trace.steps,
            "confidence": trace.confidence
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reasoning/tree-of-thoughts")
async def tree_of_thoughts(
    problem: str,
    num_branches: int = 3
) -> Dict[str, Any]:
    """Explore multiple reasoning paths"""
    _, re_ref, _ = get_systems()

    if not re_ref:
        raise HTTPException(status_code=503, detail="Reasoning engine not initialized")

    try:
        result = await re_ref.tree_of_thoughts_reasoning(
            problem=problem,
            num_branches=num_branches
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reasoning/profile")
async def get_reasoning_profile() -> Dict[str, Any]:
    """Get reasoning engine performance profile"""
    _, re_ref, _ = get_systems()

    if not re_ref:
        raise HTTPException(status_code=503, detail="Reasoning engine not initialized")

    return re_ref.get_reasoning_profile()


# ==================== SWARM COORDINATION ====================

@router.post("/swarm/coordinate")
async def coordinate_swarm_task(
    task: Dict[str, Any],
    agents: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Coordinate swarm of agents on a task"""
    as_ref, _, sc_ref = get_systems()

    if not sc_ref or not as_ref:
        raise HTTPException(status_code=503, detail="Swarm coordination system not initialized")

    try:
        # Select agents for task
        if agents:
            selected_agents = [as_ref.agents[aid] for aid in agents if aid in as_ref.agents]
        else:
            selected_agents = list(as_ref.agents.values())

        if not selected_agents:
            raise ValueError("No agents available for swarm coordination")

        # Coordinate execution
        result = await sc_ref.coordinate_swarm_task(task, selected_agents)

        return {
            "task": task,
            "agents_involved": len(selected_agents),
            "collaboration_pattern": sc_ref.active_pattern.value,
            "result": result,
            "swarm_status": sc_ref.get_swarm_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swarm/select-pattern")
async def select_collaboration_pattern(
    task_complexity: float,
    time_constraint: float,
    agent_diversity: float
) -> Dict[str, Any]:
    """Select best collaboration pattern for task"""
    _, _, sc_ref = get_systems()

    if not sc_ref:
        raise HTTPException(status_code=503, detail="Swarm coordination system not initialized")

    try:
        pattern = await sc_ref.select_collaboration_pattern(
            task_complexity=task_complexity,
            time_constraint=time_constraint,
            agent_diversity=agent_diversity
        )

        return {
            "selected_pattern": pattern.value,
            "task_parameters": {
                "complexity": task_complexity,
                "time_constraint": time_constraint,
                "diversity": agent_diversity
            },
            "swarm_status": sc_ref.get_swarm_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/swarm/status")
async def get_swarm_status() -> Dict[str, Any]:
    """Get comprehensive swarm status"""
    _, _, sc_ref = get_systems()

    if not sc_ref:
        raise HTTPException(status_code=503, detail="Swarm coordination system not initialized")

    return sc_ref.get_swarm_status()


@router.get("/swarm/emergent-properties")
async def get_emergent_properties() -> Dict[str, Any]:
    """Get detected emergent properties of the swarm"""
    _, _, sc_ref = get_systems()

    if not sc_ref:
        raise HTTPException(status_code=503, detail="Swarm coordination system not initialized")

    return {
        "swarm_intelligence_level": sc_ref.swarm_intelligence_level,
        "collective_efficiency": sc_ref.collective_efficiency,
        "emergent_properties": list(sc_ref.emergent_properties.keys()),
        "emergence_indicators": sc_ref.emergence_indicators[-20:],
        "active_pattern": sc_ref.active_pattern.value
    }


# ==================== AUTONOMOUS TASK EXECUTION ====================

@router.post("/execute")
async def execute_autonomous_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Execute task autonomously with agent self-organization"""
    as_ref, _, _ = get_systems()

    if not as_ref:
        raise HTTPException(status_code=503, detail="Autonomous system not initialized")

    try:
        result = await as_ref.execute_autonomous_task(task)

        return {
            "task": task,
            "result": result,
            "system_status": {
                "total_agents": len(as_ref.agents),
                "team_efficiency": as_ref.team_efficiency_score,
                "team_learning_rate": as_ref.team_learning_rate
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SYSTEM STATUS ====================

@router.get("/status")
async def get_autonomous_system_status() -> Dict[str, Any]:
    """Get complete autonomous system status"""
    as_ref, re_ref, sc_ref = get_systems()

    status = {
        "autonomous_agents": None,
        "reasoning_engine": None,
        "swarm_coordinator": None
    }

    if as_ref:
        status["autonomous_agents"] = {
            "total_agents": len(as_ref.agents),
            "team_efficiency": as_ref.team_efficiency_score,
            "team_learning_rate": as_ref.team_learning_rate,
            "team_cooperation": as_ref.team_cooperation_level
        }

    if re_ref:
        profile = re_ref.get_reasoning_profile()
        status["reasoning_engine"] = {
            "total_traces": profile.get("total_reasoning_traces"),
            "avg_depth": profile.get("avg_reasoning_depth"),
            "avg_confidence": profile.get("avg_confidence"),
            "total_goals": profile.get("total_goals"),
            "learned_patterns": profile.get("learned_patterns")
        }

    if sc_ref:
        swarm_status = sc_ref.get_swarm_status()
        status["swarm_coordinator"] = {
            "agent_count": swarm_status.get("agent_count"),
            "swarm_intelligence": swarm_status.get("swarm_intelligence"),
            "collective_efficiency": swarm_status.get("collective_efficiency"),
            "active_pattern": swarm_status.get("active_pattern")
        }

    return status


# ==================== WEBSOCKET REAL-TIME MONITORING ====================

@router.websocket("/ws/monitor")
async def websocket_autonomous_monitor(websocket: WebSocket):
    """WebSocket endpoint for real-time autonomous system monitoring"""
    await websocket.accept()

    try:
        while True:
            # Send system status every 2 seconds
            as_ref, re_ref, sc_ref = get_systems()

            status = {
                "timestamp": str(asyncio.get_event_loop().time()),
                "agents": len(as_ref.agents) if as_ref else 0,
                "team_efficiency": as_ref.team_efficiency_score if as_ref else 0,
                "reasoning_traces": len(re_ref.reasoning_traces) if re_ref else 0,
                "swarm_intelligence": sc_ref.swarm_intelligence_level if sc_ref else 0
            }

            await websocket.send_text(json.dumps(status))
            await asyncio.sleep(2)

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()
