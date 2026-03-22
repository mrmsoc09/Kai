"""
Specialized Agents with Cost Discipline
OSINTAgent, ReasoningAgent, RepairAgent with budget awareness
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum

from .budget_tracker import get_budget_tracker
from .hybrid_model_router import get_hybrid_router, RoutingDecision
from .model_bidding import TaskDefinition

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Agent specialization roles"""
    OSINT_SPECIALIST = "osint_specialist"
    REASONING_SPECIALIST = "reasoning_specialist"
    REPAIR_SPECIALIST = "repair_specialist"
    COORDINATION_SPECIALIST = "coordination_specialist"


@dataclass
class AgentTask:
    """Task for specialized agent"""
    task_id: str
    description: str
    required_capabilities: List[str]
    priority: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result from agent execution"""
    agent_role: AgentRole
    task_id: str
    success: bool
    output: Dict[str, Any]
    cost_cents: float = 0.0
    execution_time_ms: float = 0.0
    model_used: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AutonomousAgent:
    """
    Base class for autonomous agents with budget awareness.
    """

    def __init__(
        self,
        role: AgentRole,
        llm_model: str,
        autonomy_level: int = 2,
        budget_threshold_cents: int = 100
    ):
        """Initialize autonomous agent"""
        self.role = role
        self.llm_model = llm_model
        self.autonomy_level = autonomy_level  # 1-5 scale
        self.budget_threshold = budget_threshold_cents

        # Cost tracking
        self.cost_profile = {
            "total_spent_cents": 0.0,
            "task_count": 0,
            "avg_cost_per_task": 0.0
        }

        # Tools available to agent
        self.tools: List[str] = []

        logger.info(f"✓ {role.value} initialized with model: {llm_model}")

    def budget_exceeded(self, session_id: str) -> bool:
        """Check if agent has exceeded its budget threshold"""
        tracker = get_budget_tracker()
        session = tracker.get_session_budget(session_id)

        # Check if agent's spending approaches threshold
        agent_spent = self.cost_profile["total_spent_cents"]
        return agent_spent >= self.budget_threshold

    async def execute_task(
        self,
        task: AgentTask,
        session_id: str
    ) -> AgentResult:
        """Execute task (to be overridden by subclasses)"""
        raise NotImplementedError("Subclass must implement execute_task")

    def _update_cost_profile(self, cost_cents: float):
        """Update agent's cost tracking"""
        self.cost_profile["total_spent_cents"] += cost_cents
        self.cost_profile["task_count"] += 1
        self.cost_profile["avg_cost_per_task"] = (
            self.cost_profile["total_spent_cents"] /
            self.cost_profile["task_count"]
        )


