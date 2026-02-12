"""
Agent Coordinator
Cost-aware task delegation to specialized agents
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

from .specialized_agents import (
    OSINTAgent,
    ReasoningAgent,
    RepairAgent,
    AgentTask,
    AgentResult,
    AgentRole,
    get_osint_agent,
    get_reasoning_agent,
    get_repair_agent
)
from .budget_tracker import get_budget_tracker

logger = logging.getLogger(__name__)


class TaskCategory(str, Enum):
    """Task categorization for routing"""
    OSINT_RECON = "osint_recon"
    ANALYSIS_PLANNING = "analysis_planning"
    CODE_REPAIR = "code_repair"
    GENERAL = "general"


@dataclass
class AgentAssignment:
    """Assignment of task to agent"""
    agent_role: AgentRole
    estimated_cost_cents: float
    degraded: bool = False  # True if fallback to local due to budget
    message: str = ""


class AgentCoordinator:
    """
    Delegate tasks to specialized agents based on requirements.

    Routing Strategy:
    - OSINT/Recon → OSINTAgent (local, $0)
    - Analysis/Planning → ReasoningAgent (paid API with budget check)
    - Code repair → RepairAgent (hybrid)
    - General → Best available agent within budget
    """

    def __init__(self):
        """Initialize agent coordinator"""
        self.osint_agents: List[OSINTAgent] = [get_osint_agent()]
        self.reasoning_agents: List[ReasoningAgent] = [get_reasoning_agent()]
        self.repair_agents: List[RepairAgent] = [get_repair_agent()]
        self.budget_tracker = get_budget_tracker()

        logger.info("✓ AgentCoordinator initialized with specialized agents")

    async def delegate_task(
        self,
        task: AgentTask,
        session_id: str
    ) -> AgentAssignment:
        """
        Route task to appropriate agent based on type and budget.

        Returns:
            AgentAssignment with agent selection and cost estimate
        """

        # Classify task
        task_type = self._classify_task(task)

        logger.info(f"Delegating task: {task.description} (type: {task_type.value})")

        # Route based on type
        if task_type == TaskCategory.OSINT_RECON:
            agent = await self._get_available_osint_agent()
            return AgentAssignment(
                agent_role=agent.role,
                estimated_cost_cents=0.0,
                message="OSINT task routed to local agent (free)"
            )

        elif task_type == TaskCategory.ANALYSIS_PLANNING:
            remaining = self.budget_tracker.get_remaining(session_id)

            if remaining < 15:  # Less than $0.15
                # Fallback to local reasoning
                logger.warning(f"⚠️ Budget low (${remaining/100:.2f}) - using local reasoning")
                agent = await self._get_local_reasoning_fallback()
                return AgentAssignment(
                    agent_role=AgentRole.OSINT_SPECIALIST,  # Use OSINT for local fallback
                    estimated_cost_cents=0.0,
                    degraded=True,
                    message=f"Budget low - using local model (degraded reasoning)"
                )
            else:
                agent = await self._get_available_reasoning_agent()
                return AgentAssignment(
                    agent_role=agent.role,
                    estimated_cost_cents=150,  # ~$1.50 estimate
                    message="Reasoning task routed to paid API"
                )

        elif task_type == TaskCategory.CODE_REPAIR:
            remaining = self.budget_tracker.get_remaining(session_id)

            if remaining < 30:  # Less than $0.30
                logger.warning(f"⚠️ Insufficient budget for repair - need $0.30, have ${remaining/100:.2f}")
                return AgentAssignment(
                    agent_role=AgentRole.OSINT_SPECIALIST,
                    estimated_cost_cents=0.0,
                    degraded=True,
                    message="Budget insufficient for automated repair"
                )
            else:
                agent = await self._get_available_repair_agent()
                return AgentAssignment(
                    agent_role=agent.role,
                    estimated_cost_cents=50,  # ~$0.50 estimate
                    message="Repair task routed to hybrid agent"
                )

        else:  # GENERAL
            # Route to cheapest available agent
            agent = await self._get_available_osint_agent()
            return AgentAssignment(
                agent_role=agent.role,
                estimated_cost_cents=0.0,
                message="General task routed to OSINT agent (free)"
            )

    async def execute_delegated_task(
        self,
        task: AgentTask,
        session_id: str
    ) -> AgentResult:
        """
        Delegate and execute task with appropriate agent.

        Returns:
            AgentResult from the executing agent
        """

        # Get assignment
        assignment = await self.delegate_task(task, session_id)

        logger.info(f"Executing task with {assignment.agent_role.value}: {assignment.message}")

        # Get agent and execute
        if assignment.agent_role == AgentRole.OSINT_SPECIALIST:
            agent = await self._get_available_osint_agent()
            return await agent.execute_task(task, session_id)

        elif assignment.agent_role == AgentRole.REASONING_SPECIALIST:
            agent = await self._get_available_reasoning_agent()
            return await agent.execute_task(task, session_id)

        elif assignment.agent_role == AgentRole.REPAIR_SPECIALIST:
            agent = await self._get_available_repair_agent()
            return await agent.execute_task(task, session_id)

        else:
            # Fallback to OSINT
            agent = await self._get_available_osint_agent()
            return await agent.execute_task(task, session_id)

    async def multi_agent_workflow(
        self,
        workflow_tasks: List[AgentTask],
        session_id: str
    ) -> List[AgentResult]:
        """
        Execute multi-agent workflow with cost optimization.

        Executes tasks in order, routing each to optimal agent.
        """

        results = []

        for task in workflow_tasks:
            logger.info(f"Workflow step: {task.description}")

            # Delegate and execute
            result = await self.execute_delegated_task(task, session_id)
            results.append(result)

            # Check if workflow should stop on failure
            if not result.success and task.priority >= 8:
                logger.error(f"Critical task failed: {task.description}")
                break

        # Calculate total cost
        total_cost = sum(r.cost_cents for r in results)
        logger.info(f"Workflow complete: {len(results)} tasks, ${total_cost/100:.2f} total cost")

        return results

    def _classify_task(self, task: AgentTask) -> TaskCategory:
        """Classify task to determine routing"""

        description = task.description.lower()
        capabilities = [c.lower() for c in task.required_capabilities]

        # OSINT/Recon patterns
        osint_keywords = ["reconnaissance", "scanning", "enumerate", "discover", "osint", "recon"]
        if any(kw in description for kw in osint_keywords):
            return TaskCategory.OSINT_RECON

        if "reconnaissance" in capabilities or "scanning" in capabilities:
            return TaskCategory.OSINT_RECON

        # Analysis/Planning patterns
        reasoning_keywords = ["analyze", "assess", "evaluate", "plan", "strategy", "reason"]
        if any(kw in description for kw in reasoning_keywords):
            return TaskCategory.ANALYSIS_PLANNING

        if "reasoning" in capabilities or "analysis" in capabilities:
            return TaskCategory.ANALYSIS_PLANNING

        # Code repair patterns
        repair_keywords = ["repair", "fix", "patch", "refactor", "generate code"]
        if any(kw in description for kw in repair_keywords):
            return TaskCategory.CODE_REPAIR

        if "code_generation" in capabilities or "repair" in capabilities:
            return TaskCategory.CODE_REPAIR

        # Default to general
        return TaskCategory.GENERAL

    async def _get_available_osint_agent(self) -> OSINTAgent:
        """Get available OSINT agent"""
        # For now, return first agent (could implement load balancing)
        return self.osint_agents[0]

    async def _get_available_reasoning_agent(self) -> ReasoningAgent:
        """Get available Reasoning agent"""
        return self.reasoning_agents[0]

    async def _get_available_repair_agent(self) -> RepairAgent:
        """Get available Repair agent"""
        return self.repair_agents[0]

    async def _get_local_reasoning_fallback(self) -> OSINTAgent:
        """Get local agent for fallback reasoning"""
        # Use OSINT agent with local model for degraded reasoning
        return await self._get_available_osint_agent()

    async def get_agent_stats(self) -> Dict[str, Any]:
        """Get statistics for all agents"""

        stats = {
            "osint_agents": [],
            "reasoning_agents": [],
            "repair_agents": []
        }

        for agent in self.osint_agents:
            stats["osint_agents"].append({
                "role": agent.role.value,
                "model": agent.llm_model,
                "cost_profile": agent.cost_profile
            })

        for agent in self.reasoning_agents:
            stats["reasoning_agents"].append({
                "role": agent.role.value,
                "model": agent.llm_model,
                "cost_profile": agent.cost_profile
            })

        for agent in self.repair_agents:
            stats["repair_agents"].append({
                "role": agent.role.value,
                "model": agent.llm_model,
                "cost_profile": agent.cost_profile
            })

        return stats


# Global instance
_agent_coordinator: Optional[AgentCoordinator] = None


def get_agent_coordinator() -> AgentCoordinator:
    """Get global agent coordinator"""
    global _agent_coordinator
    if _agent_coordinator is None:
        _agent_coordinator = AgentCoordinator()
    return _agent_coordinator


def initialize_agent_coordinator() -> AgentCoordinator:
    """Initialize global agent coordinator"""
    global _agent_coordinator
    _agent_coordinator = AgentCoordinator()
    logger.info("✓ Global agent coordinator initialized")
    return _agent_coordinator
