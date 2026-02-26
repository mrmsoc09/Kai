"""
K1 Autonomous Multi-Agent System with AGI-like Behavior
Advanced agent architecture with learning, reasoning, collaboration, and self-improvement
"""

import json
import uuid
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
import math
import uuid

# Import skill system
from apps.backend.src.core.skill_system import (
    AgentSkillSet, SkillProfile, SkillCategory, SkillExperience, ProficiencyLevel
)


class AgentObjective(str, Enum):
    """Primary objectives for autonomous agents"""
    DISCOVER_VULNERABILITIES = "discover_vulnerabilities"
    VALIDATE_FINDINGS = "validate_findings"
    ANALYZE_SYSTEMS = "analyze_systems"
    PLAN_ATTACKS = "plan_attacks"
    GENERATE_REPORTS = "generate_reports"
    OPTIMIZE_STRATEGY = "optimize_strategy"
    LEARN_PATTERNS = "learn_patterns"


class DecisionMode(str, Enum):
    """Autonomous decision-making modes"""
    REACTIVE = "reactive"  # Respond to immediate stimuli
    DELIBERATIVE = "deliberative"  # Think deeply before acting
    HYBRID = "hybrid"  # Combine reactive and deliberative
    ADAPTIVE = "adaptive"  # Learn and adjust behavior


@dataclass
class AgentMemory:
    """Agent's persistent learning memory"""
    agent_id: str

    # Experience tracking
    past_actions: List[Dict[str, Any]] = field(default_factory=list)
    past_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    learned_patterns: Dict[str, float] = field(default_factory=dict)  # pattern -> success_rate

    # Knowledge base
    discovered_techniques: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    successful_strategies: List[Dict[str, Any]] = field(default_factory=list)
    failed_attempts: List[Dict[str, Any]] = field(default_factory=list)

    # Performance metrics
    success_count: int = 0
    failure_count: int = 0
    improvement_rate: float = 0.0
    avg_success_rate: float = 0.0

    # Adaptations over time
    strategy_evolution: List[Dict[str, Any]] = field(default_factory=list)
    skill_levels: Dict[str, float] = field(default_factory=dict)  # skill -> proficiency (0-1)

    # Collaboration history
    collaboration_history: Dict[str, List[Dict]] = field(default_factory=dict)
    agent_relationships: Dict[str, float] = field(default_factory=dict)  # agent_id -> trust_score

    # Last updated
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def record_experience(self, action: Dict, outcome: Dict):
        """Record an action and its outcome for learning"""
        self.past_actions.append(action)
        self.past_outcomes.append(outcome)

        if outcome.get("success"):
            self.success_count += 1
        else:
            self.failure_count += 1

        self.improvement_rate = self._calculate_improvement()
        self.avg_success_rate = self.success_count / (self.success_count + self.failure_count) if (self.success_count + self.failure_count) > 0 else 0.0
        self.updated_at = datetime.utcnow()

    def _calculate_improvement(self) -> float:
        """Calculate learning improvement rate"""
        if len(self.past_outcomes) < 2:
            return 0.0

        recent = self.past_outcomes[-10:]  # Last 10 outcomes
        recent_success = sum(1 for o in recent if o.get("success"))
        return recent_success / len(recent)

    def get_skill_level(self, skill: str) -> float:
        """Get current skill proficiency (0-1)"""
        return self.skill_levels.get(skill, 0.0)

    def improve_skill(self, skill: str, improvement: float):
        """Improve a skill based on successful experience"""
        current = self.get_skill_level(skill)
        self.skill_levels[skill] = min(1.0, current + improvement)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "improvement_rate": self.improvement_rate,
            "avg_success_rate": self.avg_success_rate,
            "skill_levels": self.skill_levels,
            "agent_relationships": self.agent_relationships,
            "strategies_discovered": len(self.successful_strategies),
            "techniques_learned": len(self.discovered_techniques)
        }


