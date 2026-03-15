"""
K1 Swarm Coordination System
Multi-agent collaboration, emergence, and self-organization
"""

from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import json
import asyncio
from collections import defaultdict


class CollaborationPattern(str, Enum):
    """Patterns of multi-agent collaboration"""
    HIERARCHICAL = "hierarchical"  # Top-down coordination
    DEMOCRATIC = "democratic"  # Consensus-based
    SWARM = "swarm"  # Decentralized, emergent
    COMPETITIVE = "competitive"  # Agents compete
    COOPERATIVE = "cooperative"  # Agents help each other
    HYBRID = "hybrid"  # Mix of patterns


@dataclass
class AgentSignal:
    """Signal sent between agents for coordination"""
    signal_id: str
    sender_id: str
    signal_type: str  # "discovery", "request_help", "warning", "success", "failure"
    content: Dict[str, Any]
    priority: int = 5  # 1-10
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl: int = 60  # Seconds


@dataclass
class EmergentProperty:
    """Emergent property of the agent swarm"""
    name: str
    description: str
    value: float  # 0-1
    measurement_method: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SwarmCoordinator:
    """Coordinates multi-agent swarm with emergent behaviors"""

    def __init__(self, llm_complete_fn: Callable):
        self.llm_complete_fn = llm_complete_fn
        self.agents: Dict[str, Any] = {}  # agent_id -> agent

        # Signal bus for inter-agent communication
        self.signal_bus: Dict[str, List[AgentSignal]] = defaultdict(list)

        # Collaboration patterns
        self.active_pattern: CollaborationPattern = CollaborationPattern.HYBRID
        self.pattern_history: List[Dict] = []

        # Emergent properties
        self.emergent_properties: Dict[str, EmergentProperty] = {}
        self.swarm_intelligence_level: float = 0.5
        self.collective_efficiency: float = 0.5

        # Task coordination
        self.shared_knowledge_base: Dict[str, Dict] = {}
        self.collective_goals: List[Dict] = []
        self.task_dependencies: Dict[str, List[str]] = defaultdict(list)

        # Performance metrics
        self.collective_learning_rate: float = 0.0
        self.emergence_indicators: List[Dict] = []

    def register_agents(self, agents: List[Any]):
        """Register agents in swarm"""
        for agent in agents:
            self.agents[agent.agent_id] = agent

    def broadcast_signal(self, signal: AgentSignal):
        """Broadcast signal from one agent to others"""
        # Add signal to all agent channels except sender
        for agent_id in self.agents:
            if agent_id != signal.sender_id:
                self.signal_bus[agent_id].append(signal)

    def get_signals_for_agent(self, agent_id: str) -> List[AgentSignal]:
        """Get all pending signals for agent"""
        signals = self.signal_bus[agent_id]
        self.signal_bus[agent_id] = []  # Clear after retrieval
        return signals

    async def select_collaboration_pattern(
        self,
        task_complexity: float,
        time_constraint: float,
        agent_diversity: float
    ) -> CollaborationPattern:
        """Select best collaboration pattern for task"""

        prompt = f"""
        Task characteristics:
        - Complexity: {task_complexity} (0-1)
        - Time constraint: {time_constraint} (0-1, higher = less time)
        - Agent diversity: {agent_diversity} (0-1, how different are agent capabilities)

        Available patterns:
        - HIERARCHICAL: Single agent decides, others execute (fast, less flexible)
        - DEMOCRATIC: All agents vote (slow, best consensus)
        - SWARM: Decentralized, emergent (flexible, unpredictable)
        - COOPERATIVE: Agents help each other (balanced)

        Which pattern is best for this task?
        Provide: recommended_pattern, reasoning, expected_efficiency (0-1)

        Format as JSON.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You select optimal collaboration patterns for multi-agent systems."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            data = json.loads(text)
            pattern_name = data.get("recommended_pattern", "HYBRID")
            pattern = CollaborationPattern[pattern_name]
            self.active_pattern = pattern
            return pattern
        except Exception:
            return CollaborationPattern.HYBRID

    async def coordinate_swarm_task(
        self,
        task: Dict[str, Any],
        agents: List[Any]
    ) -> Dict[str, Any]:
        """Coordinate agents in swarm to accomplish task"""

        # Phase 1: Signal task to all agents
        task_signal = AgentSignal(
            signal_id=f"task_{task.get('id')}",
            sender_id="orchestrator",
            signal_type="task",
            content=task,
            priority=10
        )

        for agent in agents:
            self.signal_bus[agent.agent_id].append(task_signal)

        # Phase 2: Allow agents to respond autonomously based on pattern
        if self.active_pattern == CollaborationPattern.SWARM:
            result = await self._swarm_execution(agents, task)
        elif self.active_pattern == CollaborationPattern.DEMOCRATIC:
            result = await self._democratic_execution(agents, task)
        elif self.active_pattern == CollaborationPattern.HIERARCHICAL:
            result = await self._hierarchical_execution(agents, task)
        elif self.active_pattern == CollaborationPattern.COOPERATIVE:
            result = await self._cooperative_execution(agents, task)
        else:
            result = await self._swarm_execution(agents, task)

        return result

    async def _swarm_execution(
        self,
        agents: List[Any],
        task: Dict
    ) -> Dict[str, Any]:
        """Decentralized swarm execution with emergence"""

        # All agents work simultaneously on task
        # Each makes local decisions based on signals and memory
        individual_results = []

        for agent in agents:
            # Agent gets signals from others
            signals = self.get_signals_for_agent(agent.agent_id)

            # Agent processes signals and makes autonomous decision
            local_decision = await agent.think(task, self.llm_complete_fn)

            # Agent executes
            result = await agent.execute_action(local_decision, lambda x: self._execute(x))

            individual_results.append({
                "agent_id": agent.agent_id,
                "result": result,
                "decision": local_decision
            })

            # Agent broadcasts its findings
            if result.get("success"):
                signal = AgentSignal(
                    signal_id=f"finding_{task.get('id')}_{agent.agent_id}",
                    sender_id=agent.agent_id,
                    signal_type="discovery",
                    content=result,
                    priority=result.get("confidence", 0.5) * 10
                )
                self.broadcast_signal(signal)

        # Merge results from all agents
        merged_result = await self._merge_swarm_results(individual_results)

        # Detect emergent properties
        await self._detect_emergent_properties(agents)

        return merged_result

    async def _democratic_execution(
        self,
        agents: List[Any],
        task: Dict
    ) -> Dict[str, Any]:
        """Democratic consensus-based execution"""

        # All agents propose solutions
        proposals = []

        for agent in agents:
            proposal = await agent.think(task, self.llm_complete_fn)
            proposals.append({
                "agent_id": agent.agent_id,
                "proposal": proposal,
                "confidence": proposal.get("selected_confidence", 0.5)
            })

        # Use LLM to find consensus
        prompt = f"""
        Task: {json.dumps(task)}
        Proposals from {len(proposals)} agents:
        {json.dumps(proposals)}

        Find the best consensus solution that incorporates insights from multiple proposals.
        Provide: consensus_approach, rationale, expected_success_rate

        Format as JSON.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You synthesize multiple agent proposals into consensus solutions."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            return json.loads(text)
        except Exception:
            return {"consensus_approach": proposals[0]["proposal"], "rationale": "first proposal"}

    async def _hierarchical_execution(
        self,
        agents: List[Any],
        task: Dict
    ) -> Dict[str, Any]:
        """Hierarchical command-based execution"""

        # Find lead agent (highest skill)
        lead_agent = max(agents, key=lambda a: a.memory.avg_success_rate)

        # Lead decides approach
        approach = await lead_agent.think(task, self.llm_complete_fn)

        # Signal decision to others
        decision_signal = AgentSignal(
            signal_id=f"decision_{task.get('id')}",
            sender_id=lead_agent.agent_id,
            signal_type="command",
            content={"approach": approach, "from_lead": True},
            priority=10
        )

        for agent in agents:
            if agent.agent_id != lead_agent.agent_id:
                self.signal_bus[agent.agent_id].append(decision_signal)

        # Others execute the lead's plan
        result = await lead_agent.execute_action(approach, lambda x: self._execute(x))

        return {
            "lead_agent": lead_agent.agent_id,
            "approach": approach,
            "result": result
        }

    async def _cooperative_execution(
        self,
        agents: List[Any],
        task: Dict
    ) -> Dict[str, Any]:
        """Cooperative execution with mutual support"""

        # Agents form pairs/teams and coordinate
        results = []

        # Pair agents based on complementary skills
        pairs = self._form_cooperative_pairs(agents, task)

        for pair in pairs:
            agent1, agent2 = pair

            # Collaborate
            collab_result = await agent1.collaborate(agent2, task, self.llm_complete_fn)
            results.append(collab_result)

        # Merge cooperative results
        merged = await self._merge_swarm_results(
            [{"agent_id": r.get("agents"), "result": r} for r in results]
        )

        return merged

    def _form_cooperative_pairs(
        self,
        agents: List[Any],
        task: Dict
    ) -> List[tuple]:
        """Form agent pairs based on complementary capabilities"""
        pairs = []

        # Simple pairing strategy: sort by skill and pair high with low
        skill_level = task.get("required_skill", "general")
        sorted_agents = sorted(
            agents,
            key=lambda a: a.memory.get_skill_level(skill_level)
        )

        for i in range(0, len(sorted_agents) - 1, 2):
            pairs.append((sorted_agents[i], sorted_agents[i+1]))

        if len(sorted_agents) % 2 == 1:
            # Odd agent out teams with strongest
            pairs.append((sorted_agents[-1], sorted_agents[-2]))

        return pairs

    async def _merge_swarm_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Merge results from multiple agents"""
        if not results:
            return {"merged": False}

        # Aggregate findings
        all_findings = []
        for r in results:
            if "findings" in r.get("result", {}):
                all_findings.extend(r["result"]["findings"])

        # Deduplicate
        unique_findings = list(set(all_findings))

        # Success if any agent succeeded
        overall_success = any(r.get("result", {}).get("success") for r in results)

        return {
            "merged_success": overall_success,
            "contributors": len(results),
            "unique_findings": unique_findings,
            "finding_count": len(unique_findings)
        }

    async def _detect_emergent_properties(self, agents: List[Any]):
        """Detect emergent properties of the swarm"""

        # Calculate swarm-level metrics
        avg_success = sum(a.memory.avg_success_rate for a in agents) / len(agents) if agents else 0
        specialization = self._calculate_specialization(agents)
        cooperation_level = self._calculate_cooperation_level(agents)

        # Detect emergence
        prompt = f"""
        Swarm metrics:
        - Average agent success rate: {avg_success}
        - Specialization level: {specialization} (0-1)
        - Cooperation level: {cooperation_level} (0-1)
        - Swarm size: {len(agents)}

        What emergent properties are developing?
        Consider: collective intelligence, problem-solving ability, resilience, adaptability

        Provide: emergent_properties (list), swarm_intelligence_level (0-1), indicators

        Format as JSON.
        """

        response = await self.llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system="You detect emergent properties in agent swarms."
        )

        try:
            text = response.text if hasattr(response, 'text') else str(response)
            data = json.loads(text)

            self.swarm_intelligence_level = data.get("swarm_intelligence_level", 0.5)
            self.emergence_indicators.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "properties": data.get("emergent_properties", []),
                "intelligence": self.swarm_intelligence_level
            })

        except Exception as e:
            print(f"Emergence detection error: {e}")

    def _calculate_specialization(self, agents: List[Any]) -> float:
        """Calculate how specialized agents are"""
        if not agents or len(agents) < 2:
            return 0.0

        # Look at skill distribution
        all_skills = {}
        for agent in agents:
            for skill, level in agent.memory.skill_levels.items():
                if skill not in all_skills:
                    all_skills[skill] = []
                all_skills[skill].append(level)

        # High specialization = uneven distribution
        if not all_skills:
            return 0.0

        variance_sum = 0
        for skill_levels in all_skills.values():
            if len(skill_levels) > 1:
                avg = sum(skill_levels) / len(skill_levels)
                variance = sum((x - avg) ** 2 for x in skill_levels) / len(skill_levels)
                variance_sum += variance

        return min(1.0, variance_sum / len(all_skills))

    def _calculate_cooperation_level(self, agents: List[Any]) -> float:
        """Calculate cooperation between agents"""
        if not agents:
            return 0.0

        total_relationships = 0
        positive_relationships = 0

        for agent in agents:
            total_relationships += len(agent.memory.agent_relationships)
            positive_relationships += sum(
                1 for score in agent.memory.agent_relationships.values()
                if score > 0.6
            )

        if total_relationships == 0:
            return 0.0

        return positive_relationships / total_relationships

    async def _execute(self, action: Dict) -> Dict[str, Any]:
        """Execute action (simulated)"""
        return {
            "success": action.get("selected_confidence", 0.5) > 0.5,
            "confidence": action.get("selected_confidence", 0.5),
            "findings": []
        }

    def get_swarm_status(self) -> Dict[str, Any]:
        """Get comprehensive swarm status"""
        return {
            "agent_count": len(self.agents),
            "active_pattern": self.active_pattern.value,
            "swarm_intelligence": self.swarm_intelligence_level,
            "collective_efficiency": self.collective_efficiency,
            "collective_learning_rate": self.collective_learning_rate,
            "emergent_properties": list(self.emergent_properties.keys()),
            "emergence_indicators": self.emergence_indicators[-10:],
            "shared_knowledge_size": len(self.shared_knowledge_base),
            "collective_goals": len(self.collective_goals)
        }


# Global instance
swarm_coordinator = None


def initialize_swarm_coordinator(llm_complete_fn: Callable) -> SwarmCoordinator:
    """Initialize swarm coordination system"""
    global swarm_coordinator

    swarm_coordinator = SwarmCoordinator(llm_complete_fn)
    print("✓ Swarm coordination system initialized")

    return swarm_coordinator
