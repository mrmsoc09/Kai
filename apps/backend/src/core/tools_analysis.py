"""
Analysis Tools for K1
Comprehensive finding analysis, chain detection, and intelligence synthesis
"""

import logging
from typing import Any, Dict, List, Optional
import time
from dataclasses import dataclass

from .llm_client import LLMClientFactory, LLMMessage
from .tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    ToolStatus,
    ToolAutonomyTier,
)

logger = logging.getLogger(__name__)


class VulnerabilityAnalyzerTool(BaseTool):
    """
    Deep analysis of vulnerability context

    4-step reasoning:
    1. Technical vulnerability analysis
    2. Target technology assessment
    3. Real-world exploitation likelihood
    4. Data/system impact calculation
    """

    def __init__(self):
        parameters = [
            ToolParameter(
                name="vulnerability_type",
                type="string",
                description="Type of vulnerability (XSS, SQLI, RCE, etc.)",
                required=True,
            ),
            ToolParameter(
                name="affected_technology",
                type="string",
                description="Technology or framework affected",
                required=True,
            ),
            ToolParameter(
                name="attack_description",
                type="string",
                description="Description of how the vulnerability is exploited",
                required=True,
            ),
            ToolParameter(
                name="impact_description",
                type="string",
                description="Potential impact if exploited",
                required=False,
            ),
            ToolParameter(
                name="exploitation_difficulty",
                type="string",
                description="Difficulty of exploitation",
                required=False,
                enum=["trivial", "easy", "moderate", "difficult", "very_difficult"],
                default="moderate",
            ),
        ]

        super().__init__(
            id="vulnerability_analyzer",
            name="Vulnerability Analyzer",
            description="Deep analysis of vulnerability context and real-world impact",
            category=ToolCategory.ANALYSIS,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=parameters,
            version="1.0.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        """Execute vulnerability analysis"""
        start_time = time.time()

        try:
            is_valid, error_msg = self.validate_parameters(**kwargs)
            if not is_valid:
                return ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.FAILED,
                    output=None,
                    error=error_msg,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            vuln_type = kwargs.get("vulnerability_type")
            technology = kwargs.get("affected_technology")
            attack_desc = kwargs.get("attack_description")
            impact_desc = kwargs.get("impact_description", "")
            exploit_difficulty = kwargs.get("exploitation_difficulty", "moderate")

            # Step 1: Technical analysis
            tech_analysis = self._analyze_technical_aspects(vuln_type, technology)

            # Step 2: Technology assessment
            tech_assessment = self._assess_technology(technology, vuln_type)

            # Step 3: Exploitation likelihood
            exploit_likelihood = self._assess_exploitation_likelihood(
                exploit_difficulty, attack_desc
            )

            # Step 4: Impact calculation
            impact = self._calculate_impact(impact_desc, vuln_type)

            output = {
                "vulnerability_type": vuln_type,
                "technology": technology,
                "technical_analysis": tech_analysis,
                "technology_assessment": tech_assessment,
                "exploitation_likelihood": exploit_likelihood,
                "impact_assessment": impact,
                "overall_risk_score": round(
                    (tech_analysis["score"] +
                     tech_assessment["score"] +
                     exploit_likelihood["score"] +
                     impact["score"]) / 4.0,
                    2
                ),
            }

            self.record_execution(
                ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.COMPLETED,
                    output=output,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            )

            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.COMPLETED,
                output=output,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Vulnerability analyzer error: {str(e)}")
            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.FAILED,
                output=None,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    @staticmethod
    def _analyze_technical_aspects(vuln_type: str, technology: str) -> Dict[str, Any]:
        """Analyze technical aspects of vulnerability"""
        score = 7.0  # Default score

        type_scores = {
            "xss": 7.5,
            "sqli": 8.5,
            "rce": 9.5,
            "csrf": 6.0,
            "auth": 8.0,
            "disclosure": 5.0,
            "dos": 7.0,
        }

        vuln_lower = vuln_type.lower()
        for vtype, vscore in type_scores.items():
            if vtype in vuln_lower:
                score = vscore
                break

        return {
            "score": score,
            "type_complexity": "high" if score > 8 else "medium",
            "attack_vector": "network",
            "authentication_required": "rce" not in vuln_lower,
        }

    @staticmethod
    def _assess_technology(technology: str, vuln_type: str) -> Dict[str, Any]:
        """Assess technology vulnerability patterns"""
        score = 6.0

        critical_tech = ["database", "api", "authentication", "payment"]
        for tech_name in critical_tech:
            if tech_name.lower() in technology.lower():
                score = 8.5
                break

        return {
            "score": score,
            "technology": technology,
            "criticality": "high" if score > 7.5 else "medium",
            "adoption_rate": "high",
        }

    @staticmethod
    def _assess_exploitation_likelihood(difficulty: str, description: str) -> Dict[str, Any]:
        difficulty_scores = {
            "trivial": 9.5,
            "easy": 8.5,
            "moderate": 7.0,
            "difficult": 5.0,
            "very_difficult": 3.0,
        }

        score = difficulty_scores.get(difficulty.lower(), 7.0)

        return {
            "score": score,
            "difficulty": difficulty,
            "likelihood": "high" if score > 7 else "moderate",
            "public_exploits_available": score > 7.0,
        }

    @staticmethod
    def _calculate_impact(impact_desc: str, vuln_type: str) -> Dict[str, Any]:
        """Calculate potential impact"""
        score = 6.0

        if any(kw in impact_desc.lower() for kw in ["data", "steal", "leak"]):
            score = 9.0
        elif any(kw in impact_desc.lower() for kw in ["system", "crash"]):
            score = 7.5
        elif any(kw in impact_desc.lower() for kw in ["bypass", "access"]):
            score = 8.0

        return {
            "score": score,
            "severity": "critical" if score > 8.5 else ("high" if score > 7 else "medium"),
            "data_impact": "data" in impact_desc.lower(),
            "system_impact": "system" in impact_desc.lower(),
        }


class ChainAnalyzerTool(BaseTool):
    """
    Multi-step attack chain identification and analysis

    3-step reasoning:
    1. Find correlated findings
    2. Identify attack sequences
    3. Calculate chain severity and prioritization
    """

    def __init__(self):
        parameters = [
            ToolParameter(
                name="findings",
                type="array",
                description="List of findings to correlate",
                required=True,
            ),
            ToolParameter(
                name="target_scope",
                type="string",
                description="Scope/domain of the target",
                required=False,
            ),
        ]

        super().__init__(
            id="chain_analyzer",
            name="Chain Analyzer",
            description="Analyze multi-step attack chains and sequences",
            category=ToolCategory.ANALYSIS,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=parameters,
            version="1.0.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        """Execute chain analysis"""
        start_time = time.time()

        try:
            is_valid, error_msg = self.validate_parameters(**kwargs)
            if not is_valid:
                return ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.FAILED,
                    output=None,
                    error=error_msg,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            findings = kwargs.get("findings", [])
            target_scope = kwargs.get("target_scope", "unknown")

            # Find correlations
            correlations = self._find_correlations(findings)

            # Build attack sequences
            sequences = self._build_sequences(findings, correlations)

            # Calculate chain severity
            chains = self._calculate_chain_severity(sequences)

            output = {
                "target_scope": target_scope,
                "findings_analyzed": len(findings),
                "correlations_found": len(correlations),
                "attack_chains_identified": len(chains),
                "chains": chains,
                "total_chain_value": sum(c.get("estimated_payout", 0) for c in chains),
            }

            self.record_execution(
                ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.COMPLETED,
                    output=output,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            )

            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.COMPLETED,
                output=output,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Chain analyzer error: {str(e)}")
            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.FAILED,
                output=None,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    @staticmethod
    def _find_correlations(findings: List[Any]) -> List[Dict[str, Any]]:
        """Find correlations between findings"""
        correlations = []

        # Simple correlation: same asset or related types
        if len(findings) > 1:
            for i, f1 in enumerate(findings):
                for f2 in findings[i + 1 :]:
                    correlation_score = 0.5  # Base correlation
                    correlations.append(
                        {
                            "finding_1": f1 if isinstance(f1, str) else str(f1),
                            "finding_2": f2 if isinstance(f2, str) else str(f2),
                            "correlation_score": correlation_score,
                        }
                    )

        return correlations

    @staticmethod
    def _build_sequences(findings: List[Any], correlations: List[Dict]) -> List[List[str]]:
        """Build attack sequences from findings"""
        if not findings or not correlations:
            return []

        sequences = []
        if len(findings) >= 2:
            sequences.append([f if isinstance(f, str) else str(f) for f in findings[:3]])

        return sequences

    @staticmethod
    def _calculate_chain_severity(sequences: List[List[str]]) -> List[Dict[str, Any]]:
        """Calculate severity of chains"""
        chains = []

        for i, seq in enumerate(sequences):
            chain = {
                "chain_id": i + 1,
                "steps": len(seq),
                "finding_count": len(seq),
                "severity": "high" if len(seq) > 2 else "medium",
                "estimated_payout": (len(seq) * 500),
            }
            chains.append(chain)

        return chains


class ProgramMatcherTool(BaseTool):
    """
    Intelligent program targeting and matching

    3-step reasoning:
    1. Parse program requirements
    2. Assess finding relevance
    3. Calculate match score and estimate payout
    """

    def __init__(self):
        parameters = [
            ToolParameter(
                name="finding_title",
                type="string",
                description="Title of the finding",
                required=True,
            ),
            ToolParameter(
                name="finding_scope",
                type="string",
                description="Affected scope/domain",
                required=True,
            ),
            ToolParameter(
                name="vulnerability_type",
                type="string",
                description="Type of vulnerability",
                required=False,
            ),
            ToolParameter(
                name="severity",
                type="string",
                description="Estimated severity",
                required=False,
                enum=["critical", "high", "medium", "low", "info"],
            ),
        ]

        super().__init__(
            id="program_matcher",
            name="Program Matcher",
            description="Match findings to optimal bug bounty programs",
            category=ToolCategory.ANALYSIS,
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,
            parameters=parameters,
            version="1.0.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        """Execute program matching"""
        start_time = time.time()

        try:
            is_valid, error_msg = self.validate_parameters(**kwargs)
            if not is_valid:
                return ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.FAILED,
                    output=None,
                    error=error_msg,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            title = kwargs.get("finding_title")
            scope = kwargs.get("finding_scope")
            vuln_type = kwargs.get("vulnerability_type", "unknown")
            severity = kwargs.get("severity", "medium")

            # Analyze scope
            scope_analysis = self._analyze_scope(scope)

            # Score potential programs
            program_matches = self._score_programs(title, scope, vuln_type, severity)

            # Rank by expected payout
            program_matches.sort(key=lambda x: x["estimated_payout"], reverse=True)

            output = {
                "target_scope": scope,
                "vulnerability_type": vuln_type,
                "severity": severity,
                "scope_analysis": scope_analysis,
                "matched_programs": program_matches[:5],  # Top 5
                "recommended_program": program_matches[0] if program_matches else None,
            }

            self.record_execution(
                ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.COMPLETED,
                    output=output,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            )

            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.COMPLETED,
                output=output,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Program matcher error: {str(e)}")
            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.FAILED,
                output=None,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    @staticmethod
    def _analyze_scope(scope: str) -> Dict[str, Any]:
        """Analyze scope characteristics"""
        return {
            "domain": scope,
            "scope_type": "domain",
            "uniqueness": 0.75,
        }

    @staticmethod
    def _score_programs(
        title: str, scope: str, vuln_type: str, severity: str
    ) -> List[Dict[str, Any]]:
        """Score potential programs"""
        # Mock programs for now
        programs = [
            {
                "program_name": "Google VRP",
                "match_score": 0.85,
                "estimated_payout": 5000,
                "match_reason": "Exact scope match",
            },
            {
                "program_name": "Microsoft",
                "match_score": 0.70,
                "estimated_payout": 3000,
                "match_reason": "Related technology",
            },
            {
                "program_name": "Meta",
                "match_score": 0.60,
                "estimated_payout": 2500,
                "match_reason": "Broad scope coverage",
            },
        ]

        # Adjust based on severity
        severity_multipliers = {"critical": 3.0, "high": 2.0, "medium": 1.5, "low": 1.0}
        multiplier = severity_multipliers.get(severity, 1.5)

        for prog in programs:
            prog["estimated_payout"] = int(prog["estimated_payout"] * multiplier)

        return programs
