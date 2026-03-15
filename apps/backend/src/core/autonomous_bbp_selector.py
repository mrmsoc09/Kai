"""
Autonomous Bug Bounty Program Selector
Intelligently analyzes and selects optimal BBP targets based on platform capabilities
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class SelectionCriteria(str, Enum):
    """Program selection criteria"""
    PAYOUT = "payout"  # Max payout potential
    SCOPE = "scope"  # Scope complexity/size
    MATCH_CAPABILITY = "match_capability"  # Platform capability match
    DIFFICULTY = "difficulty"  # Estimated difficulty
    ROI = "roi"  # Return on investment
    TIME_TO_VALUE = "time_to_value"  # Speed to first finding


@dataclass
class ProgramScore:
    """Scoring result for a program"""
    program_id: str
    program_name: str
    platform: str
    total_score: float
    payout_score: float
    scope_score: float
    capability_match_score: float
    difficulty_score: float
    roi_score: float
    time_to_value_score: float
    recommendation: str  # "high", "medium", "low"
    reasoning: List[str] = field(default_factory=list)
    estimated_cost_cents: int = 0
    estimated_findings: int = 0
    estimated_payout_range: tuple = (0, 0)


@dataclass
class SelectionResult:
    """Result from autonomous selection"""
    selected_programs: List[ProgramScore]
    total_analyzed: int
    selection_timestamp: datetime
    selection_criteria: List[SelectionCriteria]
    budget_allocated_cents: int
    estimated_total_payout: int
    reasoning: str


class AutonomousBBPSelector:
    """
    Autonomous Bug Bounty Program Selector

    Analyzes available BBP programs and selects optimal targets based on:
    - Platform capabilities (tools available)
    - Budget constraints
    - Expected ROI
    - Scope complexity
    - Payout potential
    """

    def __init__(self):
        """Initialize BBP selector"""
        self.platform_capabilities = self._assess_platform_capabilities()
        logger.info("✓ AutonomousBBPSelector initialized")

    def _assess_platform_capabilities(self) -> Dict[str, float]:
        """
        Assess what the platform can effectively test
        Returns capability scores (0.0-1.0) for different vulnerability types
        """
        return {
            # OWASP Top 10
            "sql_injection": 0.95,  # High capability with repair pipeline
            "xss": 0.90,
            "csrf": 0.85,
            "authentication": 0.90,
            "authorization": 0.85,
            "ssrf": 0.80,
            "xxe": 0.85,
            "deserialization": 0.75,
            "security_misconfiguration": 0.90,
            "logging_monitoring": 0.70,

            # Web application
            "api_vulnerabilities": 0.85,
            "business_logic": 0.70,
            "file_upload": 0.80,
            "path_traversal": 0.85,
            "open_redirect": 0.80,

            # Infrastructure
            "subdomain_takeover": 0.90,
            "exposed_services": 0.95,
            "dns_issues": 0.85,
            "ssl_tls": 0.90,

            # Modern app vulnerabilities
            "graphql": 0.75,
            "websocket": 0.70,
            "jwt_vulnerabilities": 0.85,
            "oauth_issues": 0.80,
        }

    async def analyze_and_select(
        self,
        available_programs: List[Dict[str, Any]],
        max_programs: int = 5,
        budget_cents: int = 10000,  # $100 default
        criteria: Optional[List[SelectionCriteria]] = None
    ) -> SelectionResult:
        """
        Analyze available programs and select optimal targets

        Args:
            available_programs: List of BBP programs to analyze
            max_programs: Maximum programs to select
            budget_cents: Available budget for scanning
            criteria: Selection criteria (default: all)

        Returns:
            SelectionResult with selected programs and reasoning
        """

        if criteria is None:
            criteria = [
                SelectionCriteria.ROI,
                SelectionCriteria.MATCH_CAPABILITY,
                SelectionCriteria.PAYOUT
            ]

        logger.info(f"Analyzing {len(available_programs)} programs with criteria: {criteria}")

        # Score all programs
        scored_programs = []
        for program in available_programs:
            score = await self._score_program(program, criteria)
            scored_programs.append(score)

        # Sort by total score (descending)
        scored_programs.sort(key=lambda x: x.total_score, reverse=True)

        # Select top programs within budget
        selected = []
        budget_used = 0

        for program in scored_programs:
            if len(selected) >= max_programs:
                break

            estimated_cost = program.estimated_cost_cents
            if budget_used + estimated_cost <= budget_cents:
                selected.append(program)
                budget_used += estimated_cost
            else:
                logger.debug(f"Skipping {program.program_name} - exceeds budget")

        # Calculate total estimated payout
        estimated_payout = sum(
            (score.estimated_payout_range[0] + score.estimated_payout_range[1]) // 2
            for score in selected
        )

        # Generate reasoning
        reasoning = self._generate_selection_reasoning(
            selected,
            len(available_programs),
            budget_cents,
            budget_used
        )

        result = SelectionResult(
            selected_programs=selected,
            total_analyzed=len(available_programs),
            selection_timestamp=datetime.now(timezone.utc),
            selection_criteria=criteria,
            budget_allocated_cents=budget_used,
            estimated_total_payout=estimated_payout,
            reasoning=reasoning
        )

        logger.info(f"✓ Selected {len(selected)}/{len(available_programs)} programs")
        logger.info(f"Budget allocated: ${budget_used/100:.2f}/${budget_cents/100:.2f}")
        logger.info(f"Estimated payout: ${estimated_payout/100:.2f}")

        return result

    async def _score_program(
        self,
        program: Dict[str, Any],
        criteria: List[SelectionCriteria]
    ) -> ProgramScore:
        """Score a single program based on criteria"""

        program_id = program.get("id", program.get("slug", "unknown"))
        program_name = program.get("name", "Unknown Program")
        platform = program.get("platform", "unknown")

        # Calculate individual scores
        payout_score = self._score_payout(program)
        scope_score = self._score_scope(program)
        capability_match = self._score_capability_match(program)
        difficulty_score = self._score_difficulty(program)
        roi_score = self._calculate_roi_score(payout_score, difficulty_score)
        time_to_value = self._score_time_to_value(scope_score, difficulty_score)

        # Weighted total score based on criteria
        weights = {
            SelectionCriteria.PAYOUT: 0.25,
            SelectionCriteria.SCOPE: 0.10,
            SelectionCriteria.MATCH_CAPABILITY: 0.20,
            SelectionCriteria.DIFFICULTY: 0.15,
            SelectionCriteria.ROI: 0.20,
            SelectionCriteria.TIME_TO_VALUE: 0.10
        }

        total_score = (
            payout_score * weights.get(SelectionCriteria.PAYOUT, 0.25) +
            scope_score * weights.get(SelectionCriteria.SCOPE, 0.10) +
            capability_match * weights.get(SelectionCriteria.MATCH_CAPABILITY, 0.20) +
            difficulty_score * weights.get(SelectionCriteria.DIFFICULTY, 0.15) +
            roi_score * weights.get(SelectionCriteria.ROI, 0.20) +
            time_to_value * weights.get(SelectionCriteria.TIME_TO_VALUE, 0.10)
        )

        # Generate reasoning
        reasoning = self._generate_program_reasoning(
            program, payout_score, capability_match, roi_score
        )

        # Estimate costs and outcomes
        estimated_cost = self._estimate_scan_cost(program, difficulty_score)
        estimated_findings = self._estimate_findings(scope_score, capability_match)
        estimated_payout = self._estimate_payout_range(program, estimated_findings)

        # Determine recommendation
        if total_score >= 0.75:
            recommendation = "high"
        elif total_score >= 0.50:
            recommendation = "medium"
        else:
            recommendation = "low"

        return ProgramScore(
            program_id=program_id,
            program_name=program_name,
            platform=platform,
            total_score=total_score,
            payout_score=payout_score,
            scope_score=scope_score,
            capability_match_score=capability_match,
            difficulty_score=difficulty_score,
            roi_score=roi_score,
            time_to_value_score=time_to_value,
            recommendation=recommendation,
            reasoning=reasoning,
            estimated_cost_cents=estimated_cost,
            estimated_findings=estimated_findings,
            estimated_payout_range=estimated_payout
        )

    def _score_payout(self, program: Dict[str, Any]) -> float:
        """Score based on payout potential (0.0-1.0)"""
        max_payout = program.get("max_payout", 0)

        # Normalize payout (log scale for better distribution)
        # $100 = 0.0, $50,000+ = 1.0
        if max_payout <= 100:
            return 0.1
        elif max_payout >= 50000:
            return 1.0
        else:
            # Logarithmic scale
            import math
            score = (math.log10(max_payout) - 2) / 2.7  # log10(100)=2, log10(50000)≈4.7
            return max(0.0, min(1.0, score))

    def _score_scope(self, program: Dict[str, Any]) -> float:
        """Score based on scope size and clarity (0.0-1.0)"""
        scope = program.get("scope", [])

        if not scope:
            return 0.3  # Unknown scope = medium-low

        # More scope items = more opportunities
        scope_size = len(scope) if isinstance(scope, list) else 1

        # Normalize: 1-3 items = 0.4, 10+ items = 1.0
        score = 0.4 + (min(scope_size, 10) - 1) * 0.066
        return min(1.0, score)

    def _score_capability_match(self, program: Dict[str, Any]) -> float:
        """Score based on match with platform capabilities (0.0-1.0)"""

        # Extract vulnerability types from program
        vuln_types = program.get("vuln_types", [])
        target_types = program.get("target_types", [])

        if not vuln_types and not target_types:
            # No specific info - assume moderate match
            return 0.6

        # Calculate average capability score for this program
        matches = []
        for vuln_type in vuln_types:
            capability = self.platform_capabilities.get(vuln_type.lower(), 0.5)
            matches.append(capability)

        # Web/API targets = good match
        if any(t in ["web", "api", "webapp"] for t in target_types):
            matches.append(0.85)

        # Mobile = lower match (we focus on web)
        if any(t in ["mobile", "android", "ios"] for t in target_types):
            matches.append(0.50)

        if not matches:
            return 0.6

        return sum(matches) / len(matches)

    def _score_difficulty(self, program: Dict[str, Any]) -> float:
        """Score based on difficulty (lower difficulty = higher score)"""

        # Factors that increase difficulty:
        # - High competition
        # - Large company with mature security
        # - Complex technologies

        # This is inverted: easier programs get higher scores
        difficulty_factors = []

        # Company size indicator
        company_size = program.get("company_size", "unknown")
        if company_size == "enterprise":
            difficulty_factors.append(0.4)  # Harder
        elif company_size == "medium":
            difficulty_factors.append(0.6)
        else:
            difficulty_factors.append(0.7)  # Easier

        # Mature program = harder
        launched = program.get("launched_at")
        if launched:
            # Programs < 6 months = easier
            difficulty_factors.append(0.7)
        else:
            difficulty_factors.append(0.6)

        return sum(difficulty_factors) / len(difficulty_factors) if difficulty_factors else 0.6

    def _calculate_roi_score(self, payout_score: float, difficulty_score: float) -> float:
        """Calculate ROI score (payout potential / difficulty)"""
        return (payout_score * 0.6 + difficulty_score * 0.4)

    def _score_time_to_value(self, scope_score: float, difficulty_score: float) -> float:
        """Estimate time to first finding (faster = higher score)"""
        # Larger scope + easier = faster findings
        return (scope_score * 0.4 + difficulty_score * 0.6)

    def _estimate_scan_cost(self, program: Dict[str, Any], difficulty: float) -> int:
        """Estimate cost to scan this program (in cents)"""

        # Base cost: $2-10 depending on difficulty
        # Easier programs = lower cost (more local models)
        base_cost = 200 + int((1.0 - difficulty) * 800)  # $2-10

        # Add cost based on scope size
        scope = program.get("scope", [])
        scope_size = len(scope) if isinstance(scope, list) else 1
        scope_cost = scope_size * 100  # $1 per scope item

        return base_cost + scope_cost

    def _estimate_findings(self, scope_score: float, capability_match: float) -> int:
        """Estimate number of findings"""
        # More scope + better capability match = more findings
        base_findings = 2
        additional = int((scope_score * capability_match) * 8)
        return base_findings + additional

    def _estimate_payout_range(
        self,
        program: Dict[str, Any],
        estimated_findings: int
    ) -> tuple:
        """Estimate payout range based on program and findings"""

        min_payout = program.get("min_payout", 100)
        max_payout = program.get("max_payout", 1000)

        # Conservative estimate: low-medium severity findings
        # Assume 70% low, 25% medium, 5% high
        estimated_low = int(min_payout * estimated_findings * 0.7)
        estimated_high = int(
            (min_payout * estimated_findings * 0.7) +
            ((max_payout * 0.3) * estimated_findings * 0.25) +
            (max_payout * estimated_findings * 0.05)
        )

        return (estimated_low, estimated_high)

    def _generate_program_reasoning(
        self,
        program: Dict[str, Any],
        payout_score: float,
        capability_match: float,
        roi_score: float
    ) -> List[str]:
        """Generate reasoning for program selection/rejection"""

        reasons = []

        # Payout analysis
        max_payout = program.get("max_payout", 0)
        if payout_score >= 0.8:
            reasons.append(f"High payout potential (${max_payout:,})")
        elif payout_score <= 0.3:
            reasons.append(f"Low payout potential (${max_payout:,})")

        # Capability match
        if capability_match >= 0.8:
            reasons.append("Excellent capability match with platform tools")
        elif capability_match <= 0.4:
            reasons.append("Limited capability match - may require manual testing")

        # ROI
        if roi_score >= 0.8:
            reasons.append("High ROI expected")
        elif roi_score <= 0.4:
            reasons.append("Lower ROI expected")

        # Scope
        scope = program.get("scope", [])
        if isinstance(scope, list) and len(scope) > 5:
            reasons.append(f"Large scope ({len(scope)} targets)")

        return reasons

    def _generate_selection_reasoning(
        self,
        selected: List[ProgramScore],
        total_analyzed: int,
        budget_cents: int,
        budget_used: int
    ) -> str:
        """Generate overall selection reasoning"""

        avg_score = sum(p.total_score for p in selected) / len(selected) if selected else 0
        total_estimated_payout = sum(
            (p.estimated_payout_range[0] + p.estimated_payout_range[1]) // 2
            for p in selected
        )

        reasoning = f"""
Autonomous Selection Analysis:

Selected {len(selected)} programs from {total_analyzed} candidates based on:
- Average selection score: {avg_score:.2%}
- Budget utilization: ${budget_used/100:.2f}/${budget_cents/100:.2f} ({budget_used/budget_cents*100:.1f}%)
- Estimated total payout range: ${total_estimated_payout/100:.2f}
- ROI estimate: {(total_estimated_payout/budget_used if budget_used > 0 else 0):.1f}x

Selection prioritized:
1. High ROI opportunities (payout vs difficulty)
2. Strong capability match with platform tools
3. Optimal budget allocation

Programs are ranked by total score and filtered by budget constraints.
        """.strip()

        return reasoning


# Global instance
_selector: Optional[AutonomousBBPSelector] = None


def get_bbp_selector() -> AutonomousBBPSelector:
    """Get global BBP selector instance"""
    global _selector
    if _selector is None:
        _selector = AutonomousBBPSelector()
    return _selector
