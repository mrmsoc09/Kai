"""
K1-Specific Agent Zero Customization
Deep integration tailored for autonomous vulnerability discovery
Customizes Agent Zero's capabilities for bug bounty hunting workflows
"""

import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio


class VulnerabilityIntent(str, Enum):
    """K1-specific intents for vulnerability discovery"""
    HUNT = "hunt"  # Autonomous vulnerability hunt
    ANALYZE = "analyze"  # Deep analysis of findings
    VALIDATE = "validate"  # Validate evidence
    CHAIN = "chain"  # Build attack chains
    REPORT = "generate_report"  # Create professional report
    MATCH = "match_programs"  # Match to bug bounty programs
    RANK = "rank_findings"  # Rank findings by value
    SUBMIT = "submit_finding"  # Submit to program
    ESCALATE = "escalate"  # Escalate to human


class BugBountyProgram(str, Enum):
    """Supported bug bounty platforms"""
    HACKERONE = "hackerone"
    BUGCROWD = "bugcrowd"
    INTIGRITI = "intigriti"
    YESWEHACK = "yeswehack"
    BOUNTYSOURCE = "bountysource"
    SYNACK = "synack"
    COBALT = "cobalt"
    BUGBOUNTY = "bugbounty.jp"


@dataclass
class K1VulnerabilityHunt:
    """K1-customized vulnerability hunt workflow"""
    hunt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target: str = ""
    target_type: str = "domain"  # domain, ip, range, app
    scope: Dict[str, Any] = field(default_factory=dict)

    # Hunting parameters
    automation_level: int = 3  # 0-3, higher = more automated
    concurrent_agents: int = 4  # How many agents work simultaneously
    prioritize_high_value: bool = True  # Find high-payout vulnerabilities first

    # Bug bounty specific
    target_programs: List[BugBountyProgram] = field(default_factory=list)
    estimated_bounty_range: Tuple[int, int] = (0, 0)
    target_severity_levels: List[str] = field(default_factory=lambda: ["critical", "high"])

    # Workflow stages
    stages: List[str] = field(default_factory=lambda: [
        "reconnaissance",
        "vulnerability_discovery",
        "validation",
        "analysis",
        "chaining",
        "reporting",
        "submission"
    ])

    current_stage: int = 0
    stage_results: Dict[str, Any] = field(default_factory=dict)

    # Quality metrics
    minimum_confidence: float = 0.75
    evidence_requirement: str = "high"  # low, medium, high
    require_poc: bool = True

    # Timeline
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Status tracking
    status: str = "pending"  # pending, in_progress, complete, error
    findings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hunt_id": self.hunt_id,
            "target": self.target,
            "target_type": self.target_type,
            "status": self.status,
            "current_stage": self.stages[self.current_stage] if self.current_stage < len(self.stages) else "complete",
            "findings_count": len(self.findings),
            "automation_level": self.automation_level,
            "estimated_bounty_range": f"${self.estimated_bounty_range[0]}-${self.estimated_bounty_range[1]}",
            "findings": self.findings
        }


@dataclass
class K1Finding:
    """K1-customized finding with bug bounty metadata"""
    finding_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    vulnerability_type: str = ""
    target: str = ""

    # Severity & impact
    severity: str = "medium"  # critical, high, medium, low, info
    cvss_score: Optional[float] = None
    owasp_category: str = ""
    cwe_id: Optional[int] = None

    # Evidence & validation
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    poc: Optional[Dict[str, str]] = None  # Proof of concept
    confidence: float = 0.0
    is_validated: bool = False
    validation_steps: List[str] = field(default_factory=list)

    # Bug bounty optimization
    estimated_bounty: int = 0
    target_programs: List[BugBountyProgram] = field(default_factory=list)
    submission_ready: bool = False
    submission_template: Optional[str] = None

    # Attack chains
    chain_id: Optional[str] = None
    chain_position: int = 0  # Position in attack chain
    required_findings: List[str] = field(default_factory=list)  # Must have these first
    enables_findings: List[str] = field(default_factory=list)  # Unlocks these findings

    # Remediation
    remediation_steps: List[str] = field(default_factory=list)
    remediation_difficulty: str = "medium"  # easy, medium, hard

    # Metadata
    discovered_by: str = "scout"  # Which agent discovered it
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    mcp_server: str = ""
    hunt_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "severity": self.severity,
            "cvss_score": self.cvss_score,
            "confidence": round(self.confidence * 100),
            "estimated_bounty": f"${self.estimated_bounty}",
            "submission_ready": self.submission_ready,
            "target_programs": [p.value for p in self.target_programs],
            "chain_id": self.chain_id
        }


