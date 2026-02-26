from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Callable
import itertools

@dataclass
class Thought:
    state: Dict[str, Any]
    rationale: str
    score: float = 0.0

@dataclass
class ToTConfig:
    breadth: int = 4
    depth: int = 3
    beam_size: int = 5

class DeepReasoner:
    def __init__(self, config: ToTConfig | None = None):
        self.cfg = config or ToTConfig()

    def search(self, seed: Thought, expand_fn: Callable[[Thought], List[Thought]], score_fn: Callable[[Thought], float]) -> List[Thought]:
        frontier: List[Thought] = [seed]
        best: List[Thought] = []
        for _ in range(self.cfg.depth):
            expansions = list(itertools.chain.from_iterable(expand_fn(t) for t in frontier))
            for t in expansions:
                t.score = score_fn(t)
            expansions.sort(key=lambda t: t.score, reverse=True)
            frontier = expansions[: self.cfg.beam_size]
            best.extend(frontier)
            if not frontier:
                break
        best.sort(key=lambda t: t.score, reverse=True)
        return best[: self.cfg.beam_size]

DEFAULT_ATTACK_TACTICS = [
    "Subdomain Enum", "Dir Bruteforce", "JS Secrets", "Param Fuzzing", "Auth Bypass", "IDOR Mapping", "SSRF Probes", "CORS Checks", "Open Redirect", "Header Injection"
]

def rule_based_expand(t: Thought) -> List[Thought]:
    scope = t.state.get('scope', {})
    assets = scope.get('assets', []) or ["root"]
    already = {a.get('name') for a in t.state.get('actions', [])}
    out: List[Thought] = []
    for asset in assets:
        count = 0
        for tactic in DEFAULT_ATTACK_TACTICS:
            name = f"{tactic} @ {asset}"
            if name in already:
                continue
            actions = list(t.state.get('actions', [])) + [{
                'name': name, 'tactic': tactic, 'asset': asset, 'requires_hil': True, 'risk': 'low', 'mode': 'plan'
            }]
            out.append(Thought(state={'scope': scope, 'actions': actions}, rationale=f"Consider {tactic} on {asset}"))
            count += 1
            if count >= 4:
                break
    return out

def simple_score(t: Thought) -> float:
    actions = t.state.get('actions', [])
    tactics = {a['tactic'] for a in actions}
    assets = {a['asset'] for a in actions}
    return len(tactics) * 1.0 + len(assets) * 0.5
