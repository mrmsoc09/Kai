"""Intelligent target selection for autonomous scanning."""

from typing import List, Dict, Any, Optional
import random
from datetime import datetime, timedelta


class TargetSelector:
    """Select targets for autonomous scanning based on multiple criteria."""

    def __init__(self):
        """Initialize selector."""
        self.selection_history: List[Dict[str, Any]] = []

    def select_target(
        self,
        programs: List[Dict[str, Any]],
        scorer_results: List[Dict[str, Any]],
        strategy: str = "greedy",
    ) -> Optional[Dict[str, Any]]:
        """
        Select a single target from available programs.

        Strategies:
        - greedy: always pick highest score
        - round_robin: cycle through top candidates
        - random_top10: random from top 10
        - balanced: pick based on diversity
        """
        if not scorer_results:
            return None

        if strategy == "greedy":
            selected = scorer_results[0]

        elif strategy == "round_robin":
            # Pick next in rotation, cycling through top programs
            idx = len(self.selection_history) % min(10, len(scorer_results))
            selected = scorer_results[idx]

        elif strategy == "random_top10":
            # Randomize among top 10 to avoid always picking same target
            candidates = scorer_results[:10]
            selected = random.choice(candidates)

        elif strategy == "balanced":
            # Pick highest score not recently selected
            for result in scorer_results:
                prog_id = result.get("program_id")
                if not self._recently_selected(prog_id, hours=24):
                    selected = result
                    break
            else:
                selected = scorer_results[0]

        else:
            selected = scorer_results[0]

        # Log selection
        self.selection_history.append({
            "program_id": selected.get("program_id"),
            "program_name": selected.get("program_name"),
            "score": selected.get("score"),
            "strategy": strategy,
            "selected_at": datetime.utcnow().isoformat(),
        })

        return selected

    def select_batch(
        self,
        programs: List[Dict[str, Any]],
        scorer_results: List[Dict[str, Any]],
        batch_size: int = 3,
        strategy: str = "diverse",
    ) -> List[Dict[str, Any]]:
        """
        Select multiple targets for parallel scanning.

        Strategies:
        - diverse: pick from different markets/exploitability
        - score_based: pick top N by score
        - market_spread: one from each market
        """
        if not scorer_results:
            return []

        if strategy == "score_based":
            selected = scorer_results[:batch_size]

        elif strategy == "diverse":
            selected = []
            seen_markets = set()
            seen_exploitability = set()

            for result in scorer_results:
                if len(selected) >= batch_size:
                    break

                # Find program data for diversification
                prog_id = result.get("program_id")
                program = self._find_program(programs, prog_id)
                if not program:
                    continue

                market = program.get("market")
                tags = tuple(sorted(program.get("exploitability_tags", [])))

                # Prefer programs from different markets/exploitability
                is_new_market = market not in seen_markets
                is_new_exploitability = tags not in seen_exploitability

                if is_new_market or is_new_exploitability or len(selected) < 2:
                    selected.append(result)
                    seen_markets.add(market)
                    seen_exploitability.add(tags)

            # Fill remaining slots if needed
            while len(selected) < batch_size and len(selected) < len(scorer_results):
                for result in scorer_results:
                    if result not in selected:
                        selected.append(result)
                        break

            selected = selected[:batch_size]

        elif strategy == "market_spread":
            # One from each market
            selected_by_market = {}
            for result in scorer_results:
                prog_id = result.get("program_id")
                program = self._find_program(programs, prog_id)
                if not program:
                    continue

                market = program.get("market", "unknown")
                if market not in selected_by_market:
                    selected_by_market[market] = result

                if len(selected_by_market) >= batch_size:
                    break

            selected = list(selected_by_market.values())[:batch_size]

        else:
            selected = scorer_results[:batch_size]

        # Log batch selections
        for result in selected:
            self.selection_history.append({
                "program_id": result.get("program_id"),
                "program_name": result.get("program_name"),
                "score": result.get("score"),
                "strategy": f"batch_{strategy}",
                "selected_at": datetime.utcnow().isoformat(),
            })

        return selected

    def select_for_rotation(
        self,
        programs: List[Dict[str, Any]],
        scorer_results: List[Dict[str, Any]],
        rotation_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Select programs for rotation over N days (one per day).
        Avoids repeating recently scanned targets.
        """
        cutoff_time = datetime.utcnow() - timedelta(days=rotation_days)
        available = []

        for result in scorer_results:
            prog_id = result.get("program_id")
            last_selection = self._get_last_selection(prog_id)

            if last_selection is None or last_selection < cutoff_time:
                available.append(result)

        # Shuffle to add randomness
        random.shuffle(available)
        return available[:rotation_days]

    def recommend_for_autonomy_tier(
        self,
        programs: List[Dict[str, Any]],
        scorer_results: List[Dict[str, Any]],
        autonomy_tier: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Recommend programs based on autonomy tier.

        Tiers:
        - 0 (PLANNING): All programs, HiL approval required
        - 1 (NOTIFICATION): Only verified, high-acceptance programs
        - 2 (APPROVAL): Only high-confidence programs with recent history
        - 3 (AUTONOMOUS): Only top-tier programs with strong track record
        """
        if autonomy_tier == 0:  # PLANNING
            return scorer_results[:20]  # All options

        elif autonomy_tier == 1:  # NOTIFICATION
            # Verified programs with good acceptance
            candidates = [
                r for r in scorer_results
                if r.get("acceptance_score", 0) > 0.6
                and self._find_program(programs, r.get("program_id"))
                and self._find_program(programs, r.get("program_id")).get("source_verified")
            ]
            return candidates[:10]

        elif autonomy_tier == 2:  # APPROVAL
            # High-confidence programs with 3+ previous successful scans
            candidates = [
                r for r in scorer_results
                if r.get("acceptance_score", 0) > 0.7
                and self._count_successful_scans(r.get("program_id")) >= 3
            ]
            return candidates[:5]

        elif autonomy_tier == 3:  # AUTONOMOUS
            # Only proven high-performers
            candidates = [
                r for r in scorer_results
                if r.get("score", 0) > 0.75
                and self._count_successful_scans(r.get("program_id")) >= 10
            ]
            return candidates[:3]

        return scorer_results[:5]

    def _find_program(
        self, programs: List[Dict[str, Any]], prog_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find program by ID."""
        for prog in programs:
            if prog.get("id") == prog_id:
                return prog
        return None

    def _recently_selected(self, program_id: str, hours: int = 24) -> bool:
        """Check if program was recently selected."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        for entry in reversed(self.selection_history):
            if entry.get("program_id") == program_id:
                try:
                    selected_at = datetime.fromisoformat(entry.get("selected_at", ""))
                    return selected_at > cutoff
                except (ValueError, TypeError):
                    return False
        return False

    def _get_last_selection(self, program_id: str) -> Optional[datetime]:
        """Get timestamp of last selection."""
        for entry in reversed(self.selection_history):
            if entry.get("program_id") == program_id:
                try:
                    return datetime.fromisoformat(entry.get("selected_at", ""))
                except (ValueError, TypeError):
                    return None
        return None

    def _count_successful_scans(self, program_id: str) -> int:
        """Count successful scans for a program (stub)."""
        # In real implementation, query findings/submissions database
        return len([
            e for e in self.selection_history
            if e.get("program_id") == program_id
        ])

    def get_selection_metrics(self) -> Dict[str, Any]:
        """Get metrics on selection history."""
        if not self.selection_history:
            return {
                "total_selections": 0,
                "unique_programs": 0,
                "strategies_used": {},
                "most_selected": None,
                "selection_rate": 0,
            }

        unique_progs = set(e.get("program_id") for e in self.selection_history)
        strategies = {}
        for entry in self.selection_history:
            strategy = entry.get("strategy", "unknown")
            strategies[strategy] = strategies.get(strategy, 0) + 1

        # Find most selected program
        prog_counts = {}
        for entry in self.selection_history:
            prog_id = entry.get("program_id")
            prog_counts[prog_id] = prog_counts.get(prog_id, 0) + 1

        most_selected = max(prog_counts.items(), key=lambda x: x[1])[0] if prog_counts else None

        return {
            "total_selections": len(self.selection_history),
            "unique_programs": len(unique_progs),
            "strategies_used": strategies,
            "most_selected": most_selected,
            "average_score": sum(
                e.get("score", 0) for e in self.selection_history
            ) / len(self.selection_history) if self.selection_history else 0,
        }