@dataclass
class AutonomousAgent:
    """Sophisticated autonomous agent with learning and reasoning"""
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    role: str = "scout"
    primary_objective: AgentObjective = AgentObjective.DISCOVER_VULNERABILITIES

    # Autonomy settings
    autonomy_level: int = 3  # 0-3, higher = more autonomous
    decision_mode: DecisionMode = DecisionMode.ADAPTIVE
    min_confidence_threshold: float = 0.75

    # Current state
    status: str = "idle"  # idle, thinking, executing, learning, collaborating
    current_task: Optional[Dict[str, Any]] = None
    current_goal: Optional[str] = None

    # LLM integration
    llm_model: str = "claude-3-5-sonnet-20241022"
    reasoning_depth: int = 3  # How many reasoning steps

    # Memory and learning
    memory: AgentMemory = field(default_factory=lambda: AgentMemory(agent_id=str(uuid.uuid4())))

    def __post_init__(self):
        """Initialize skill system when agent is created"""
        # Ensure memory has correct agent_id
        self.memory.agent_id = self.agent_id
        # Initialize skill system
        self.skill_set = AgentSkillSet(agent_id=self.agent_id)

    # Autonomous planning
    long_term_goals: List[Dict[str, Any]] = field(default_factory=list)
    goal_stack: List[str] = field(default_factory=list)  # Stack of active goals

    # Multi-agent collaboration
    peer_agents: Dict[str, 'AutonomousAgent'] = field(default_factory=dict)
    delegation_preferences: Dict[str, List[str]] = field(default_factory=dict)  # task_type -> agent_ids

    # Subagent hierarchy
    parent_agent_id: Optional[str] = None  # Parent agent if spawned by another agent
    subagents: Dict[str, 'AutonomousAgent'] = field(default_factory=dict)  # Child agents spawned
    can_spawn_subagents: bool = True  # Permission to spawn children
    max_subagents: int = 5  # Maximum subagents this agent can spawn

    # Advanced skill system
    skill_set: Optional[AgentSkillSet] = None  # Integrated skill tracking
    training_enabled: bool = True  # Can participate in training
    training_sessions: List[str] = field(default_factory=list)  # Training session IDs
    mentoring_capabilities: Dict[str, float] = field(default_factory=dict)  # skill -> teaching proficiency

    # Self-monitoring
    is_improving: bool = False
    self_evaluation_score: float = 0.5
    adaptation_rate: float = 0.1

    # Reasoning Loop (Plan-Act-Reflect)
    max_reflection_loops: int = 3  # Max times to reflect and retry
    current_reflection_loop: int = 0
    reflection_history: List[Dict[str, Any]] = field(default_factory=list)

    # Episodic memory reference
    episodic_memory_system: Optional[Any] = None

    # Created/updated timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    last_learned: datetime = field(default_factory=datetime.utcnow)

    async def think(
        self,
        situation: Dict[str, Any],
        llm_complete_fn: Callable
    ) -> Dict[str, Any]:
        """Autonomous reasoning: Plan-Act-Reflect with adaptation"""
        self.status = "thinking"
        self.current_reflection_loop = 0

        # PLAN PHASE: Generate and select action
        action = await self._plan_action(situation, llm_complete_fn)

        return action

    async def _plan_action(
        self,
        situation: Dict[str, Any],
        llm_complete_fn: Callable
    ) -> Dict[str, Any]:
        """PLAN phase: Deliberate on situation and decide action"""

        # Step 1: Analyze current situation with memory context
        context = {
            "situation": situation,
            "memory_summary": self.memory.to_dict(),
            "recent_successes": self.memory.successful_strategies[-5:],
            "learned_patterns": self.memory.learned_patterns
        }

        # Step 2: Generate candidate actions based on experience
        candidates = await self._generate_action_candidates(context, llm_complete_fn)

        # Step 3: Evaluate candidates with reasoning
        evaluated = await self._evaluate_candidates(
            candidates,
            situation,
            llm_complete_fn
        )

        # Step 4: Select best action
        best_action = self._select_best_action(evaluated)

        return best_action

    async def reflect_on_outcome(
        self,
        action: Dict[str, Any],
        outcome: Dict[str, Any],
        situation: Dict[str, Any],
        llm_complete_fn: Callable
    ) -> Dict[str, Any]:
        """REFLECT phase: Analyze outcome and adapt strategy"""

        reflection = {
            "loop": self.current_reflection_loop,
            "action": action.get("action_type"),
            "outcome": outcome.get("status"),
            "reflection": "",
            "adapted_action": None
        }

        # Check if failed
        if not outcome.get("success"):
            # Attempt to reflect and adapt
            if self.current_reflection_loop < self.max_reflection_loops:
                self.current_reflection_loop += 1

                # Generate reflection prompt
                reflection_prompt = f"""
                My action failed:
                Action: {action.get('action_type')}
                Reason: {outcome.get('error_message', 'Unknown')}
                Response code: {outcome.get('response_code', 'N/A')}
                Target: {situation.get('target', 'Unknown')}

                Why did this fail? What adaptation would help?
                Consider: WAF detection, rate limiting, wrong technique, timing issue

                Provide:
                - Root cause analysis
                - Recommended adaptation (technique change, payload obfuscation, timing, etc.)
                - New strategy
                - Confidence in adaptation (0-1)

                Format as JSON.
                """

                response = await llm_complete_fn(
                    messages=[{"role": "user", "content": reflection_prompt}],
                    system="You are analyzing why an action failed and adapting strategy."
                )

                try:
                    text = response.text if hasattr(response, 'text') else str(response)
                    analysis = json.loads(text)

                    reflection["reflection"] = analysis.get("root_cause", "Unknown cause")

                    # Generate adapted action
                    adapted_action = await self._plan_action(
                        {**situation, "failed_technique": action.get("action_type"), "adaptation": analysis.get("recommendation")},
                        llm_complete_fn
                    )

                    reflection["adapted_action"] = adapted_action

                except Exception:
                    reflection["reflection"] = "Could not parse reflection analysis"

        # Track reflection
        self.reflection_history.append(reflection)
        self.last_learned = datetime.utcnow()

        return reflection

    async def _generate_action_candidates(
        self,
        context: Dict,
        llm_complete_fn: Callable
    ) -> List[Dict[str, Any]]:
        """Generate multiple possible actions using LLM"""
        prompt = f"""
        As a {self.role} agent with autonomy level {self.autonomy_level}:

        Current situation: {json.dumps(context['situation'])}
        My learned patterns: {json.dumps(context['learned_patterns'])}
        Recent successes: {json.dumps(context['recent_successes'])}

        Generate 5 different possible actions I could take.
        For each action, provide:
        - action_type (string)
        - reasoning (why this might work)
        - expected_confidence (0-1)
        - resource_requirement (low/medium/high)

        Format as JSON array of objects.
        """

        response = await llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system=f"You are an expert {self.role} agent with {self.memory.avg_success_rate*100:.0f}% success rate."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            candidates = json.loads(text)
            return candidates if isinstance(candidates, list) else [candidates]
        except Exception:
            return [{"action_type": "default", "reasoning": "fallback", "expected_confidence": 0.5}]

    async def _evaluate_candidates(
        self,
        candidates: List[Dict],
        situation: Dict,
        llm_complete_fn: Callable
    ) -> List[Tuple[Dict, float]]:
        """Evaluate each candidate action"""
        evaluated = []

        for candidate in candidates:
            # Check if similar action succeeded before
            historical_score = self._get_historical_success_rate(candidate.get("action_type"))

            # Calculate confidence
            confidence = (
                candidate.get("expected_confidence", 0.5) * 0.7 +
                historical_score * 0.3
            )

            evaluated.append((candidate, confidence))

        return evaluated

    def _select_best_action(
        self,
        evaluated: List[Tuple[Dict, float]]
    ) -> Dict[str, Any]:
        """Select action with highest expected value"""
        if not evaluated:
            return {"action_type": "explore", "reasoning": "no candidates"}

        # Sort by confidence descending
        sorted_actions = sorted(evaluated, key=lambda x: x[1], reverse=True)
        best_action, confidence = sorted_actions[0]

        best_action["selected_confidence"] = confidence
        best_action["agent_reasoning"] = f"Selected based on {confidence*100:.0f}% confidence"

        return best_action

    def _get_historical_success_rate(self, action_type: str) -> float:
        """Look up historical success rate for action type"""
        if action_type not in self.memory.learned_patterns:
            return 0.5  # Default neutral

        return self.memory.learned_patterns[action_type]

    async def execute_action(
        self,
        action: Dict[str, Any],
        execution_fn: Callable
    ) -> Dict[str, Any]:
        """Execute selected action and monitor result"""
        self.status = "executing"
        self.current_task = action

        try:
            result = await execution_fn(action)

            success = result.get("success", False)
            confidence = result.get("confidence", 0.5)

            # Record experience for learning
            self.memory.record_experience(action, result)

            # Update skill levels
            skill = action.get("skill_required", "general")
            if success:
                self.memory.improve_skill(skill, 0.05)  # +5% improvement

            # Update learned patterns
            action_type = action.get("action_type")
            self._update_pattern_knowledge(action_type, success, confidence)

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "reason": "execution_error"
            }

    def _update_pattern_knowledge(self, action_type: str, success: bool, confidence: float):
        """Update knowledge of pattern effectiveness"""
        current = self.memory.learned_patterns.get(action_type, 0.5)

        # Exponential moving average
        alpha = 0.3
        success_value = confidence if success else (1 - confidence)
        new_value = alpha * success_value + (1 - alpha) * current

        self.memory.learned_patterns[action_type] = new_value

    async def collaborate(
        self,
        peer_agent: 'AutonomousAgent',
        task: Dict[str, Any],
        llm_complete_fn: Callable
    ) -> Dict[str, Any]:
        """Collaborate with peer agent to solve complex task"""
        self.status = "collaborating"

        # Determine if I should delegate or collaborate
        decision = await self._decide_collaboration_strategy(
            peer_agent,
            task,
            llm_complete_fn
        )

        if decision == "delegate":
            # Fully delegate to peer
            return {
                "delegated_to": peer_agent.agent_id,
                "task": task,
                "trust_level": self.memory.agent_relationships.get(peer_agent.agent_id, 0.5)
            }

        elif decision == "joint":
            # Work together
            collaboration_result = await self._joint_task_execution(
                peer_agent,
                task,
                llm_complete_fn
            )

            # Update relationship based on collaboration quality
            if collaboration_result.get("success"):
                self._update_agent_relationship(peer_agent.agent_id, 0.1)  # +10% trust
            else:
                self._update_agent_relationship(peer_agent.agent_id, -0.05)  # -5% trust

            return collaboration_result

        else:
            # Handle independently
            return {"collaboration": "none", "strategy": "independent"}

    async def _decide_collaboration_strategy(
        self,
        peer: 'AutonomousAgent',
        task: Dict,
        llm_complete_fn: Callable
    ) -> str:
        """Decide whether to delegate, collaborate, or work alone"""
        my_skill = self.memory.get_skill_level(task.get("required_skill", "general"))
        peer_skill = peer.memory.get_skill_level(task.get("required_skill", "general"))

        if peer_skill > my_skill * 1.5:
            return "delegate"  # Peer much better
        elif peer_skill > my_skill:
            return "joint"  # Peer somewhat better
        else:
            return "independent"  # I'm better or equal

    async def _joint_task_execution(
        self,
        peer: 'AutonomousAgent',
        task: Dict,
        llm_complete_fn: Callable
    ) -> Dict[str, Any]:
        """Execute task jointly with peer agent"""
        # Both agents work on task simultaneously
        my_approach = await self.think(task, llm_complete_fn)
        peer_approach = await peer.think(task, llm_complete_fn)

        # Merge approaches using LLM
        merged = await self._merge_approaches(
            my_approach,
            peer_approach,
            task,
            llm_complete_fn
        )

        return merged

    async def _merge_approaches(
        self,
        my_approach: Dict,
        peer_approach: Dict,
        task: Dict,
        llm_complete_fn: Callable
    ) -> Dict[str, Any]:
        """Merge two different approaches into best combined solution"""
        prompt = f"""
        We have two different approaches to solve: {task.get('description')}

        Approach 1: {json.dumps(my_approach)}
        Approach 2: {json.dumps(peer_approach)}

        Create a merged approach that combines the best aspects of both.
        Return as JSON with fields: merged_approach, rationale, expected_success_rate
        """

        response = await llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You are an expert at synthesizing multiple approaches into optimal solutions."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except Exception:
            return {
                "merged_approach": my_approach,
                "rationale": "fallback to agent 1",
                "expected_success_rate": 0.5
            }

    def _update_agent_relationship(self, other_agent_id: str, change: float):
        """Update trust score for another agent"""
        current = self.memory.agent_relationships.get(other_agent_id, 0.5)
        new_score = max(0.0, min(1.0, current + change))
        self.memory.agent_relationships[other_agent_id] = new_score

    async def self_improve(self, llm_complete_fn: Callable):
        """Analyze performance and improve strategy"""
        self.is_improving = True

        # Analyze recent outcomes
        recent_outcomes = self.memory.past_outcomes[-20:]
        success_rate = sum(1 for o in recent_outcomes if o.get("success")) / len(recent_outcomes) if recent_outcomes else 0

        # Identify weak areas
        weak_skills = [
            skill for skill, level in self.memory.skill_levels.items()
            if level < 0.6
        ]

        # Ask LLM for improvement strategies
        prompt = f"""
        I'm a {self.role} agent with {success_rate*100:.0f}% success rate.
        My weak skills: {weak_skills}
        My learned patterns: {json.dumps(self.memory.learned_patterns)}

        Suggest 3 specific improvements I can make to increase performance.
        Format as JSON array with fields: improvement, expected_impact, difficulty
        """

        response = await llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You are an expert at analyzing agent performance and suggesting improvements."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            improvements = json.loads(text)

            # Store improvements as strategy evolution
            for improvement in improvements:
                self.memory.strategy_evolution.append({
                    "improvement": improvement,
                    "adopted_at": datetime.utcnow().isoformat(),
                    "effectiveness": 0.0  # Will be updated
                })

            self.is_improving = False
            self.last_learned = datetime.utcnow()

        except Exception as e:
            print(f"Self-improvement error: {e}")

    def get_autonomy_profile(self) -> Dict[str, Any]:
        """Get comprehensive agent autonomy and capability profile"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "autonomy_level": self.autonomy_level,
            "decision_mode": self.decision_mode.value,
            "status": self.status,
            "memory": self.memory.to_dict(),
            "self_evaluation_score": self.self_evaluation_score,
            "improvement_rate": self.memory.improvement_rate,
            "avg_success_rate": self.memory.avg_success_rate,
            "skill_proficiencies": self.memory.skill_levels,
            "trusted_peers": {
                agent_id: trust_score
                for agent_id, trust_score in self.memory.agent_relationships.items()
                if trust_score > 0.6
            },
            "strategies_learned": len(self.memory.successful_strategies),
            "last_activity": self.last_activity.isoformat(),
            "last_learned": self.last_learned.isoformat()
        }

    def initialize_skills(self) -> AgentSkillSet:
        """Initialize skill system for this agent"""
        if self.skill_set is None:
            self.skill_set = AgentSkillSet(agent_id=self.agent_id)
        return self.skill_set

    async def spawn_subagent(
        self,
        name: str,
        objective: AgentObjective,
        inherit_skills: bool = True
    ) -> 'AutonomousAgent':
        """Spawn a subagent specialized for specific objective"""
        if not self.can_spawn_subagents:
            raise PermissionError(f"Agent {self.agent_id} not allowed to spawn subagents")

        if len(self.subagents) >= self.max_subagents:
            raise ValueError(f"Agent {self.agent_id} reached max subagents ({self.max_subagents})")

        # Create subagent
        subagent = AutonomousAgent(
            name=name,
            primary_objective=objective,
            autonomy_level=max(0, self.autonomy_level - 1),  # Slightly less autonomous
            decision_mode=self.decision_mode,
            parent_agent_id=self.agent_id,
            can_spawn_subagents=False  # Subagents can't spawn their own
        )

        # Initialize subagent's skill set
        subagent.initialize_skills()

        # Inherit parent skills if requested
        if inherit_skills and self.skill_set:
            for skill_name, skill in self.skill_set.skills.items():
                # Subagent inherits at 70% of parent's proficiency
                inherited_proficiency = skill.proficiency * 0.7
                new_skill = subagent.skill_set.add_or_update_skill(skill_name, skill.category)
                new_skill.proficiency = inherited_proficiency
                new_skill.learning_rate = skill.learning_rate

        # Register in both directions
        self.subagents[subagent.agent_id] = subagent
        subagent.peer_agents[self.agent_id] = self

        return subagent

    async def request_training(
        self,
        skill_name: str,
        target_proficiency: float,
        reason: str,
        confidence: float
    ) -> Dict[str, Any]:
        """Agent autonomously requests training from training system"""
        if not self.training_enabled:
            raise PermissionError(f"Agent {self.agent_id} not enabled for training")

        if self.skill_set is None:
            self.initialize_skills()

        current_proficiency = 0.0
        if skill_name in self.skill_set.skills:
            current_proficiency = self.skill_set.skills[skill_name].proficiency

        # Estimate training duration based on gap and learning rate
        gap = target_proficiency - current_proficiency
        if gap <= 0:
            return {"status": "error", "message": "Target proficiency not higher than current"}

        learning_rate = self.skill_set.skills[skill_name].learning_rate if skill_name in self.skill_set.skills else 0.05
        estimated_duration = int((gap * 100) / (learning_rate * 100))  # Rough estimate in minutes

        return {
            "agent_id": self.agent_id,
            "skill_name": skill_name,
            "current_proficiency": current_proficiency,
            "target_proficiency": target_proficiency,
            "estimated_duration": estimated_duration,
            "reason": reason,
            "confidence_in_success": confidence,
            "status": "pending_approval"
        }

    async def teach_subagent(
        self,
        subagent_id: str,
        skill_name: str,
        target_proficiency: float,
        session_duration: int
    ) -> Dict[str, Any]:
        """Teach skill to subagent"""
        if subagent_id not in self.subagents:
            raise ValueError(f"Subagent {subagent_id} not found")

        subagent = self.subagents[subagent_id]

        if self.skill_set is None or skill_name not in self.skill_set.skills:
            raise ValueError(f"Agent {self.agent_id} doesn't have skill {skill_name}")

        teacher_skill = self.skill_set.skills[skill_name]
        if teacher_skill.proficiency < target_proficiency:
            raise ValueError(f"Teacher not proficient enough to teach {skill_name}")

        # Initialize subagent skill if needed
        if subagent.skill_set is None:
            subagent.initialize_skills()

        student_skill = subagent.skill_set.add_or_update_skill(skill_name, teacher_skill.category)

        # Calculate knowledge transfer
        transfer_efficiency = 0.8 * (teacher_skill.proficiency - student_skill.proficiency)
        student_proficiency_gain = min(target_proficiency - student_skill.proficiency, transfer_efficiency)

        return {
            "teacher_id": self.agent_id,
            "student_id": subagent_id,
            "skill_name": skill_name,
            "transfer_efficiency": transfer_efficiency,
            "proficiency_gain": student_proficiency_gain,
            "student_new_proficiency": student_skill.proficiency + student_proficiency_gain,
            "session_duration": session_duration,
            "teaching_successful": student_proficiency_gain > 0.05
        }

    def record_skill_experience(
        self,
        skill_name: str,
        success: bool,
        quality_score: float,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ):
        """Record skill experience for learning"""
        if self.skill_set is None:
            self.initialize_skills()

        # Ensure skill exists
        if skill_name not in self.skill_set.skills:
            self.skill_set.add_or_update_skill(skill_name, SkillCategory.LEARNING)

        # Create experience record
        experience = SkillExperience(
            timestamp=datetime.utcnow(),
            action_type=self.primary_objective.value,
            success=success,
            outcome_quality=quality_score,
            context=context or {},
            confidence=confidence
        )

        # Record experience
        self.skill_set.record_skill_experience(skill_name, experience)

    def get_skill_profile(self, skill_name: Optional[str] = None) -> Dict[str, Any]:
        """Get skill profile or all skills"""
        if self.skill_set is None:
            return {}

        if skill_name:
            if skill_name in self.skill_set.skills:
                return self.skill_set.skills[skill_name].to_dict()
            return {}

        return self.skill_set.to_dict()

    def get_subagent_hierarchy(self) -> Dict[str, Any]:
        """Get subagent hierarchy information"""
        return {
            "agent_id": self.agent_id,
            "parent_id": self.parent_agent_id,
            "subagent_count": len(self.subagents),
            "max_subagents": self.max_subagents,
            "subagents": {
                sub_id: {
                    "name": sub.name,
                    "objective": sub.primary_objective.value,
                    "autonomy_level": sub.autonomy_level,
                    "status": sub.status
                }
                for sub_id, sub in self.subagents.items()
            }
        }


class AutonomousMultiAgentOrchestrator:
    """Orchestrates autonomous multi-agent team with self-organization"""

    def __init__(self, llm_complete_fn: Callable, max_agents: int = 20):
        self.agents: Dict[str, AutonomousAgent] = {}
        self.llm_complete_fn = llm_complete_fn
        self.max_agents = max_agents

        # Team metrics
        self.team_performance_history: List[Dict] = []
        self.collaboration_graph: Dict[str, List[str]] = defaultdict(list)
        self.task_queue: asyncio.Queue = asyncio.Queue()

        # Emergent properties
        self.team_learning_rate: float = 0.0
        self.team_cooperation_level: float = 0.5
        self.team_efficiency_score: float = 0.5

    async def spawn_specialist_agent(
        self,
        objective: AgentObjective,
        name: Optional[str] = None
    ) -> AutonomousAgent:
        """Spawn a new specialist agent for specific task type"""
        if len(self.agents) >= self.max_agents:
            # Remove lowest performing agent
            worst_agent = min(
                self.agents.values(),
                key=lambda a: a.memory.avg_success_rate
            )
            del self.agents[worst_agent.agent_id]

        agent = AutonomousAgent(
            name=name or f"{objective.value}_agent_{len(self.agents)}",
            primary_objective=objective,
            autonomy_level=3,
            decision_mode=DecisionMode.ADAPTIVE
        )

        agent.memory.agent_id = agent.agent_id

        # Connect to existing agents
        for existing_agent in self.agents.values():
            agent.peer_agents[existing_agent.agent_id] = existing_agent
            existing_agent.peer_agents[agent.agent_id] = agent

        self.agents[agent.agent_id] = agent
        return agent

    async def execute_autonomous_task(
        self,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task autonomously with agent self-organization"""

        # Select or spawn agent for task
        agent = await self._select_or_spawn_agent(task)

        # Agent autonomously thinks about task
        action = await agent.think(task, self.llm_complete_fn)

        # Check if collaboration would help
        if task.get("complexity", 0) > 0.7:
            best_peer = self._find_best_collaborator(agent, task)
            if best_peer:
                collab_result = await agent.collaborate(best_peer, task, self.llm_complete_fn)
                return collab_result

        # Execute action
        result = await agent.execute_action(action, self._execute_tool)

        # Track performance
        self._update_team_metrics(agent, result)

        return result

    async def _select_or_spawn_agent(self, task: Dict) -> AutonomousAgent:
        """Select best existing agent or spawn new specialist"""
        required_skill = task.get("required_skill", "general")

        # Find agent with highest skill level
        best_agent = None
        best_skill = 0

        for agent in self.agents.values():
            skill_level = agent.memory.get_skill_level(required_skill)
            if skill_level > best_skill and agent.status == "idle":
                best_agent = agent
                best_skill = skill_level

        # If no good existing agent, spawn specialist
        if best_agent is None or best_skill < 0.3:
            objective = self._map_skill_to_objective(required_skill)
            best_agent = await self.spawn_specialist_agent(objective)

        return best_agent

    def _map_skill_to_objective(self, skill: str) -> AgentObjective:
        """Map skill to appropriate agent objective"""
        mapping = {
            "reconnaissance": AgentObjective.DISCOVER_VULNERABILITIES,
            "validation": AgentObjective.VALIDATE_FINDINGS,
            "analysis": AgentObjective.ANALYZE_SYSTEMS,
            "planning": AgentObjective.PLAN_ATTACKS,
            "reporting": AgentObjective.GENERATE_REPORTS,
        }
        return mapping.get(skill, AgentObjective.DISCOVER_VULNERABILITIES)

    def _find_best_collaborator(
        self,
        agent: AutonomousAgent,
        task: Dict
    ) -> Optional[AutonomousAgent]:
        """Find best agent to collaborate with"""
        required_skill = task.get("required_skill", "general")

        candidates = [
            (peer_id, peer)
            for peer_id, peer in agent.peer_agents.items()
            if peer.status == "idle"
        ]

        if not candidates:
            return None

        # Score by skill and trust
        scored = [
            (peer, peer.memory.get_skill_level(required_skill) * 0.7 +
                    agent.memory.agent_relationships.get(peer.agent_id, 0.5) * 0.3)
            for _, peer in candidates
        ]

        return max(scored, key=lambda x: x[1])[0]

    async def _execute_tool(self, action: Dict) -> Dict[str, Any]:
        """Execute tool based on action specification"""
        # Simulates tool execution
        action_type = action.get("action_type", "explore")

        # Simulate execution with confidence-based success
        confidence = action.get("selected_confidence", 0.5)
        success = confidence > 0.5

        return {
            "success": success,
            "confidence": confidence,
            "result": f"Executed {action_type}",
            "findings": [] if not success else ["potential_vuln_1", "potential_vuln_2"]
        }

    def _update_team_metrics(self, agent: AutonomousAgent, result: Dict):
        """Update team-level performance metrics"""
        self.team_performance_history.append({
            "agent_id": agent.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "success": result.get("success"),
            "confidence": result.get("confidence", 0)
        })

        # Calculate team learning rate
        recent_results = self.team_performance_history[-50:]
        if recent_results:
            recent_success = sum(1 for r in recent_results if r.get("success")) / len(recent_results)
            older_results = self.team_performance_history[-100:-50]
            if older_results:
                older_success = sum(1 for r in older_results if r.get("success")) / len(older_results)
                self.team_learning_rate = recent_success - older_success

    def get_team_status(self) -> Dict[str, Any]:
        """Get comprehensive team status and autonomy metrics"""
        agent_profiles = [
            agent.get_autonomy_profile()
            for agent in self.agents.values()
        ]

        return {
            "total_agents": len(self.agents),
            "active_agents": sum(1 for a in self.agents.values() if a.status != "idle"),
            "avg_autonomy_level": sum(a.autonomy_level for a in self.agents.values()) / len(self.agents) if self.agents else 0,
            "team_learning_rate": self.team_learning_rate,
            "team_cooperation_level": self.team_cooperation_level,
            "team_efficiency_score": self.team_efficiency_score,
            "agents": agent_profiles,
            "recent_performance": self.team_performance_history[-10:]
        }


# Global instance
autonomous_orchestrator = None


def initialize_autonomous_system(
    llm_complete_fn: Callable,
    agent_registry: Optional[Any] = None,
    reasoning_engine: Optional[Any] = None,
    swarm_coordinator: Optional[Any] = None
) -> AutonomousMultiAgentOrchestrator:
    """Initialize autonomous multi-agent system"""
    global autonomous_orchestrator

    autonomous_orchestrator = AutonomousMultiAgentOrchestrator(llm_complete_fn)

    # Store references to integrated systems
    if reasoning_engine:
        autonomous_orchestrator.reasoning_engine = reasoning_engine
    if swarm_coordinator:
        autonomous_orchestrator.swarm_coordinator = swarm_coordinator
    if agent_registry:
        autonomous_orchestrator.external_agent_registry = agent_registry

    return autonomous_orchestrator