class K1AgentZeroOrchestrator:
    """K1-specific Agent Zero orchestration engine

    This is the customization layer that adapts Agent Zero's
    general agent coordination to K1's specific vulnerability
    hunting needs.
    """

    def __init__(self, agent_registry, a2a_bus, mcp_manager):
        self.agent_registry = agent_registry
        self.a2a_bus = a2a_bus
        self.mcp_manager = mcp_manager
        self.hunts: Dict[str, K1VulnerabilityHunt] = {}
        self.findings: Dict[str, K1Finding] = {}
        self.bug_bounty_db = self._initialize_bounty_db()

    def _initialize_bounty_db(self) -> Dict[str, Dict]:
        """Initialize bug bounty platform database"""
        return {
            "hackerone": {
                "name": "HackerOne",
                "url": "https://hackerone.com",
                "avg_payout": 2500,
                "payout_range": (100, 50000),
                "response_time": "7-14 days",
                "acceptance_rate": 0.75,
                "api_available": True
            },
            "bugcrowd": {
                "name": "Bugcrowd",
                "url": "https://bugcrowd.com",
                "avg_payout": 1500,
                "payout_range": (100, 30000),
                "response_time": "10-20 days",
                "acceptance_rate": 0.65,
                "api_available": True
            },
            "intigriti": {
                "name": "Intigriti",
                "url": "https://intigriti.com",
                "avg_payout": 1800,
                "payout_range": (100, 40000),
                "response_time": "7-14 days",
                "acceptance_rate": 0.70,
                "api_available": True
            }
        }

    async def create_k1_hunt_workflow(
        self,
        target: str,
        target_type: str = "domain",
        scope: Dict[str, Any] = None,
        automation_level: int = 3,
        target_programs: Optional[List[str]] = None
    ) -> K1VulnerabilityHunt:
        """Create K1-customized vulnerability hunting workflow"""

        hunt = K1VulnerabilityHunt(
            target=target,
            target_type=target_type,
            scope=scope or {},
            automation_level=automation_level,
            target_programs=[BugBountyProgram(p) for p in (target_programs or [])]
        )

        self.hunts[hunt.hunt_id] = hunt

        # Estimate bounty range based on programs
        if hunt.target_programs:
            bounties = [
                self.bug_bounty_db.get(p.value, {}).get("payout_range", (0, 0))
                for p in hunt.target_programs
            ]
            if bounties:
                hunt.estimated_bounty_range = (
                    min(b[0] for b in bounties),
                    max(b[1] for b in bounties)
                )

        # Start hunt immediately if automation_level >= 2
        if automation_level >= 2:
            await self._start_reconnaissance_stage(hunt)

        return hunt

    async def _start_reconnaissance_stage(self, hunt: K1VulnerabilityHunt):
        """Start reconnaissance stage - Scout agent discovers target details"""
        hunt.status = "in_progress"
        hunt.started_at = datetime.utcnow()

        # Get Scout agent
        scouts = self.agent_registry.get_agents_by_role("scout")
        if not scouts:
            hunt.errors.append("No scout agent available")
            return

        scout = scouts[0]

        # Send reconnaissance task
        from apps.backend.src.core.agent_a2a import A2AMessage, MessageType

        message = A2AMessage(
            sender_id="orchestrator",
            receiver_id=scout.agent_id,
            message_type=MessageType.TASK_REQUEST,
            content={
                "hunt_id": hunt.hunt_id,
                "task": "reconnaissance",
                "target": hunt.target,
                "target_type": hunt.target_type,
                "scope": hunt.scope,
                "mcp_tools": ["domain_enumeration", "subdomain_discovery", "ssl_analyzer", "header_analyzer"],
                "automation_level": hunt.automation_level
            },
            correlation_id=hunt.hunt_id,
            priority=10  # Highest priority
        )

        self.a2a_bus.publish(message)
        self.agent_registry.update_agent_status(scout.agent_id, "working", hunt.hunt_id)

    async def handle_recon_results(
        self,
        hunt_id: str,
        recon_data: Dict[str, Any]
    ):
        """Process reconnaissance results and start vulnerability discovery"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        hunt.stage_results["reconnaissance"] = recon_data
        hunt.current_stage = 1  # Move to vulnerability_discovery

        # Start vulnerability discovery stage
        # Scouts continue but now looking for vulnerabilities
        scouts = self.agent_registry.get_agents_by_role("scout")
        if scouts:
            scout = scouts[0]

            from apps.backend.src.core.agent_a2a import A2AMessage, MessageType

            message = A2AMessage(
                sender_id="orchestrator",
                receiver_id=scout.agent_id,
                message_type=MessageType.TASK_REQUEST,
                content={
                    "hunt_id": hunt.hunt_id,
                    "task": "vulnerability_discovery",
                    "target": hunt.target,
                    "recon_data": recon_data,
                    "automation_level": hunt.automation_level,
                    "use_mcp_servers": ["k1-osint", "k1-analysis"]
                },
                correlation_id=hunt.hunt_id,
                priority=9
            )

            self.a2a_bus.publish(message)

    async def handle_vulnerability_discovery(
        self,
        hunt_id: str,
        discovered_findings: List[Dict[str, Any]]
    ):
        """Process discovered vulnerabilities and initiate validation"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        # Create K1Finding objects
        for finding_data in discovered_findings:
            finding = K1Finding(
                title=finding_data.get("title"),
                description=finding_data.get("description"),
                target=hunt.target,
                severity=finding_data.get("severity", "medium"),
                confidence=finding_data.get("confidence", 0.0),
                hunt_id=hunt_id,
                evidence=[finding_data.get("evidence", {})]
            )

            self.findings[finding.finding_id] = finding
            hunt.findings.append(finding.to_dict())

        # If confidence too low, request validation
        low_confidence = [f for f in discovered_findings if f.get("confidence", 0.0) < hunt.minimum_confidence]
        if low_confidence:
            await self._request_validation(hunt_id, low_confidence)

        # Progress to analysis stage
        hunt.current_stage = 3  # analysis

    async def _request_validation(self, hunt_id: str, findings: List[Dict]):
        """Request finding validation from Validator agent"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        validators = self.agent_registry.get_agents_by_role("validator")
        if not validators:
            return

        validator = validators[0]

        from apps.backend.src.core.agent_a2a import A2AMessage, MessageType

        message = A2AMessage(
            sender_id="orchestrator",
            receiver_id=validator.agent_id,
            message_type=MessageType.TASK_REQUEST,
            content={
                "hunt_id": hunt_id,
                "task": "validate_findings",
                "findings": findings,
                "automation_level": hunt.automation_level,
                "mcp_server": "k1-validator"
            },
            correlation_id=hunt_id,
            priority=8
        )

        self.a2a_bus.publish(message)

    async def initiate_analysis_stage(self, hunt_id: str):
        """Start deep analysis of validated findings"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        hunt.current_stage = 3  # analysis

        analyzers = self.agent_registry.get_agents_by_role("analyzer")
        if not analyzers:
            return

        analyzer = analyzers[0]

        from apps.backend.src.core.agent_a2a import A2AMessage, MessageType

        message = A2AMessage(
            sender_id="orchestrator",
            receiver_id=analyzer.agent_id,
            message_type=MessageType.TASK_REQUEST,
            content={
                "hunt_id": hunt_id,
                "task": "deep_analysis",
                "findings": hunt.findings,
                "mcp_server": "k1-analysis",
                "analyze_chains": True,
                "calculate_cvss": True,
                "minimum_severity": hunt.target_severity_levels
            },
            correlation_id=hunt_id,
            priority=7
        )

        self.a2a_bus.publish(message)

    async def handle_analysis_complete(
        self,
        hunt_id: str,
        analysis_results: Dict[str, Any]
    ):
        """Process analysis and move to chaining/reporting"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        hunt.stage_results["analysis"] = analysis_results

        # If high-value findings, build chains
        if analysis_results.get("chains_found", 0) > 0:
            await self._build_attack_chains(hunt_id, analysis_results)

        # Always try to match to programs
        await self._match_to_bug_bounty_programs(hunt_id)

    async def _build_attack_chains(self, hunt_id: str, analysis_data: Dict):
        """Build attack chains from findings"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        strategists = self.agent_registry.get_agents_by_role("strategist")
        if not strategists:
            return

        strategist = strategists[0]

        from apps.backend.src.core.agent_a2a import A2AMessage, MessageType

        message = A2AMessage(
            sender_id="orchestrator",
            receiver_id=strategist.agent_id,
            message_type=MessageType.TASK_REQUEST,
            content={
                "hunt_id": hunt_id,
                "task": "build_chains",
                "findings": hunt.findings,
                "analysis_data": analysis_data,
                "mcp_server": "k1-graph",
                "target": hunt.target
            },
            correlation_id=hunt_id,
            priority=6
        )

        self.a2a_bus.publish(message)

    async def _match_to_bug_bounty_programs(self, hunt_id: str):
        """Match findings to bug bounty programs and estimate payouts"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        for finding_id, finding in self.findings.items():
            if finding.hunt_id != hunt_id:
                continue

            # Match to programs
            matched_programs = []
            max_bounty = 0

            for program_name, program_data in self.bug_bounty_db.items():
                # Simple matching: check if severity is in scope
                if finding.severity.lower() in ["critical", "high"]:
                    matched_programs.append(BugBountyProgram(program_name))
                    max_bounty = max(max_bounty, program_data["payout_range"][1])

            finding.target_programs = matched_programs
            finding.estimated_bounty = max_bounty

            # If matches found and validated, mark as submission ready
            if matched_programs and finding.is_validated and finding.confidence >= hunt.minimum_confidence:
                finding.submission_ready = True

    async def generate_professional_reports(self, hunt_id: str):
        """Generate professional bug bounty reports"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return

        reporters = self.agent_registry.get_agents_by_role("reporter")
        if not reporters:
            return

        reporter = reporters[0]

        from apps.backend.src.core.agent_a2a import A2AMessage, MessageType

        # Group findings by program
        findings_by_program = {}
        for finding in hunt.findings:
            for program in finding.get("target_programs", []):
                if program not in findings_by_program:
                    findings_by_program[program] = []
                findings_by_program[program].append(finding)

        # Generate report for each program
        for program, findings in findings_by_program.items():
            message = A2AMessage(
                sender_id="orchestrator",
                receiver_id=reporter.agent_id,
                message_type=MessageType.TASK_REQUEST,
                content={
                    "hunt_id": hunt_id,
                    "task": "generate_report",
                    "program": program,
                    "findings": findings,
                    "report_format": "professional",
                    "include_poc": True,
                    "include_remediation": True
                },
                correlation_id=hunt_id,
                priority=5
            )

            self.a2a_bus.publish(message)

    def get_hunt_summary(self, hunt_id: str) -> Dict[str, Any]:
        """Get comprehensive hunt summary"""
        hunt = self.hunts.get(hunt_id)
        if not hunt:
            return {}

        # Calculate metrics
        critical_findings = len([f for f in hunt.findings if f.get("severity") == "critical"])
        high_findings = len([f for f in hunt.findings if f.get("severity") == "high"])
        total_bounty = sum([f.get("estimated_bounty", 0) for f in hunt.findings])
        submission_ready = len([f for f in hunt.findings if f.get("submission_ready")])

        return {
            "hunt_id": hunt.hunt_id,
            "target": hunt.target,
            "status": hunt.status,
            "duration_seconds": (datetime.utcnow() - hunt.started_at).total_seconds() if hunt.started_at else 0,
            "current_stage": hunt.stages[hunt.current_stage] if hunt.current_stage < len(hunt.stages) else "complete",
            "statistics": {
                "total_findings": len(hunt.findings),
                "critical": critical_findings,
                "high": high_findings,
                "submission_ready": submission_ready,
                "total_estimated_bounty": f"${total_bounty}"
            },
            "matched_programs": list(set(
                p for f in hunt.findings for p in f.get("target_programs", [])
            )),
            "findings": hunt.findings
        }


# Global instance
k1_orchestrator = None


def initialize_k1_orchestrator(agent_registry, a2a_bus, mcp_manager) -> K1AgentZeroOrchestrator:
    """Initialize K1-specific Agent Zero orchestrator"""
    global k1_orchestrator

    k1_orchestrator = K1AgentZeroOrchestrator(agent_registry, a2a_bus, mcp_manager)
    print("✓ K1-customized Agent Zero orchestrator initialized")

    return k1_orchestrator
