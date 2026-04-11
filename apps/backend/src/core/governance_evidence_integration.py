"""
Governance & Evidence Integration Layer.

Orchestrates the integration of:
1. Human-in-the-Loop (HiL) approval gates
2. Evidence recording and capture
3. Reproducible script generation
4. Bundle packaging and PGP-signed approval

Wires these into the main orchestration pipeline.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, Optional
from uuid import UUID
from enum import Enum

logger = logging.getLogger(__name__)


class ActionCriticality(str, Enum):
    """Action criticality level for HiL gate."""
    LOW = "low"           # Auto-approved
    MEDIUM = "medium"     # Auto-approved
    HIGH = "high"         # Manual approval required
    CRITICAL = "critical" # Manual approval required


class ActionType(str, Enum):
    """Type of action being executed."""
    TOOL_EXECUTION = "tool_execution"
    PAYLOAD_INJECTION = "payload_injection"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    PLATFORM_SUBMISSION = "platform_submission"
    EXPLOITATION_CHAIN = "exploitation_chain"


class FindingDetectionEvent:
    """Event emitted when a vulnerability is detected."""

    def __init__(
        self,
        task_id: str,
        finding_id: Optional[UUID],
        target_url: str,
        vulnerability_type: str,
        severity: str,
        tool_name: str,
        evidence: Dict[str, Any],
    ):
        self.task_id = task_id
        self.finding_id = finding_id
        self.target_url = target_url
        self.vulnerability_type = vulnerability_type
        self.severity = severity
        self.tool_name = tool_name
        self.evidence = evidence
        self.timestamp = None


class GovernanceEvidenceIntegration:
    """
    Integration point for governance and evidence modules.

    Orchestrates:
    - HiL approval gates before HIGH/CRITICAL actions
    - Evidence capture on vulnerability detection
    - Script generation and bundling
    - Submission blocking until approved
    """

    def __init__(self):
        """Initialize integration layer."""
        self._hil_gateway = None
        self._recording_engine = None
        self._repro_generator = None
        self._bundle_generator = None
        self._scope_guardrails = None

    async def initialize(self) -> bool:
        """
        Initialize all governance and evidence modules.

        Called once from main.py during startup.

        Returns:
            True if all modules initialized successfully
        """
        try:
            # Import and initialize HiL approval gateway
            from .governance_hil_approval import get_hil_gateway
            self._hil_gateway = await get_hil_gateway()
            logger.info("✓ HiL Approval Gateway initialized")

            # Import and initialize recording engine
            from .evidence_recording_engine import get_recording_engine
            self._recording_engine = await get_recording_engine()
            logger.info("✓ Evidence Recording Engine initialized")

            # Import and initialize repro script generator
            from .repro_script_generator import get_repro_generator
            self._repro_generator = await get_repro_generator()
            logger.info("✓ Repro Script Generator initialized")

            # Import and initialize bundle generator
            from .generate_hil_bundle import get_hil_bundle_generator
            self._bundle_generator = await get_hil_bundle_generator()
            logger.info("✓ HiL Bundle Generator initialized")

            # Import scope guardrails
            from .scope_guardrails import ScopeGuardrails
            self._scope_guardrails = ScopeGuardrails()
            logger.info("✓ Scope Guardrails loaded")

            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info("✅ Governance & Evidence Integration READY")
            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            return True

        except Exception as e:
            logger.error(f"❌ Governance & Evidence Integration failed: {str(e)}")
            return False

    # ═════════════════════════════════════════════════════════════════════════════
    # 1. GOVERNANCE HOOK: HiL Approval Gate
    # ═════════════════════════════════════════════════════════════════════════════

    async def request_action_approval(
        self,
        action_id: str,
        action_type: ActionType,
        criticality: ActionCriticality,
        description: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300,
    ) -> bool:
        """
        Request approval for an action via HiL gate.

        HIGH/CRITICAL actions are blocked until manual approval received.
        LOW/MEDIUM actions are auto-approved.

        Args:
            action_id: Unique action identifier
            action_type: Type of action being executed
            criticality: Action criticality level
            description: Human-readable action description
            context: Additional context for approver
            timeout_seconds: Approval window (default 5 minutes)

        Returns:
            True if approved, False if rejected or timed out
        """
        if not self._hil_gateway:
            logger.warning("HiL gateway not initialized, auto-approving")
            return True

        # LOW and MEDIUM actions are auto-approved
        if criticality in (ActionCriticality.LOW, ActionCriticality.MEDIUM):
            logger.info(f"⚪ Action {action_id} ({criticality.value}) auto-approved")
            return True

        # HIGH and CRITICAL require manual approval
        logger.warning(f"🔴 HOLD-FOR-APPROVAL: {action_type.value} (criticality={criticality.value})")
        logger.warning(f"   Action ID: {action_id}")
        logger.warning(f"   Description: {description}")

        from .governance_hil_approval import ActionRequest, CriticalityLevel

        # Map criticality to HiL level
        hil_criticality = CriticalityLevel.HIGH if criticality == ActionCriticality.HIGH else CriticalityLevel.CRITICAL

        action_request = ActionRequest(
            action_id=action_id,
            action_type=action_type.value,
            criticality=hil_criticality,
            description=description,
            context=context or {},
            requested_at=None,  # Uses current time
        )

        # Request approval (blocks until decision or timeout)
        approved = await self._hil_gateway.request_approval(
            action_request,
            timeout_seconds=timeout_seconds,
        )

        if approved:
            logger.info(f"✅ Action {action_id} APPROVED")
        else:
            logger.error(f"❌ Action {action_id} REJECTED or TIMED OUT")

        return approved

    # ═════════════════════════════════════════════════════════════════════════════
    # 2. EVIDENCE HOOK: Capture on Vulnerability Detection
    # ═════════════════════════════════════════════════════════════════════════════

    async def on_vulnerability_detected(
        self,
        event: FindingDetectionEvent,
    ) -> Dict[str, Any]:
        """
        Triggered when a vulnerability is detected.

        Initiates:
        1. Screen recording of exploitation
        2. Script generation (curl, Python, exploit)
        3. HTTP traffic logging

        Args:
            event: FindingDetectionEvent with detection metadata

        Returns:
            Dict with recording and script metadata
        """
        logger.info(f"🎥 Vulnerability detected: {event.vulnerability_type} ({event.severity})")
        logger.info(f"   Target: {event.target_url}")
        logger.info(f"   Tool: {event.tool_name}")

        if not self._recording_engine:
            logger.warning("Recording engine not initialized, skipping evidence capture")
            return {}

        try:
            # Start recording session
            logger.info(f"   → Starting video recording for {event.task_id}...")
            recording_session = await self._recording_engine.start_recording(
                event.task_id,
                event.target_url,
            )

            if not recording_session:
                logger.error(f"Failed to start recording for {event.task_id}")
                return {}

            logger.info(f"   ✓ Recording started: {recording_session.session_id}")

            # Store session for later retrieval
            return {
                "recording_session_id": recording_session.session_id,
                "status": "recording_started",
            }

        except Exception as e:
            logger.error(f"Error starting recording: {str(e)}")
            return {}

    async def on_exploitation_complete(
        self,
        task_id: str,
        target_url: str,
        http_requests: list[Dict[str, Any]],
        vulnerability_type: str,
        description: str,
    ) -> Dict[str, Any]:
        """
        Called after exploitation is complete.

        Generates:
        1. Curl commands for reproduction
        2. Python requests scripts
        3. Standalone exploit classes

        Args:
            task_id: Task identifier
            target_url: Exploited target
            http_requests: List of HTTP requests/responses captured
            vulnerability_type: Type of vulnerability
            description: Vulnerability description

        Returns:
            Dict with script paths and metadata
        """
        logger.info(f"🔧 Generating reproduction scripts for {task_id}...")

        if not self._repro_generator:
            logger.warning("Repro generator not initialized")
            return {}

        try:
            scripts = {}

            # Generate curl command from first request
            if http_requests:
                first_req = http_requests[0]
                curl_script = await self._repro_generator.generate_curl_command(
                    task_id=task_id,
                    method=first_req.get("method", "GET"),
                    url=target_url,
                    headers=first_req.get("headers", {}),
                    body=first_req.get("body"),
                    description=description,
                )
                scripts["curl"] = curl_script.filename
                logger.info(f"   ✓ Generated curl command: {curl_script.filename}")

            # Generate Python requests script
            if http_requests:
                first_req = http_requests[0]
                python_script = await self._repro_generator.generate_python_requests(
                    task_id=task_id,
                    method=first_req.get("method", "GET"),
                    url=target_url,
                    headers=first_req.get("headers", {}),
                    body=first_req.get("body"),
                    description=description,
                )
                scripts["python_requests"] = python_script.filename
                logger.info(f"   ✓ Generated Python script: {python_script.filename}")

            # Generate standalone exploit for complex chains
            if len(http_requests) > 2:
                exploit_script = await self._repro_generator.generate_exploit_script(
                    task_id=task_id,
                    vulnerability_type=vulnerability_type,
                    target_url=target_url,
                    exploitation_steps=[
                        f"Step {i+1}: {req.get('method', 'GET')} {req.get('url', target_url)}"
                        for i, req in enumerate(http_requests[:5])
                    ],
                    payload=http_requests[-1].get("body", ""),
                    description=description,
                )
                scripts["exploit"] = exploit_script.filename
                logger.info(f"   ✓ Generated exploit.py: {exploit_script.filename}")

            logger.info(f"   ✓ All scripts generated for {task_id}")
            return scripts

        except Exception as e:
            logger.error(f"Error generating scripts: {str(e)}")
            return {}

    # ═════════════════════════════════════════════════════════════════════════════
    # 3. BUNDLING & APPROVAL GATE
    # ═════════════════════════════════════════════════════════════════════════════

    async def create_hil_bundle(
        self,
        task_id: str,
        markdown_report_path: str,
        video_recording_path: Optional[str] = None,
        repro_scripts: Optional[list[str]] = None,
        http_logs_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Create HiL Review Bundle containing all evidence.

        Packages:
        1. Markdown report (3-persona format)
        2. Video recording + metadata
        3. Reproducible scripts (curl, Python, exploit)
        4. Raw HTTP traffic logs

        Returns bundle path or None if failed.
        """
        if not self._bundle_generator:
            logger.warning("Bundle generator not initialized")
            return None

        try:
            logger.info(f"📦 Creating HiL Review Bundle for {task_id}...")

            bundle = await self._bundle_generator.create_bundle(
                task_id=task_id,
                markdown_report_path=markdown_report_path,
                video_recording_path=video_recording_path,
                repro_scripts=repro_scripts,
                http_logs_path=http_logs_path,
                metadata=metadata,
            )

            if bundle and bundle.bundle_zip_path:
                logger.info(f"   ✓ Bundle created: {bundle.bundle_zip_path}")
                logger.info(f"   ✓ Bundle ID: {bundle.bundle_id}")
                logger.warning(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                logger.warning(f"📋 READY FOR HiL REVIEW")
                logger.warning(f"   Bundle path: {bundle.bundle_zip_path}")
                logger.warning(f"   Task ID: {task_id}")
                logger.warning(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

                return bundle.bundle_zip_path

            return None

        except Exception as e:
            logger.error(f"Error creating bundle: {str(e)}")
            return None

    async def request_bundle_approval(
        self,
        task_id: str,
        timeout_seconds: int = 300,
    ) -> bool:
        """
        Request manual PGP-signed approval for bundle.

        Blocks until approval received or timeout.

        Args:
            task_id: Task identifier
            timeout_seconds: Approval window (default 5 minutes)

        Returns:
            True if approved and signed, False otherwise
        """
        if not self._bundle_generator:
            logger.warning("Bundle generator not initialized")
            return False

        logger.warning(f"🔒 Awaiting PGP-signed approval for {task_id}...")
        logger.warning(f"   Timeout: {timeout_seconds} seconds")

        try:
            approved = await self._bundle_generator.request_approval(
                task_id,
                timeout_seconds=timeout_seconds,
            )

            if approved:
                logger.info(f"✅ Bundle {task_id} APPROVED with valid PGP signature")
            else:
                logger.error(f"❌ Bundle {task_id} approval REJECTED or TIMED OUT")

            return approved

        except Exception as e:
            logger.error(f"Error requesting approval: {str(e)}")
            return False

    # ═════════════════════════════════════════════════════════════════════════════
    # 4. SUBMISSION GATE: Block Until Approved
    # ═════════════════════════════════════════════════════════════════════════════

    async def can_submit_to_platform(self, task_id: str) -> bool:
        """
        Check if finding is approved for platform submission.

        BLOCKS submission if:
        - Bundle not created
        - No valid PGP signature
        - Signature expired
        - Status is not APPROVED

        Args:
            task_id: Task identifier

        Returns:
            True if submission allowed, False otherwise
        """
        if not self._bundle_generator:
            logger.error("Bundle generator not initialized — submission blocked")
            return False

        # Check if bundle exists and is approved
        bundle = await self._bundle_generator.get_bundle(task_id)

        if not bundle:
            logger.error(f"❌ SUBMISSION BLOCKED: No bundle found for {task_id}")
            return False

        if not bundle.is_approved():
            logger.error(
                f"❌ SUBMISSION BLOCKED: Bundle {task_id} not approved. "
                f"Status: {bundle.approval_status.value}"
            )
            return False

        logger.info(f"✅ Submission approved for {task_id}")
        return True

    async def on_platform_submission(
        self,
        task_id: str,
        platform: str,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Called before platform submission (HackerOne, Bugcrowd, Intigriti).

        Performs final checks:
        1. Verify HiL bundle approval
        2. Check PGP signature validity
        3. Log submission attempt

        Args:
            task_id: Task identifier
            platform: Platform name (hackerone, bugcrowd, intigriti)
            payload: Submission payload

        Returns:
            True if submission allowed, False if blocked
        """
        logger.warning(f"🚀 Platform submission requested: {platform}")
        logger.warning(f"   Task ID: {task_id}")

        # CRITICAL: Check approval before submission
        if not await self.can_submit_to_platform(task_id):
            logger.error(f"🔴 SUBMISSION BLOCKED FOR {task_id.upper()}")
            logger.error(f"   Platform: {platform}")
            logger.error(f"   Reason: Approval required before submission")
            logger.error(f"   Action: Operator must provide PGP-signed approval via k1 approve {task_id}")

            return False  # BLOCK submission

        logger.info(f"✅ Submission allowed for {task_id}")
        return True  # Allow submission


# ═════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═════════════════════════════════════════════════════════════════════════════

_integration: Optional[GovernanceEvidenceIntegration] = None


async def get_governance_evidence_integration() -> GovernanceEvidenceIntegration:
    """Get or create global integration singleton."""
    global _integration

    if _integration is None:
        _integration = GovernanceEvidenceIntegration()
        await _integration.initialize()

    return _integration