class OSINTAgent(AutonomousAgent):
    """
    OSINT/Recon specialist - ALWAYS uses local models.
    Cost: $0 per task

    Tools: subfinder, amass, nmap, shodan, nuclei
    LLM: Local Ollama models only
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.OSINT_SPECIALIST,
            llm_model="qwen2.5-coder:7b",  # Local only
            autonomy_level=3,
            budget_threshold_cents=0  # No paid API budget
        )

        self.tools = [
            "subfinder",
            "amass",
            "nmap",
            "shodan",
            "nuclei",
            "httpx",
            "katana"
        ]

        self.cost_profile["model_cost"] = 0.0  # Always free
        self.cost_profile["api_costs"] = 0.0

    async def execute_task(
        self,
        task: AgentTask,
        session_id: str
    ) -> AgentResult:
        """Execute OSINT/recon task using local models"""

        start_time = datetime.now(timezone.utc)

        try:
            # OSINT tasks always use local models (free)
            logger.info(f"OSINT Agent executing: {task.description}")

            # Create task definition for routing
            task_def = TaskDefinition(
                task_id=task.task_id,
                name=f"OSINT: {task.description}",
                description=task.description,
                complexity_estimate=3,  # OSINT is moderate complexity
                required_capabilities=task.required_capabilities,
                security_sensitive=True,
                estimated_tokens_input=1500,
                estimated_tokens_output=800
            )

            # Route to local model (should always be local for OSINT)
            router = get_hybrid_router()
            routing = await router.route_task(task_def, session_id)

            if not routing.is_local:
                logger.warning("⚠️ OSINT task routed to paid API - forcing local fallback")
                routing.model_id = "qwen2.5-coder:7b"
                routing.is_local = True
                routing.estimated_cost_cents = 0.0

            # Execute OSINT workflow (simulated for now)
            output = await self._run_osint_workflow(task, routing)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Cost is always $0 for OSINT (local models)
            self._update_cost_profile(0.0)

            return AgentResult(
                agent_role=self.role,
                task_id=task.task_id,
                success=True,
                output=output,
                cost_cents=0.0,
                execution_time_ms=execution_time,
                model_used=routing.model_id
            )

        except Exception as e:
            logger.error(f"OSINT Agent error: {str(e)}")
            return AgentResult(
                agent_role=self.role,
                task_id=task.task_id,
                success=False,
                output={},
                error=str(e)
            )

    async def _run_osint_workflow(
        self,
        task: AgentTask,
        routing: RoutingDecision
    ) -> Dict[str, Any]:
        """Run OSINT workflow with specified tools"""

        # Simulated OSINT results
        # In production, this would call actual tools
        results = {
            "task": task.description,
            "tools_used": self.tools[:3],  # Use first 3 tools
            "model": routing.model_id,
            "findings": {
                "subdomains_discovered": 15,
                "open_ports": [80, 443, 8080],
                "technologies_detected": ["nginx", "php", "mysql"],
                "potential_vulnerabilities": []
            },
            "cost": "$0.00 (local model)"
        }

        return results

    async def discover_vulnerabilities(self, target: str) -> Dict[str, Any]:
        """Discover vulnerabilities for a target"""

        task = AgentTask(
            task_id=f"osint_discover_{target}",
            description=f"Discover vulnerabilities for {target}",
            required_capabilities=["reconnaissance", "scanning"]
        )

        # Use a default session for autonomous execution
        result = await self.execute_task(task, session_id="osint_autonomous")

        return result.output


class ReasoningAgent(AutonomousAgent):
    """
    Complex reasoning specialist - uses paid APIs with budget awareness.
    Cost: Variable based on task complexity

    LLM: Best reasoning model within budget (Claude Opus, GPT-4o)
    Budget: $1-5 per session
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.REASONING_SPECIALIST,
            llm_model="claude-opus-4.5",  # Best reasoning
            autonomy_level=2,
            budget_threshold_cents=500  # $5 max per session
        )

        self.tools = [
            "code_analysis",
            "logical_reasoning",
            "strategic_planning",
            "vulnerability_assessment"
        ]

    async def execute_task(
        self,
        task: AgentTask,
        session_id: str
    ) -> AgentResult:
        """Execute reasoning task with budget check"""

        start_time = datetime.now(timezone.utc)

        try:
            # Check budget before expensive reasoning
            if self.budget_exceeded(session_id):
                logger.warning("⚠️ Reasoning Agent budget exceeded - falling back to local")
                return await self._fallback_to_local_reasoning(task, session_id)

            logger.info(f"Reasoning Agent executing: {task.description}")

            # Create task definition
            task_def = TaskDefinition(
                task_id=task.task_id,
                name=f"Reasoning: {task.description}",
                description=task.description,
                complexity_estimate=8,  # High complexity for reasoning
                required_capabilities=task.required_capabilities + ["reasoning"],
                security_sensitive=task.metadata.get("security_sensitive", False),
                estimated_tokens_input=6000,
                estimated_tokens_output=3000
            )

            # Route with budget awareness
            router = get_hybrid_router()
            routing = await router.route_task(task_def, session_id)

            # Execute reasoning workflow
            output = await self._run_reasoning_workflow(task, routing)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Update cost tracking
            self._update_cost_profile(routing.estimated_cost_cents)

            # Record cost in budget tracker
            tracker = get_budget_tracker()
            await tracker.record_actual_cost(
                task_id=task.task_id,
                cost_cents=routing.estimated_cost_cents,
                session_id=session_id,
                model_id=routing.model_id,
                task_type="reasoning"
            )

            return AgentResult(
                agent_role=self.role,
                task_id=task.task_id,
                success=True,
                output=output,
                cost_cents=routing.estimated_cost_cents,
                execution_time_ms=execution_time,
                model_used=routing.model_id
            )

        except Exception as e:
            logger.error(f"Reasoning Agent error: {str(e)}")
            return AgentResult(
                agent_role=self.role,
                task_id=task.task_id,
                success=False,
                output={},
                error=str(e)
            )

    async def _fallback_to_local_reasoning(
        self,
        task: AgentTask,
        session_id: str
    ) -> AgentResult:
        """Fallback to local model when budget exceeded"""

        logger.info("Using local model for reasoning (budget exceeded)")

        # Simulated local reasoning (degraded quality)
        output = {
            "task": task.description,
            "model": "qwen2.5-coder:7b (local fallback)",
            "analysis": "Basic analysis using local model (budget constraints)",
            "confidence": "medium",
            "cost": "$0.00",
            "warning": "Budget exceeded - using local model with reduced capabilities"
        }

        return AgentResult(
            agent_role=self.role,
            task_id=task.task_id,
            success=True,
            output=output,
            cost_cents=0.0,
            model_used="qwen2.5-coder:7b"
        )

    async def _run_reasoning_workflow(
        self,
        task: AgentTask,
        routing: RoutingDecision
    ) -> Dict[str, Any]:
        """Run reasoning workflow with best model"""

        # Simulated reasoning results
        results = {
            "task": task.description,
            "model": routing.model_id,
            "analysis": {
                "reasoning_depth": "expert",
                "confidence_score": 0.95,
                "approach": "multi-step logical analysis",
                "conclusions": []
            },
            "cost": f"${routing.estimated_cost_cents/100:.4f}"
        }

        return results

    async def deep_analysis(
        self,
        finding: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform deep analysis on a finding"""

        task = AgentTask(
            task_id=f"reasoning_analysis_{finding.get('id', 'unknown')}",
            description=f"Deep analysis of finding: {finding.get('title', 'unknown')}",
            required_capabilities=["reasoning", "analysis"],
            metadata={"finding": finding, "context": context}
        )

        result = await self.execute_task(task, session_id="reasoning_autonomous")

        return result.output


class RepairAgent(AutonomousAgent):
    """
    Code repair specialist - uses Claude Code + Codex for fixes.
    Cost: Medium (uses paid APIs selectively)

    Tools: Claude Code CLI, Codex, static analyzers
    LLM: Claude Sonnet (balanced cost/quality)
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.REPAIR_SPECIALIST,
            llm_model="claude-3.5-sonnet",
            autonomy_level=2,
            budget_threshold_cents=300  # $3 max
        )

        self.tools = [
            "claude_code",
            "codex",
            "semgrep",
            "bandit",
            "eslint"
        ]

        # Initialize CLI clients
        from ..integrations.claude_code_client import get_claude_code_client
        from ..integrations.codex_client import get_codex_client

        self.claude_code = get_claude_code_client()
        self.codex = get_codex_client()

    async def execute_task(
        self,
        task: AgentTask,
        session_id: str
    ) -> AgentResult:
        """Execute repair task"""

        start_time = datetime.now(timezone.utc)

        try:
            logger.info(f"Repair Agent executing: {task.description}")

            # Route repair task
            task_def = TaskDefinition(
                task_id=task.task_id,
                name=f"Repair: {task.description}",
                description=task.description,
                complexity_estimate=7,  # High but not expert
                required_capabilities=task.required_capabilities + ["code_generation"],
                security_sensitive=True,
                estimated_tokens_input=4000,
                estimated_tokens_output=2000
            )

            router = get_hybrid_router()
            routing = await router.route_task(task_def, session_id)

            # Execute repair workflow
            output = await self._run_repair_workflow(task, routing)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Update cost
            self._update_cost_profile(routing.estimated_cost_cents)

            # Record cost
            tracker = get_budget_tracker()
            await tracker.record_actual_cost(
                task_id=task.task_id,
                cost_cents=routing.estimated_cost_cents,
                session_id=session_id,
                model_id=routing.model_id,
                task_type="repair"
            )

            return AgentResult(
                agent_role=self.role,
                task_id=task.task_id,
                success=True,
                output=output,
                cost_cents=routing.estimated_cost_cents,
                execution_time_ms=execution_time,
                model_used=routing.model_id
            )

        except Exception as e:
            logger.error(f"Repair Agent error: {str(e)}")
            return AgentResult(
                agent_role=self.role,
                task_id=task.task_id,
                success=False,
                output={},
                error=str(e)
            )

    async def _run_repair_workflow(
        self,
        task: AgentTask,
        routing: RoutingDecision
    ) -> Dict[str, Any]:
        """Run repair workflow using Claude Code + Codex"""

        vulnerability = task.metadata.get("vulnerability", {})
        code_context = task.metadata.get("code_context", {})

        # Step 1: Generate fix with Codex (if available)
        fix_generated = False
        if self.codex.available:
            logger.info("Generating fix with Codex...")
            # In production, would call actual Codex
            fix_generated = True

        # Step 2: Apply fix with Claude Code (if available and auto_apply)
        fix_applied = False
        auto_apply = task.metadata.get("auto_apply", True)

        if fix_generated and auto_apply and self.claude_code.available:
            logger.info("Applying fix with Claude Code...")
            # In production, would call actual Claude Code
            fix_applied = True

        results = {
            "task": task.description,
            "vulnerability": vulnerability,
            "fix_generated": fix_generated,
            "fix_applied": fix_applied,
            "model": routing.model_id,
            "cost": f"${routing.estimated_cost_cents/100:.4f}",
            "changes": {
                "files_modified": [],
                "security_improvements": []
            }
        }

        return results

    async def repair_vulnerability(
        self,
        vulnerability: Dict[str, Any],
        code_context: Dict[str, Any],
        auto_apply: bool = True
    ) -> Dict[str, Any]:
        """Repair a vulnerability"""

        task = AgentTask(
            task_id=f"repair_{vulnerability.get('id', 'unknown')}",
            description=f"Repair vulnerability: {vulnerability.get('type', 'unknown')}",
            required_capabilities=["code_generation", "security"],
            metadata={
                "vulnerability": vulnerability,
                "code_context": code_context,
                "auto_apply": auto_apply
            }
        )

        result = await self.execute_task(task, session_id="repair_autonomous")

        return result.output


# Global instances
_osint_agent: Optional[OSINTAgent] = None
_reasoning_agent: Optional[ReasoningAgent] = None
_repair_agent: Optional[RepairAgent] = None


def get_osint_agent() -> OSINTAgent:
    """Get global OSINT agent"""
    global _osint_agent
    if _osint_agent is None:
        _osint_agent = OSINTAgent()
    return _osint_agent


def get_reasoning_agent() -> ReasoningAgent:
    """Get global Reasoning agent"""
    global _reasoning_agent
    if _reasoning_agent is None:
        _reasoning_agent = ReasoningAgent()
    return _reasoning_agent


def get_repair_agent() -> RepairAgent:
    """Get global Repair agent"""
    global _repair_agent
    if _repair_agent is None:
        _repair_agent = RepairAgent()
    return _repair_agent
