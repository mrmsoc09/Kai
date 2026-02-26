from __future__ import annotations
from typing import List, Dict, Any, Callable

# Simple ToT: expand thoughts with heuristic score and pick best path

class ToTPlanner:
    def __init__(self, expand: Callable[[str], List[str]], score: Callable[[str], float], width: int = 3, depth: int = 3):
        self.expand = expand
        self.score = score
        self.width = max(1, width)
        self.depth = max(1, depth)

    def plan(self, goal: str) -> Dict[str, Any]:
        frontier = [(goal, self.score(goal))]
        paths: List[List[str]] = [[goal]]
        best_path, best_score = paths[0], frontier[0][1]
        for _ in range(self.depth):
            new_frontier = []
            new_paths = []
            for path in paths:
                last = path[-1]
                for t in self.expand(last)[: self.width]:
                    sc = self.score(t)
                    new_frontier.append((t, sc))
                    new_paths.append(path + [t])
                    if sc > best_score:
                        best_score = sc
                        best_path = path + [t]
            if not new_frontier:
                break
            # Keep top-k by score
            pairs = sorted(zip(new_paths, [s for _, s in new_frontier]), key=lambda x: x[1], reverse=True)[: self.width]
            paths = [p for p, _ in pairs]
        return { 'goal': goal, 'best_path': best_path, 'best_score': round(float(best_score), 3) }

# Default heuristics for security exploitation steps
DEFAULT_EXPAND = lambda t: [
    f"Enumerate endpoints from: {t}",
    f"Probe auth/csrf around: {t}",
    f"Chain with XSS vector near: {t}"
]

DEFAULT_SCORE = lambda t: 1.0 + 0.1 * len(t)


def plan_steps(goal: str) -> Dict[str, Any]:
    planner = ToTPlanner(DEFAULT_EXPAND, DEFAULT_SCORE, width=3, depth=3)
    return planner.plan(goal)
