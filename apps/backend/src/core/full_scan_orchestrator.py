"""
Full Scan Orchestrator
Autonomous end-to-end workflow from BBP selection through scanning and reporting
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ScanPhase(str, Enum):
    """Phases of full scan workflow"""
    PROGRAM_SELECTION = "program_selection"
    AUTHORIZATION_CHECK = "authorization_check"
    RECONNAISSANCE = "reconnaissance"
    VULNERABILITY_SCAN = "vulnerability_scan"
    ANALYSIS = "analysis"
    REPAIR = "repair"
    VALIDATION = "validation"
    REPORTING = "reporting"
    STAKEHOLDER_COMMUNICATION = "stakeholder_communication"
    COMPLETED = "completed"


class ScanStatus(str, Enum):
    """Status of scan"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PhaseResult:
    """Result from a scan phase"""
    phase: ScanPhase
    status: ScanStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    findings_count: int = 0
    cost_cents: int = 0
    output: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class FullScanResult:
    """Complete result from full scan"""
    scan_id: str
    program_id: str
    program_name: str
    target: str
    status: ScanStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    phases: List[PhaseResult] = field(default_factory=list)
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    total_cost_cents: int = 0
    estimated_payout_cents: int = 0
    stakeholder_notified: bool = False
    final_report_path: Optional[str] = None


