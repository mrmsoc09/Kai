"""Program scoring and ranking engine."""

from typing import List, Dict, Any, Optional
import math


class ProgramScorer:
    """Score and rank programs for autonomous targeting."""

    # Weights for different scoring factors
    PAYOUT_WEIGHT = 0.35  # How much we value high payouts
    EXPLOITABILITY_WEIGHT = 0.40  # How likely we are to find issues
    ACCEPTANCE_WEIGHT = 0.15  # How likely they are to accept our report
    MARKET_OPPORTUNITY_WEIGHT = 0.10  # Strategic market value

    def __init__(self):
        """Initialize scorer with default weights."""
        self.weights = {
            "payout": self.PAYOUT_WEIGHT,
            "exploitability": self.EXPLOITABILITY_WEIGHT,
            "acceptance": self.ACCEPTANCE_WEIGHT,
            "market_opportunity": self.MARKET_OPPORTUNITY_WEIGHT,
        }

    def score_program(
        self,
        program: Dict[str, Any],
        k1_capabilities: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Score a single program based on multiple factors.

        Returns dict with:
        - score: 0-1 overall score
        - payout_score: normalized payout value
        - exploitability_score: K1 fit for program targets
        - acceptance_score: likelihood of acceptance
        - market_opportunity_score: strategic value
        - breakdown: detailed scoring factors
        """
        if k1_capabilities is None:
            k1_capabilities = self._default_k1_capabilities()

        payout_score = self._score_payout(program)
        exploitability_score = self._score_exploitability(program, k1_capabilities)
        acceptance_score = self._score_acceptance(program)
        market_opportunity_score = self._score_market_opportunity(program)

        # Weighted combination
        overall_score = (
            payout_score * self.weights["payout"]
            + exploitability_score * self.weights["exploitability"]
            + acceptance_score * self.weights["acceptance"]
            + market_opportunity_score * self.weights["market_opportunity"]
        )

        return {
            "program_id": program.get("id"),
            "program_name": program.get("name"),
            "score": min(1.0, overall_score),
            "payout_score": payout_score,
            "exploitability_score": exploitability_score,
            "acceptance_score": acceptance_score,
            "market_opportunity_score": market_opportunity_score,
            "breakdown": {
                "payout_max": program.get("payout_max_usd"),
                "platform": program.get("platform"),
                "exploitability_tags": program.get("exploitability_tags", []),
                "priority_bucket": program.get("priority_bucket"),
                "market": program.get("market"),
                "source_verified": program.get("source_verified"),
            },
        }

    def score_programs(
        self,
        programs: List[Dict[str, Any]],
        k1_capabilities: Optional[Dict[str, float]] = None,
        sort: bool = True,
    ) -> List[Dict[str, Any]]:
        """Score multiple programs and optionally sort by score."""
        scores = [self.score_program(prog, k1_capabilities) for prog in programs]

        if sort:
            scores.sort(key=lambda x: x["score"], reverse=True)

        return scores

    def _score_payout(self, program: Dict[str, Any]) -> float:
        """Score based on payout value. Assume $2M is max (Apple)."""
        max_payout = program.get("payout_max_usd")
        if not max_payout:
            return 0.3  # Programs without published payouts get baseline score

        # Normalize to 0-1, with diminishing returns above $100k
        if max_payout >= 2000000:
            return 1.0
        elif max_payout >= 100000:
            return 0.8 + (min(1900000, max_payout - 100000) / 1900000) * 0.2
        elif max_payout >= 10000:
            return 0.3 + (min(90000, max_payout - 10000) / 90000) * 0.5
        else:
            return 0.1 + (max_payout / 10000) * 0.2

    def _score_exploitability(
        self, program: Dict[str, Any], k1_capabilities: Dict[str, float]
    ) -> float:
        """Score based on how well K1's capabilities match program scope."""
        tags = program.get("exploitability_tags", [])
        if not tags:
            return 0.5  # Unknown exploitability

        # Map tags to K1 capability scores
        matching_scores = []
        for tag in tags:
            cap_score = k1_capabilities.get(tag, 0.3)
            matching_scores.append(cap_score)

        # Average of matching capabilities, boosted by diversity
        if not matching_scores:
            return 0.3
        avg_score = sum(matching_scores) / len(matching_scores)
        diversity_bonus = min(0.2, len(tags) * 0.05)  # Bonus for multiple attack vectors

        return min(1.0, avg_score + diversity_bonus)

    def _score_acceptance(self, program: Dict[str, Any]) -> float:
        """Score based on acceptance likelihood."""
        # Higher score for verified, established programs
        base_score = 0.6

        if program.get("source_verified"):
            base_score += 0.2

        # Platform popularity factor
        platform = program.get("platform")
        platform_score = {
            "direct": 0.15,  # Company-direct programs (Apple, Google)
            "hackerone": 0.1,  # HackerOne adds slight overhead
            "bugcrowd": 0.05,  # BugCrowd sometimes slower
            "intigriti": 0.08,  # Intigriti is solid
            "yeswehack": 0.05,  # YesWeHack smaller programs
            "disclosed": 0.0,  # Disclosed programs may be inactive
        }
        base_score += platform_score.get(platform, 0.05)

        # Priority bucket adjustment
        priority = program.get("priority_bucket", "medium")
        priority_score = {
            "high": 0.1,
            "medium": 0.05,
            "low": 0.0,
        }
        base_score += priority_score.get(priority, 0.0)

        return min(1.0, base_score)

    def _score_market_opportunity(self, program: Dict[str, Any]) -> float:
        """Score strategic market opportunity."""
        market = program.get("market", "other")

        # Some markets are hotter for bug hunters
        market_score = {
            "cloud": 0.9,  # AWS, Azure, Google Cloud - high adoption
            "consumer": 0.7,  # Apple, Meta - high payouts
            "fintech": 0.8,  # Crypto, payments - high value targets
            "enterprise": 0.6,  # Microsoft, Okta - established programs
            "security": 0.8,  # Cloudflare, Duo - sensitive
            "other": 0.5,
        }

        return market_score.get(market, 0.5)

    def rank_for_k1_objective(
        self,
        programs: List[Dict[str, Any]],
        objective: str = "balanced",
        k1_capabilities: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank programs for specific K1 objective.

        Objectives:
        - balanced: standard payout/exploitability balance
        - high_payout: maximize expected payout
        - high_confidence: maximize likelihood of acceptance
        - research: maximize learning/novel targets
        """
        if k1_capabilities is None:
            k1_capabilities = self._default_k1_capabilities()

        scores = self.score_programs(programs, k1_capabilities, sort=False)

        # Adjust weights based on objective
        if objective == "high_payout":
            for s in scores:
                s["adjusted_score"] = (
                    s["payout_score"] * 0.6
                    + s["exploitability_score"] * 0.25
                    + s["acceptance_score"] * 0.1
                    + s["market_opportunity_score"] * 0.05
                )

        elif objective == "high_confidence":
            for s in scores:
                s["adjusted_score"] = (
                    s["acceptance_score"] * 0.4
                    + s["exploitability_score"] * 0.4
                    + s["payout_score"] * 0.15
                    + s["market_opportunity_score"] * 0.05
                )

        elif objective == "research":
            for s in scores:
                s["adjusted_score"] = (
                    s["exploitability_score"] * 0.5
                    + s["market_opportunity_score"] * 0.25
                    + s["payout_score"] * 0.15
                    + s["acceptance_score"] * 0.1
                )

        else:  # balanced
            for s in scores:
                s["adjusted_score"] = s["score"]

        # Sort by adjusted score
        scores.sort(key=lambda x: x["adjusted_score"], reverse=True)
        return scores

    def _default_k1_capabilities(self) -> Dict[str, float]:
        """Default K1 capability scores for different exploitability types."""
        return {
            "web": 0.9,  # K1 is very strong at web vulnerabilities
            "api": 0.85,  # APIs are well-studied
            "mobile": 0.6,  # Harder without physical devices
            "cloud": 0.8,  # Good at configuration/IAM issues
            "iam": 0.85,  # K1 can find auth/access control issues
            "crypto": 0.5,  # Crypto research is difficult
            "hardware": 0.2,  # Very limited (requires lab setup)
            "desktop": 0.4,  # Harder without deep OS knowledge
        }

    def get_recommended_targets(
        self,
        programs: List[Dict[str, Any]],
        count: int = 5,
        objective: str = "balanced",
    ) -> List[Dict[str, Any]]:
        """Get top N recommended targets for scanning."""
        ranked = self.rank_for_k1_objective(programs, objective)
        return ranked[:count]

    def group_programs_by_objective(
        self,
        programs: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group programs by different objectives for easy selection."""
        objectives = ["balanced", "high_payout", "high_confidence", "research"]
        grouped = {}

        for obj in objectives:
            ranked = self.rank_for_k1_objective(programs, obj)
            grouped[obj] = ranked[:10]  # Top 10 per objective

        return grouped
