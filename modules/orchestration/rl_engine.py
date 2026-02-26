from __future__ import annotations
from typing import Dict, Any

class RLEngine:
    def __init__(self):
        self.weights: Dict[str, float] = {}

    def update(self, feedback: Dict[str, Any]) -> Dict[str, float]:
        tactic = feedback.get('tactic')
        delta = feedback.get('delta', 0.1 if feedback.get('positive') else -0.05)
        if tactic:
            self.weights[tactic] = self.weights.get(tactic, 0.0) + delta
        return self.weights

    def suggest_bias(self, tactic: str) -> float:
        return self.weights.get(tactic, 0.0)