class FullScanOrchestrator:
    """
    Full Scan Orchestrator

    Coordinates autonomous end-to-end scanning workflow:
    1. Program Selection (user initiates or autonomous)
    2. Authorization Check (verify scope, permission slips)
    3. Reconnaissance (OSINT, subdomain discovery)
    4. Vulnerability Scanning (nuclei, custom tools)
    5. Analysis (reasoning agent, severity assessment)
    6. Repair (auto-generate fixes for discovered vulnerabilities)
    7. Validation (verify fixes work)
    8. Reporting (generate comprehensive report)
    9. Stakeholder Communication (email findings to program contacts)
    """

    def __init__(self):
        """Initialize full scan orchestrator"""
        # Import dependencies
        from .autonomous_bbp_selector import get_bbp_selector
        from .repair_pipeline import get_repair_pipeline
        from .budget_tracker import get_budget_tracker
        from ..integrations.notification_service import get_notification_service

        self.bbp_selector = get_bbp_selector()
        self.repair_pipeline = get_repair_pipeline()
        self.budget_tracker = get_budget_tracker()
        self.notification_service = get_notification_service()

        # Active scans
        self.active_scans: Dict[str, FullScanResult] = {}

        logger.info("✓ FullScanOrchestrator initialized")

    async def initiate_autonomous_scan(
        self,
        user_id: str,
        budget_cents: int = 10000,  # $100 default
        max_programs: int = 3,
        notify_stakeholders: bool = True
    ) -> FullScanResult:
        """
        User initiates autonomous scanning workflow

        Platform will:
        1. Select optimal BBP programs
        2. Execute full scan on each
        3. Generate reports
        4. Notify stakeholders (if enabled)

        Args:
            user_id: User initiating scan
            budget_cents: Budget allocation for scanning
            max_programs: Maximum programs to scan
            notify_stakeholders: Whether to email findings to programs

        Returns:
            FullScanResult with comprehensive results
        """

        scan_id = str(uuid.uuid4())
        logger.info(f"Initiating autonomous scan {scan_id} for user {user_id}")

        # Phase 1: Program Selection
        logger.info("Phase 1: Selecting optimal BBP programs")

        # Get available programs (would come from programs router)
        available_programs = await self._fetch_available_programs()

        selection_result = await self.bbp_selector.analyze_and_select(
            available_programs=available_programs,
            max_programs=max_programs,
            budget_cents=budget_cents
        )

        logger.info(f"Selected {len(selection_result.selected_programs)} programs")
        logger.info(f"Reasoning: {selection_result.reasoning}")

        # Execute scan for each selected program
        scan_results = []
        for program_score in selection_result.selected_programs:
            result = await self.execute_full_scan(
                program_id=program_score.program_id,
                program_name=program_score.program_name,
                user_id=user_id,
                budget_cents=program_score.estimated_cost_cents,
                notify_stakeholders=notify_stakeholders
            )
            scan_results.append(result)

        # Return summary (for now, just return first scan)
        # TODO: Aggregate multiple scan results
        return scan_results[0] if scan_results else None

    async def execute_full_scan(
        self,
        program_id: str,
        program_name: str,
        user_id: str,
        budget_cents: int = 10000,
        notify_stakeholders: bool = True
    ) -> FullScanResult:
        """
        Execute full scan on a specific program

        Args:
            program_id: BBP program ID
            program_name: BBP program name
            user_id: User initiating scan
            budget_cents: Budget for this scan
            notify_stakeholders: Whether to notify program contacts

        Returns:
            FullScanResult with all findings and reports
        """

        scan_id = str(uuid.uuid4())
        session_id = f"scan_{scan_id}"

        # Create scan result
        scan_result = FullScanResult(
            scan_id=scan_id,
            program_id=program_id,
            program_name=program_name,
            target="",  # Will be set from program scope
            status=ScanStatus.IN_PROGRESS,
            started_at=datetime.utcnow()
        )

        self.active_scans[scan_id] = scan_result

        try:
            # Get program details
            program = await self._get_program_details(program_id)
            target = self._extract_primary_target(program)
            scan_result.target = target

            logger.info(f"Starting full scan {scan_id} for {program_name} ({target})")

            # Phase 1: Authorization Check
            auth_phase = await self._phase_authorization_check(
                scan_id, program, user_id
            )
            scan_result.phases.append(auth_phase)

            if auth_phase.status == ScanStatus.FAILED:
                scan_result.status = ScanStatus.FAILED
                return scan_result

            # Phase 2: Reconnaissance
            recon_phase = await self._phase_reconnaissance(
                scan_id, target, session_id
            )
            scan_result.phases.append(recon_phase)
            scan_result.total_cost_cents += recon_phase.cost_cents

            # Phase 3: Vulnerability Scanning
            vuln_phase = await self._phase_vulnerability_scan(
                scan_id, target, session_id
            )
            scan_result.phases.append(vuln_phase)
            scan_result.total_cost_cents += vuln_phase.cost_cents

            # Phase 4: Analysis
            analysis_phase = await self._phase_analysis(
                scan_id, vuln_phase.output, session_id
            )
            scan_result.phases.append(analysis_phase)
            scan_result.total_cost_cents += analysis_phase.cost_cents

            # Extract findings counts
            findings = analysis_phase.output.get("findings", [])
            scan_result.total_findings = len(findings)
            scan_result.critical_findings = sum(1 for f in findings if f.get("severity") == "critical")
            scan_result.high_findings = sum(1 for f in findings if f.get("severity") == "high")
            scan_result.medium_findings = sum(1 for f in findings if f.get("severity") == "medium")
            scan_result.low_findings = sum(1 for f in findings if f.get("severity") == "low")

            # Phase 5: Repair (optional, only for high/critical)
            if scan_result.critical_findings > 0 or scan_result.high_findings > 0:
                repair_phase = await self._phase_repair(
                    scan_id, findings, target, session_id
                )
                scan_result.phases.append(repair_phase)
                scan_result.total_cost_cents += repair_phase.cost_cents

            # Phase 6: Reporting
            report_phase = await self._phase_reporting(
                scan_id, program, scan_result
            )
            scan_result.phases.append(report_phase)
            scan_result.final_report_path = report_phase.output.get("report_path")

            # Phase 7: Stakeholder Communication
            if notify_stakeholders and scan_result.total_findings > 0:
                comm_phase = await self._phase_stakeholder_communication(
                    scan_id, program, scan_result
                )
                scan_result.phases.append(comm_phase)
                scan_result.stakeholder_notified = True

            # Mark as completed
            scan_result.status = ScanStatus.COMPLETED
            scan_result.completed_at = datetime.utcnow()

            logger.info(f"✓ Full scan {scan_id} completed")
            logger.info(f"Findings: {scan_result.total_findings} total, {scan_result.critical_findings} critical")
            logger.info(f"Total cost: ${scan_result.total_cost_cents/100:.2f}")

            return scan_result

        except Exception as e:
            logger.error(f"Full scan {scan_id} failed: {str(e)}")
            scan_result.status = ScanStatus.FAILED
            scan_result.completed_at = datetime.utcnow()
            return scan_result

    async def _fetch_available_programs(self) -> List[Dict[str, Any]]:
        """Fetch available BBP programs"""
        # TODO: Call programs API
        # For now, return mock data
        return [
            {
                "id": "program1",
                "slug": "example-corp",
                "name": "Example Corp Bug Bounty",
                "platform": "hackerone",
                "max_payout": 10000,
                "min_payout": 100,
                "scope": ["*.example.com", "api.example.com"],
                "vuln_types": ["sql_injection", "xss", "csrf"],
                "target_types": ["web", "api"],
                "company_size": "medium"
            }
        ]

    async def _get_program_details(self, program_id: str) -> Dict[str, Any]:
        """Get program details"""
        # TODO: Call programs API
        return {
            "id": program_id,
            "name": "Example Program",
            "scope": ["*.example.com"],
            "contact_email": "security@example.com",
            "policy_url": "https://example.com/security"
        }

    def _extract_primary_target(self, program: Dict[str, Any]) -> str:
        """Extract primary target from program scope"""
        scope = program.get("scope", [])
        if scope and isinstance(scope, list):
            return scope[0].replace("*.", "")
        return "example.com"

    async def _phase_authorization_check(
        self,
        scan_id: str,
        program: Dict[str, Any],
        user_id: str
    ) -> PhaseResult:
        """Phase: Check authorization and scope"""

        started_at = datetime.utcnow()
        logger.info(f"[{scan_id}] Phase: Authorization Check")

        # Check if target is in authorized scope
        # Check permission slips
        # TODO: Implement actual authorization check

        # Simulate authorization check
        await asyncio.sleep(1)

        authorized = True  # Placeholder

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        return PhaseResult(
            phase=ScanPhase.AUTHORIZATION_CHECK,
            status=ScanStatus.COMPLETED if authorized else ScanStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            output={"authorized": authorized},
            errors=[] if authorized else ["Target not authorized"]
        )

    async def _phase_reconnaissance(
        self,
        scan_id: str,
        target: str,
        session_id: str
    ) -> PhaseResult:
        """Phase: Reconnaissance (OSINT)"""

        started_at = datetime.utcnow()
        logger.info(f"[{scan_id}] Phase: Reconnaissance on {target}")

        # Execute reconnaissance using OSINTAgent
        # TODO: Implement actual reconnaissance

        # Simulate reconnaissance
        await asyncio.sleep(2)

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        return PhaseResult(
            phase=ScanPhase.RECONNAISSANCE,
            status=ScanStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            findings_count=0,
            cost_cents=0,  # Local models only
            output={
                "subdomains": ["www.example.com", "api.example.com", "mail.example.com"],
                "open_ports": [80, 443, 22],
                "technologies": ["nginx", "php", "mysql"]
            }
        )

    async def _phase_vulnerability_scan(
        self,
        scan_id: str,
        target: str,
        session_id: str
    ) -> PhaseResult:
        """Phase: Vulnerability Scanning"""

        started_at = datetime.utcnow()
        logger.info(f"[{scan_id}] Phase: Vulnerability Scan on {target}")

        # Execute vulnerability scanning
        # Use nuclei, custom scanners
        # TODO: Implement actual scanning

        # Simulate scanning
        await asyncio.sleep(3)

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        return PhaseResult(
            phase=ScanPhase.VULNERABILITY_SCAN,
            status=ScanStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            findings_count=5,
            cost_cents=0,  # Local scanning
            output={
                "raw_findings": [
                    {"type": "sql_injection", "url": "https://example.com/login", "param": "username"},
                    {"type": "xss", "url": "https://example.com/search", "param": "q"},
                    {"type": "csrf", "url": "https://example.com/profile", "param": "action"}
                ]
            }
        )

    async def _phase_analysis(
        self,
        scan_id: str,
        scan_output: Dict[str, Any],
        session_id: str
    ) -> PhaseResult:
        """Phase: Analysis and Severity Assessment"""

        started_at = datetime.utcnow()
        logger.info(f"[{scan_id}] Phase: Analysis")

        # Use ReasoningAgent to analyze findings
        # Calculate CVSS scores, exploitability
        # TODO: Implement actual analysis

        # Simulate analysis (with paid API cost for complex findings)
        await asyncio.sleep(2)

        raw_findings = scan_output.get("raw_findings", [])
        analyzed_findings = []

        for finding in raw_findings:
            analyzed_findings.append({
                "id": str(uuid.uuid4()),
                "type": finding["type"],
                "url": finding["url"],
                "param": finding.get("param"),
                "severity": "high" if finding["type"] == "sql_injection" else "medium",
                "cvss": 8.5 if finding["type"] == "sql_injection" else 6.0,
                "exploitability": "high",
                "description": f"{finding['type']} vulnerability found"
            })

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        # Cost: $0.30 for analysis of complex findings
        cost_cents = 30

        return PhaseResult(
            phase=ScanPhase.ANALYSIS,
            status=ScanStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            findings_count=len(analyzed_findings),
            cost_cents=cost_cents,
            output={"findings": analyzed_findings}
        )

    async def _phase_repair(
        self,
        scan_id: str,
        findings: List[Dict[str, Any]],
        target: str,
        session_id: str
    ) -> PhaseResult:
        """Phase: Repair (generate fixes)"""

        started_at = datetime.utcnow()
        logger.info(f"[{scan_id}] Phase: Repair")

        # Use repair pipeline to generate fixes
        # Only for high/critical findings
        high_critical = [f for f in findings if f.get("severity") in ["high", "critical"]]

        logger.info(f"Generating repairs for {len(high_critical)} high/critical findings")

        # Execute repair pipeline
        try:
            repair_result = await self.repair_pipeline.discover_and_repair(
                target=target,
                auto_repair=False,  # Don't auto-apply for BBP
                session_id=session_id
            )

            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            return PhaseResult(
                phase=ScanPhase.REPAIR,
                status=ScanStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                findings_count=repair_result.repairs_generated,
                cost_cents=repair_result.total_cost_cents,
                output={
                    "repairs_generated": repair_result.repairs_generated,
                    "report": repair_result.post_review_report
                }
            )

        except Exception as e:
            logger.error(f"Repair phase failed: {str(e)}")
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            return PhaseResult(
                phase=ScanPhase.REPAIR,
                status=ScanStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                errors=[str(e)]
            )

    async def _phase_reporting(
        self,
        scan_id: str,
        program: Dict[str, Any],
        scan_result: FullScanResult
    ) -> PhaseResult:
        """Phase: Generate comprehensive report"""

        started_at = datetime.utcnow()
        logger.info(f"[{scan_id}] Phase: Reporting")

        # Generate comprehensive report
        from .report_generator import generate_bbp_report

        report_path = await generate_bbp_report(
            scan_id=scan_id,
            program=program,
            scan_result=scan_result
        )

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        return PhaseResult(
            phase=ScanPhase.REPORTING,
            status=ScanStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            output={"report_path": report_path}
        )

    async def _phase_stakeholder_communication(
        self,
        scan_id: str,
        program: Dict[str, Any],
        scan_result: FullScanResult
    ) -> PhaseResult:
        """Phase: Communicate findings to program stakeholders"""

        started_at = datetime.utcnow()
        logger.info(f"[{scan_id}] Phase: Stakeholder Communication")

        # Send findings to program contact
        from .stakeholder_communicator import send_findings_to_program

        success = await send_findings_to_program(
            program=program,
            scan_result=scan_result,
            notification_service=self.notification_service
        )

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        return PhaseResult(
            phase=ScanPhase.STAKEHOLDER_COMMUNICATION,
            status=ScanStatus.COMPLETED if success else ScanStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            output={"email_sent": success}
        )

    def get_scan_status(self, scan_id: str) -> Optional[FullScanResult]:
        """Get status of active scan"""
        return self.active_scans.get(scan_id)

    def list_active_scans(self) -> List[FullScanResult]:
        """List all active scans"""
        return list(self.active_scans.values())


# Global instance
_orchestrator: Optional[FullScanOrchestrator] = None


def get_scan_orchestrator() -> FullScanOrchestrator:
    """Get global scan orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = FullScanOrchestrator()
    return _orchestrator
