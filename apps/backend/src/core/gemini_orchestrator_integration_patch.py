"""
Integration patch for GeminiOrchestrator.

This file shows the exact modifications needed to wire Governance & Evidence
into the GeminiOrchestrator's main execution loop.

USAGE: Copy these modifications into gemini_orchestrator.py
"""

# ═════════════════════════════════════════════════════════════════════════════
# PATCH 1: Add imports at top of gemini_orchestrator.py
# ═════════════════════════════════════════════════════════════════════════════

# Add these imports after existing imports:

"""
from .governance_evidence_integration import (
    get_governance_evidence_integration,
    ActionType,
    ActionCriticality,
    FindingDetectionEvent,
)
"""


# ═════════════════════════════════════════════════════════════════════════════
# PATCH 2: Add governance integration to __init__
# ═════════════════════════════════════════════════════════════════════════════

# In GeminiOrchestrator.__init__(), add:

"""
    def __init__(self) -> None:
        # ... existing init code ...

        # Initialize governance & evidence integration
        self._governance_integration: Optional[GovernanceEvidenceIntegration] = None
"""


# ═════════════════════════════════════════════════════════════════════════════
# PATCH 3: Initialize integration in startup
# ═════════════════════════════════════════════════════════════════════════════

# In GeminiOrchestrator's initialization (after _init_vision_agent), add:

"""
    async def _init_governance_integration(self) -> None:
        '''Initialize governance and evidence integration.'''
        try:
            self._governance_integration = await get_governance_evidence_integration()
            logger.info('GeminiOrchestrator: Governance & Evidence integration ready')
        except Exception as exc:
            logger.warning(
                'GeminiOrchestrator: Governance & Evidence integration failed: %s',
                exc
            )
"""


# ═════════════════════════════════════════════════════════════════════════════
# PATCH 4: Add HiL approval check in execute()
# ═════════════════════════════════════════════════════════════════════════════

# In GeminiOrchestrator.execute(), BEFORE tool dispatch (around line 179), add:

"""
        # Check for governance gates on HIGH/CRITICAL actions
        if tools and self._governance_integration:
            # Determine criticality from context
            criticality = ActionCriticality.MEDIUM  # default
            if "criticality" in (context or {}):
                criticality_str = context["criticality"].lower()
                if criticality_str in ("high", "critical"):
                    criticality = ActionCriticality[criticality_str.upper()]

            # Request approval for HIGH/CRITICAL
            if criticality in (ActionCriticality.HIGH, ActionCriticality.CRITICAL):
                action_id = f"{session_id}_tool_execution"
                approved = await self._governance_integration.request_action_approval(
                    action_id=action_id,
                    action_type=ActionType.TOOL_EXECUTION,
                    criticality=criticality,
                    description=f"Execute tools: {', '.join(tools)}",
                    context=context,
                )

                if not approved:
                    logger.error(f'Tool execution BLOCKED: {action_id}')
                    return {
                        "task_id": session_id,
                        "status": "BLOCKED_PENDING_APPROVAL",
                        "output": f"Execution blocked pending HiL approval",
                        "tool_calls_made": [],
                    }
"""


# ═════════════════════════════════════════════════════════════════════════════
# PATCH 5: Add evidence capture hook
# ═════════════════════════════════════════════════════════════════════════════

# Add new method to GeminiOrchestrator:

"""
    async def capture_evidence_on_finding(
        self,
        task_id: str,
        target_url: str,
        vulnerability_type: str,
        severity: str,
        tool_name: str,
        evidence: dict,
    ) -> dict:
        '''Trigger evidence capture when vulnerability is detected.'''
        if not self._governance_integration:
            return {}

        event = FindingDetectionEvent(
            task_id=task_id,
            finding_id=None,
            target_url=target_url,
            vulnerability_type=vulnerability_type,
            severity=severity,
            tool_name=tool_name,
            evidence=evidence,
        )

        result = await self._governance_integration.on_vulnerability_detected(event)
        logger.info(f'Evidence capture initiated for {task_id}: {result}')
        return result
"""


