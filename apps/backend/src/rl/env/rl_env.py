from __future__ import annotations
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from ..core.attack_surface_graph import AttackSurfaceGraph
from ..core.experience_engine import ExperienceEngine
from .optimization.reward_function import StrategicReward

logger = logging.getLogger(__name__)

class K1OffensiveEnv:
    """
    K1 Offensive Security RL Environment.
    Wraps the Attack Surface Graph (State) and Playbook Dispatch (Action).
    """

    def __init__(self, graph: AttackSurfaceGraph, engine: ExperienceEngine):
        self.graph = graph
        self.engine = engine
        self.rewarder = StrategicReward()
        self.replay_path = Path("artifacts/rl/replay_buffer.json")
        self.replay_path.parent.mkdir(parents=True, exist_ok=True)

    def get_state(self) -> Dict[str, Any]:
        """Returns the current state representation of the Attack Surface Graph."""
        nodes = self.graph._graph.nodes(data=True)
        return {
            "node_count": len(nodes),
            "critical_assets": len([n for n, d in nodes if d.get("severity") == "critical"]),
            "graph_summary": self.graph.get_node_context(root_node="root")
        }

    def step(self, action_data: Dict[str, Any], target_node: str) -> Tuple[Dict[str, Any], float, bool]:
        """
        Executes a step: Playbook + Mutation against a target node.
        Returns: (next_state, reward, done)
        """
        # Execute action (placeholder for actual tool dispatch)
        playbook_id = action_data.get("playbook_id")
        outcome = "Exploitation_Success" # Logic to be filled by tool runner
        
        # Calculate Reward
        reward = self.rewarder.calculate_reward(outcome, {})
        
        # Store in Replay Buffer
        self._record_to_buffer(self.get_state(), action_data, reward, outcome)
        
        return self.get_state(), reward, False

    def _record_to_buffer(self, state: Dict[str, Any], action: Dict[str, Any], reward: float, outcome: str):
        buffer = json.loads(self.replay_path.read_text()) if self.replay_path.exists() else {"steps": []}
        buffer["steps"].append({
            "state": state,
            "action": action,
            "reward": reward,
            "outcome": outcome,
            "timestamp": datetime.now(UTC).isoformat()
        })
        
        # Keep buffer to last 10,000
        if len(buffer["steps"]) > 10000:
            buffer["steps"] = buffer["steps"][-10000:]
            
        self.replay_path.write_text(json.dumps(buffer, indent=2))
