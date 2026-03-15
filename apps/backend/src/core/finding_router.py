"""
K1 Finding Router
Routes findings to appropriate module based on severity and duplicate status
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
import uuid


class FindingRoute(str, Enum):
    """Where findings are routed"""
    HIL_VALIDATION = "hil_validation"  # Critical/High → Human review
    EXPLOIT_CHAINING = "exploit_chaining"  # Medium/Low → Chain with others
    DUPLICATE_SKIP = "duplicate_skip"  # Already reported
    DISCARDED = "discarded"  # Low confidence/out of scope


@dataclass
class RoutedFinding:
    """Finding with routing decision"""
    finding_id: str
    target_domain: str
    vulnerability_type: str
    cvss_score: float
    severity: str
    route: FindingRoute
    confidence_score: float  # How confident in this finding (0-1)
    routed_at: datetime = None
    reasoning: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.routed_at is None:
            self.routed_at = datetime.now(timezone.utc)
        if self.metadata is None:
            self.metadata = {}


class FindingRouter:
    """Routes findings to appropriate pipeline"""

    def __init__(self):
        self.routing_history: Dict[str, List[RoutedFinding]] = {}  # domain -> routed findings
        self.route_stats = {
            FindingRoute.HIL_VALIDATION: 0,
            FindingRoute.EXPLOIT_CHAINING: 0,
            FindingRoute.DUPLICATE_SKIP: 0,
            FindingRoute.DISCARDED: 0
        }

    async def route_finding(
        self,
        target_domain: str,
        vulnerability_type: str,
        endpoint: str,
        cvss_score: float,
        severity: str,
        confidence_score: float,
        is_duplicate: bool = False,
        duplicate_reason: Optional[str] = None,
        chainable_with: Optional[List[str]] = None
    ) -> RoutedFinding:
        """Route single finding to appropriate module"""

        finding_id = f"finding_{uuid.uuid4().hex[:8]}"
        reasoning = ""

        # Step 1: Check if duplicate
        if is_duplicate:
            route = FindingRoute.DUPLICATE_SKIP
            reasoning = f"Duplicate: {duplicate_reason}"
        # Step 2: Check confidence threshold
        elif confidence_score < 0.5:
            route = FindingRoute.DISCARDED
            reasoning = f"Low confidence score ({confidence_score:.2f})"
        # Step 3: Route by severity
        elif severity.lower() in ["critical", "high"]:
            route = FindingRoute.HIL_VALIDATION
            reasoning = f"{severity} severity finding requires HiL approval"
        elif severity.lower() in ["medium", "low", "average"]:
            # Can these be chained?
            if chainable_with:
                route = FindingRoute.EXPLOIT_CHAINING
                reasoning = f"{severity} severity → chainable with {len(chainable_with)} other findings"
            else:
                route = FindingRoute.EXPLOIT_CHAINING
                reasoning = f"{severity} severity → attempt exploit chaining to increase impact"
        else:
            route = FindingRoute.DISCARDED
            reasoning = f"Unknown severity: {severity}"

        routed = RoutedFinding(
            finding_id=finding_id,
            target_domain=target_domain,
            vulnerability_type=vulnerability_type,
            cvss_score=cvss_score,
            severity=severity,
            route=route,
            confidence_score=confidence_score,
            reasoning=reasoning,
            metadata={
                "endpoint": endpoint,
                "chainable_with": chainable_with or []
            }
        )

        # Track routing
        if target_domain not in self.routing_history:
            self.routing_history[target_domain] = []
        self.routing_history[target_domain].append(routed)

        # Update stats
        self.route_stats[route] += 1

        return routed

    async def route_batch(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[RoutedFinding]:
        """Route multiple findings"""
        routed = []
        for finding in findings:
            routed_finding = await self.route_finding(
                target_domain=finding.get("target_domain"),
                vulnerability_type=finding.get("vulnerability_type"),
                endpoint=finding.get("endpoint"),
                cvss_score=finding.get("cvss_score", 5.0),
                severity=finding.get("severity", "medium"),
                confidence_score=finding.get("confidence_score", 0.7),
                is_duplicate=finding.get("is_duplicate", False),
                duplicate_reason=finding.get("duplicate_reason"),
                chainable_with=finding.get("chainable_with")
            )
            routed.append(routed_finding)

        return routed

    def get_findings_for_hil_validation(self) -> List[RoutedFinding]:
        """Get findings awaiting HiL validation"""
        findings = []
        for domain_findings in self.routing_history.values():
            findings.extend([
                f for f in domain_findings
                if f.route == FindingRoute.HIL_VALIDATION
            ])
        return findings

    def get_findings_for_chaining(self) -> List[RoutedFinding]:
        """Get findings for exploit chaining"""
        findings = []
        for domain_findings in self.routing_history.values():
            findings.extend([
                f for f in domain_findings
                if f.route == FindingRoute.EXPLOIT_CHAINING
            ])
        return findings

    def get_duplicate_findings(self) -> List[RoutedFinding]:
        """Get findings marked as duplicates"""
        findings = []
        for domain_findings in self.routing_history.values():
            findings.extend([
                f for f in domain_findings
                if f.route == FindingRoute.DUPLICATE_SKIP
            ])
        return findings

    def get_findings_by_domain(self, domain: str) -> List[RoutedFinding]:
        """Get all routed findings for domain"""
        return self.routing_history.get(domain, [])

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics"""
        total = sum(self.route_stats.values())
        return {
            "total_findings_routed": total,
            "hil_validation": {
                "count": self.route_stats[FindingRoute.HIL_VALIDATION],
                "percentage": (self.route_stats[FindingRoute.HIL_VALIDATION] / total * 100) if total > 0 else 0
            },
            "exploit_chaining": {
                "count": self.route_stats[FindingRoute.EXPLOIT_CHAINING],
                "percentage": (self.route_stats[FindingRoute.EXPLOIT_CHAINING] / total * 100) if total > 0 else 0
            },
            "duplicate_skip": {
                "count": self.route_stats[FindingRoute.DUPLICATE_SKIP],
                "percentage": (self.route_stats[FindingRoute.DUPLICATE_SKIP] / total * 100) if total > 0 else 0
            },
            "discarded": {
                "count": self.route_stats[FindingRoute.DISCARDED],
                "percentage": (self.route_stats[FindingRoute.DISCARDED] / total * 100) if total > 0 else 0
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "domains_processed": len(self.routing_history),
            "stats": self.get_routing_stats()
        }


# Global instance
finding_router = None


def initialize_finding_router() -> FindingRouter:
    """Initialize finding router"""
    global finding_router

    finding_router = FindingRouter()
    print("✓ Finding router initialized")

    return finding_router