# ═════════════════════════════════════════════════════════════════════════════
# USAGE IN FINDING DETECTION
# ═════════════════════════════════════════════════════════════════════════════

# In phase9_alert_case_service.py, when a finding is detected, call:

"""
from .gemini_orchestrator import get_gemini_orchestrator

# In create_alert() or equivalent method:

orchestrator = get_gemini_orchestrator()
await orchestrator.capture_evidence_on_finding(
    task_id="task_xyz789",
    target_url="https://example.com/admin",
    vulnerability_type="SQL Injection",
    severity="CRITICAL",
    tool_name="nuclei",
    evidence={
        "template_id": "sql-injection",
        "matched_text": "error in SQL",
        "request_url": "https://example.com/api/search?q=test'",
    }
)
"""


# ═════════════════════════════════════════════════════════════════════════════
# COMPLETE EXAMPLE: Full integration flow
# ═════════════════════════════════════════════════════════════════════════════

"""
# ──────────────────────────────────────────────────────────────────────────────
# 1. ORCHESTRATOR EXECUTION WITH HiL GATE
# ──────────────────────────────────────────────────────────────────────────────

async def main():
    orchestrator = get_gemini_orchestrator()

    # HIGH/CRITICAL action requires HiL approval
    result = await orchestrator.execute(
        instruction="Exploit SQL injection vulnerability",
        context={
            "criticality": "HIGH",  # Triggers HiL gate
            "target": "example.com",
        },
        tools=["custom_exploit_tool"],
        complexity_hint="COMPLEXITY_HIGH",
    )

    # If status is BLOCKED_PENDING_APPROVAL, halt execution
    if result["status"] == "BLOCKED_PENDING_APPROVAL":
        print(f"⏸️  Action blocked waiting for approval")
        # Operator must run: k1 approve {action_id}


# ──────────────────────────────────────────────────────────────────────────────
# 2. FINDING DETECTION WITH EVIDENCE CAPTURE
# ──────────────────────────────────────────────────────────────────────────────

async def on_finding_detected(finding_data):
    orchestrator = get_gemini_orchestrator()

    # Automatically start recording and script generation
    evidence = await orchestrator.capture_evidence_on_finding(
        task_id=finding_data["task_id"],
        target_url=finding_data["target_url"],
        vulnerability_type=finding_data["vuln_type"],
        severity=finding_data["severity"],
        tool_name=finding_data["tool"],
        evidence=finding_data["evidence"],
    )

    return evidence


# ──────────────────────────────────────────────────────────────────────────────
# 3. BUNDLE CREATION AND APPROVAL
# ──────────────────────────────────────────────────────────────────────────────

async def create_and_review_bundle(task_id, report_path, video_path, scripts):
    integration = await get_governance_evidence_integration()

    # Create bundle with all evidence
    bundle_path = await integration.create_hil_bundle(
        task_id=task_id,
        markdown_report_path=report_path,
        video_recording_path=video_path,
        repro_scripts=scripts,
        metadata={
            "vulnerability_type": "SQL Injection",
            "severity": "CRITICAL",
            "cvss_score": 9.8,
        }
    )

    # Request manual approval (blocks until decision)
    approved = await integration.request_bundle_approval(task_id)

    return approved


# ──────────────────────────────────────────────────────────────────────────────
# 4. PLATFORM SUBMISSION WITH APPROVAL GATE
# ──────────────────────────────────────────────────────────────────────────────

async def submit_to_platform(task_id, platform, payload):
    integration = await get_governance_evidence_integration()

    # CRITICAL CHECK: Can only submit if approved
    if not await integration.on_platform_submission(task_id, platform, payload):
        raise PermissionError(f'Submission blocked: {task_id} not approved')

    # If we reach here, submission is allowed
    # Proceed with HackerOne/Bugcrowd/Intigriti API call
    return await hackerone_client.submit_finding(payload)
"""
