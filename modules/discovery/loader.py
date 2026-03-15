"""Load and manage bug bounty programs from knowledge bank."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class ProgramLoader:
    """Load BBP programs from knowledge bank."""

    def __init__(self, knowledge_dir: Optional[Path] = None):
        """Initialize loader with knowledge directory path."""
        if knowledge_dir is None:
            # Try multiple locations to find the knowledge directory
            candidates = [
                Path(__file__).resolve().parents[3] / "artifacts" / "knowledge",  # From module
                Path.cwd() / "artifacts" / "knowledge",  # From current working directory
                Path.cwd() / ".." / "artifacts" / "knowledge",  # One level up
            ]

            for candidate in candidates:
                if candidate.exists():
                    knowledge_dir = candidate
                    break

            if knowledge_dir is None:
                # Default to first candidate even if doesn't exist
                knowledge_dir = candidates[0]

        self.knowledge_dir = Path(knowledge_dir)
        self.canonical_jsonl = self.knowledge_dir / "bbp_programs_top50_canonical.jsonl"
        self.priority_csv = self.knowledge_dir / "bbp_priority_rank_top50_canonical.csv"
        self.validation_json = self.knowledge_dir / "bbp_top50_url_validation.json"
        self._programs_cache: Optional[List[Dict[str, Any]]] = None

    def load_programs(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """Load all programs from canonical JSONL."""
        if self._programs_cache and not refresh:
            return self._programs_cache

        programs = []
        try:
            with open(self.canonical_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        prog = json.loads(line)
                        programs.append(prog)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass

        self._programs_cache = programs
        return programs

    def get_program_by_id(self, program_id: str) -> Optional[Dict[str, Any]]:
        """Get program by ID."""
        programs = self.load_programs()
        for prog in programs:
            if prog.get("id") == program_id:
                return prog
        return None

    def filter_programs(
        self,
        programs: Optional[List[Dict[str, Any]]] = None,
        exploitability_tags: Optional[List[str]] = None,
        market: Optional[str] = None,
        priority_bucket: Optional[str] = None,
        min_payout: Optional[int] = None,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter programs by criteria."""
        if programs is None:
            programs = self.load_programs()

        filtered = programs

        if exploitability_tags:
            filtered = [
                p for p in filtered
                if any(tag in p.get("exploitability_tags", []) for tag in exploitability_tags)
            ]

        if market:
            filtered = [p for p in filtered if p.get("market") == market]

        if priority_bucket:
            filtered = [p for p in filtered if p.get("priority_bucket") == priority_bucket]

        if min_payout is not None:
            filtered = [
                p for p in filtered
                if p.get("payout_max_usd") and p.get("payout_max_usd") >= min_payout
            ]

        if platform:
            filtered = [p for p in filtered if p.get("platform") == platform]

        return filtered

    def get_verified_programs(self, verification_status: bool = True) -> List[Dict[str, Any]]:
        """Get programs with specified verification status."""
        programs = self.load_programs()
        return [p for p in programs if p.get("source_verified") == verification_status]

    def get_programs_by_market(self, market: str) -> List[Dict[str, Any]]:
        """Get programs by market sector."""
        programs = self.load_programs()
        return [p for p in programs if p.get("market") == market]

    def get_programs_by_exploitability(self, tag: str) -> List[Dict[str, Any]]:
        """Get programs that match exploitability tag."""
        programs = self.load_programs()
        return [p for p in programs if tag in p.get("exploitability_tags", [])]

    def get_top_payout_programs(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get top N programs by max payout."""
        programs = self.load_programs()
        ranked = sorted(
            programs,
            key=lambda p: p.get("payout_max_usd") or 0,
            reverse=True
        )
        return ranked[:n]

    def get_top_priority_programs(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get top N programs by priority score."""
        programs = self.load_programs()
        ranked = sorted(
            programs,
            key=lambda p: p.get("priority_score", 0),
            reverse=True
        )
        return ranked[:n]

    def validate_program_urls(self) -> Dict[str, Any]:
        """Load URL validation data."""
        try:
            with open(self.validation_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"validation": [], "checked_at": datetime.now(timezone.utc).isoformat()}

    def get_market_distribution(self) -> Dict[str, int]:
        """Get count of programs by market."""
        programs = self.load_programs()
        distribution = {}
        for prog in programs:
            market = prog.get("market", "unknown")
            distribution[market] = distribution.get(market, 0) + 1
        return distribution

    def get_exploitability_coverage(self) -> Dict[str, int]:
        """Get coverage of exploitability tags."""
        programs = self.load_programs()
        coverage = {}
        for prog in programs:
            for tag in prog.get("exploitability_tags", []):
                coverage[tag] = coverage.get(tag, 0) + 1
        return coverage

    def get_program_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics on programs."""
        programs = self.load_programs()
        if not programs:
            return {
                "total": 0,
                "verified": 0,
                "average_payout": 0,
                "markets": {},
                "exploitability_coverage": {},
            }

        verified = sum(1 for p in programs if p.get("source_verified"))
        payouts = [p.get("payout_max_usd") or 0 for p in programs if p.get("payout_max_usd")]
        avg_payout = sum(payouts) / len(payouts) if payouts else 0

        return {
            "total": len(programs),
            "verified": verified,
            "unverified": len(programs) - verified,
            "average_payout": avg_payout,
            "max_payout": max(payouts) if payouts else 0,
            "min_payout": min(payouts) if payouts else 0,
            "markets": self.get_market_distribution(),
            "exploitability_coverage": self.get_exploitability_coverage(),
        }
