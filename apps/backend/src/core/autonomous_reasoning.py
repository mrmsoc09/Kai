"""
K1 Autonomous Reasoning Engine
Advanced goal decomposition, planning, and reasoning without human direction
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json


class ReasoningStrategy(str, Enum):
    """Different reasoning approaches agents can use"""
    CHAIN_OF_THOUGHT = "chain_of_thought"  # Step-by-step reasoning
    TREE_OF_THOUGHTS = "tree_of_thoughts"  # Explore multiple paths
    HIERARCHICAL = "hierarchical"  # Break into sub-goals
    ANALOGICAL = "analogical"  # Use past experiences
    CREATIVE = "creative"  # Novel combinations


@dataclass
class AutonomousGoal:
    """Autonomous goal with planning and decomposition"""
    goal_id: str
    description: str
    objective_type: str  # vulnerability_discovery, chain_analysis, etc.
    priority: int = 5  # 1-10
    deadline: Optional[datetime] = None
    parent_goal_id: Optional[str] = None
    sub_goals: List['AutonomousGoal'] = field(default_factory=list)
    required_resources: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, abandoned
    progress: float = 0.0  # 0-1
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class ReasoningTrace:
    """Trace of reasoning steps for transparency and learning"""
    trace_id: str
    initial_problem: str
    strategy_used: ReasoningStrategy
    steps: List[Dict[str, Any]] = field(default_factory=list)
    conclusion: Optional[str] = None
    confidence: float = 0.0
    reasoning_depth: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def add_step(self, step_num: int, content: str, reasoning: str, confidence: float):
        """Add a reasoning step"""
        self.steps.append({
            "step": step_num,
            "content": content,
            "reasoning": reasoning,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat()
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "strategy": self.strategy_used.value,
            "step_count": len(self.steps),
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "reasoning_depth": self.reasoning_depth
        }


class AutonomousReasoningEngine:
    """Engine for autonomous reasoning and problem-solving without human intervention"""

    def __init__(self, llm_complete_fn: Callable):
        self.llm_complete_fn = llm_complete_fn
        self.reasoning_traces: Dict[str, ReasoningTrace] = {}
        self.goal_hierarchy: Dict[str, AutonomousGoal] = {}
        self.learned_patterns: Dict[str, Dict] = {}  # problem_type -> solution_pattern

    async def autonomous_goal_setting(
        self,
        mission: str,
        agent_capabilities: List[str],
        environment: Dict[str, Any]
    ) -> List[AutonomousGoal]:
        """Autonomously set goals based on mission and capabilities"""

        prompt = f"""
        Given this mission: {mission}
        My capabilities: {agent_capabilities}
        Current environment: {json.dumps(environment)}

        Autonomously generate a set of goals to accomplish this mission.
        For each goal, provide:
        - description (clear goal statement)
        - objective_type (category)
        - priority (1-10)
        - required_resources (list)
        - success_criteria (list of measurable criteria)
        - sub_goals (if this is a complex goal, break it down)

        Format as JSON array of goals, arranged hierarchically.
        Focus on maximum impact with available resources.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You are an expert strategic planner. Set ambitious but achievable goals autonomously."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            goals_data = json.loads(text)

            # Convert to AutonomousGoal objects
            goals = []
            for goal_data in goals_data:
                goal = AutonomousGoal(
                    goal_id=goal_data.get("id", f"goal_{len(goals)}"),
                    description=goal_data.get("description"),
                    objective_type=goal_data.get("objective_type"),
                    priority=goal_data.get("priority", 5),
                    required_resources=goal_data.get("required_resources", []),
                    success_criteria=goal_data.get("success_criteria", [])
                )
                goals.append(goal)
                self.goal_hierarchy[goal.goal_id] = goal

            return goals

        except Exception as e:
            print(f"Goal setting error: {e}")
            return []

    async def decompose_complex_problem(
        self,
        problem: str,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """Autonomously decompose complex problem into sub-problems"""

        prompt = f"""
        Problem: {problem}

        Decompose this into sub-problems that can be solved independently.
        Create a hierarchical structure with:
        - Primary challenges
        - Secondary tasks
        - Dependencies between tasks
        - Resources needed for each

        Each sub-problem should be:
        - Specific and measurable
        - Solvable within context
        - Ideally independent of others

        Format as JSON with structure:
        {{
            "main_problem": "...",
            "sub_problems": [
                {{
                    "problem": "...",
                    "depends_on": [...],
                    "difficulty": "easy/medium/hard",
                    "resources_needed": [...]
                }}
            ],
            "solving_order": [...],
            "estimated_total_effort": "low/medium/high"
        }}
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You are expert at decomposing complex problems into manageable sub-tasks."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except:
            return {"main_problem": problem, "sub_problems": []}

    async def chain_of_thought_reasoning(
        self,
        problem: str,
        max_steps: int = 5,
        trace_id: Optional[str] = None
    ) -> Tuple[str, ReasoningTrace]:
        """Perform chain-of-thought reasoning for step-by-step problem solving"""

        trace = ReasoningTrace(
            trace_id=trace_id or f"trace_{datetime.utcnow().timestamp()}",
            initial_problem=problem,
            strategy_used=ReasoningStrategy.CHAIN_OF_THOUGHT
        )

        current_problem = problem
        step_num = 1

        while step_num <= max_steps and current_problem:
            # Think about current state
            prompt = f"""
            Current problem/state: {current_problem}

            What is the next logical step to solve or progress this?
            Provide:
            - Next step to take
            - Why this is the right step
            - Confidence (0-1)
            - What we'll know after this step

            Format as JSON.
            """

            response = await self.llm_complete_fn(
                messages=[{"role": "user", "content": prompt}],
                system="You are solving a complex problem step by step. Be logical and methodical."
            )

            try:
                text = response.text if hasattr(response, 'text') else str(response)
                step_data = json.loads(text)

                next_step = step_data.get("next_step")
                reasoning = step_data.get("reasoning")
                confidence = step_data.get("confidence", 0.5)

                trace.add_step(step_num, next_step, reasoning, confidence)
                trace.reasoning_depth = step_num

                # Prepare for next iteration
                current_problem = step_data.get("what_we_learn", "")
                step_num += 1

            except:
                break

        trace.confidence = sum(s["confidence"] for s in trace.steps) / len(trace.steps) if trace.steps else 0
        self.reasoning_traces[trace.trace_id] = trace

        return trace.conclusion or problem, trace

    async def tree_of_thoughts_reasoning(
        self,
        problem: str,
        num_branches: int = 3
    ) -> Dict[str, Any]:
        """Explore multiple reasoning paths simultaneously"""

        prompt = f"""
        Problem: {problem}

        Generate {num_branches} different approaches to solve this problem.
        For each approach:
        - Description of the approach
        - Steps involved
        - Potential obstacles
        - Expected success rate (0-1)
        - Resources required

        Then identify:
        - The most promising approach
        - Why it's most promising
        - Potential improvements

        Format as JSON.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You are exploring multiple solution paths. Be thorough and consider diverse approaches."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except:
            return {"approaches": [], "best_approach": None}

    async def autonomous_planning(
        self,
        goal: AutonomousGoal,
        available_resources: Dict[str, int],
        constraints: List[str]
    ) -> Dict[str, Any]:
        """Create autonomous execution plan for goal"""

        prompt = f"""
        Goal: {goal.description}
        Success criteria: {goal.success_criteria}
        Available resources: {json.dumps(available_resources)}
        Constraints: {constraints}
        Deadline: {goal.deadline}

        Create a detailed execution plan:
        - Phases of execution
        - Key milestones
        - Resource allocation per phase
        - Risk mitigation strategies
        - Contingency plans for common failures
        - Success metrics for each phase

        The plan should be autonomous (minimal human intervention required).

        Format as JSON.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You are an expert planner. Create detailed, autonomous execution plans."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except:
            return {"phases": [], "milestones": []}

    async def learn_from_failure(
        self,
        goal: AutonomousGoal,
        failure_reason: str,
        attempted_solution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Learn from failures and adapt approach autonomously"""

        prompt = f"""
        Goal that failed: {goal.description}
        Reason for failure: {failure_reason}
        Approach that was attempted: {json.dumps(attempted_solution)}

        Analyze:
        - Root cause of failure
        - What assumptions were wrong
        - Alternative approaches to try
        - How to prevent this failure in future
        - Updated understanding of the problem

        Format as JSON with fields:
        - root_cause
        - lessons_learned
        - new_approaches (list)
        - prevention_strategies
        - confidence_in_success (0-1)
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You are learning from failure. Be analytical and adaptable."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            learning = json.loads(text)

            # Store pattern
            self.learned_patterns[goal.objective_type] = learning

            return learning
        except:
            return {"root_cause": "unknown", "lessons_learned": []}

    async def prioritize_goals_dynamically(
        self,
        goals: List[AutonomousGoal],
        environment: Dict[str, Any]
    ) -> List[AutonomousGoal]:
        """Dynamically reprioritize goals based on changing environment"""

        prompt = f"""
        Current goals: {[{"id": g.goal_id, "desc": g.description, "priority": g.priority} for g in goals]}
        Current environment: {json.dumps(environment)}

        Reprioritize these goals based on:
        - Maximum impact on mission
        - Resource efficiency
        - Time constraints
        - Dependencies between goals
        - Changing environmental conditions

        Return as JSON array of goal IDs in priority order with explanations.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You prioritize goals dynamically based on changing conditions."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            priority_data = json.loads(text)

            # Reorder goals
            priority_order = priority_data.get("priority_order", [])
            goal_map = {g.goal_id: g for g in goals}

            reprioritized = [
                goal_map[goal_id]
                for goal_id in priority_order
                if goal_id in goal_map
            ]

            return reprioritized

        except:
            return goals

    async def handle_unexpected_situation(
        self,
        situation: Dict[str, Any],
        current_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle unexpected situations autonomously with plan adaptation"""

        prompt = f"""
        Unexpected situation: {json.dumps(situation)}
        Current execution plan: {json.dumps(current_plan)}

        How should we respond autonomously?
        - Is the current plan still valid?
        - What adjustments are needed?
        - What new opportunities or threats emerged?
        - Should we pivot strategy?

        Provide:
        - Assessment of situation
        - Recommended response
        - Plan adjustments
        - New priorities
        - Risk level (low/medium/high)

        Format as JSON.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You handle unexpected situations adaptively without waiting for human direction."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except:
            return {"assessment": "uncertain", "recommended_response": "proceed_cautiously"}

    def get_reasoning_profile(self) -> Dict[str, Any]:
        """Get profile of reasoning capabilities and history"""
        return {
            "total_reasoning_traces": len(self.reasoning_traces),
            "avg_reasoning_depth": sum(t.reasoning_depth for t in self.reasoning_traces.values()) / len(self.reasoning_traces) if self.reasoning_traces else 0,
            "avg_confidence": sum(t.confidence for t in self.reasoning_traces.values()) / len(self.reasoning_traces) if self.reasoning_traces else 0,
            "strategies_used": list(set(t.strategy_used for t in self.reasoning_traces.values())),
            "total_goals": len(self.goal_hierarchy),
            "active_goals": sum(1 for g in self.goal_hierarchy.values() if g.status == "in_progress"),
            "completed_goals": sum(1 for g in self.goal_hierarchy.values() if g.status == "completed"),
            "learned_patterns": len(self.learned_patterns),
            "recent_traces": [t.to_dict() for t in list(self.reasoning_traces.values())[-5:]]
        }


# Global instance
reasoning_engine = None


def initialize_reasoning_engine(llm_complete_fn: Callable) -> AutonomousReasoningEngine:
    """Initialize autonomous reasoning engine"""
    global reasoning_engine

    reasoning_engine = AutonomousReasoningEngine(llm_complete_fn)
    print("✓ Autonomous reasoning engine initialized")

    return reasoning_engine
