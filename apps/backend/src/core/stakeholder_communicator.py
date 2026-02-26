"""
Stakeholder Communication System (DEPRECATED)

⚠️  WARNING: This module contains DEPRECATED auto-send functions.
⚠️  Platform NEVER auto-sends emails per HiL approval policy.

MIGRATION PATH:
--------------
OLD (Deprecated):
    from .stakeholder_communicator import send_findings_to_program
    await send_findings_to_program(program, scan_result, notification_service)

NEW (Correct):
    from .email_draft_generator import generate_initial_findings_draft
    from .hil_approval_system import HiLApprovalSystem

    # Generate draft
    draft = await generate_initial_findings_draft(program, scan_result)

    # Create approval request
    hil_system = HiLApprovalSystem()
    approval = await hil_system.request_report_submission_approval(
        scan_id=scan_id,
        program_id=program['id'],
        program_name=program['name'],
        report_content={'email_draft': draft, ...},
        submission_platform=program['platform']
    )

    # User reviews and approves via API
    # User manually sends email

For new code, use:
- email_draft_generator.py - Generate email drafts
- hil_approval_system.py - Manage approval workflow
- hil_approval.py (router) - API endpoints for approval management
"""

import logging
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# DEPRECATED FUNCTIONS - Use HiL Approval System Instead
# ============================================================================


async def send_findings_to_program(
    program: Dict[str, Any],
    scan_result: Any,  # FullScanResult
    notification_service: Any
) -> bool:
    """
    ⚠️  DEPRECATED: Auto-send function violates HiL approval policy.

    This function automatically sends emails, which is no longer allowed.
    Platform NEVER auto-sends emails - all communications require HiL approval.

    MIGRATION:
        Use email_draft_generator.generate_initial_findings_draft() to create
        draft, then use HiLApprovalSystem.request_report_submission_approval()
        to queue for user review.

    Args:
        program: BBP program details
        scan_result: Full scan result with findings
        notification_service: Notification service (unused in new workflow)

    Returns:
        False - Function is deprecated and does nothing
    """

    warnings.warn(
        "send_findings_to_program() is DEPRECATED and does nothing. "
        "Use HiL approval system: email_draft_generator + HiLApprovalSystem",
        DeprecationWarning,
        stacklevel=2
    )

    logger.error("⚠️  DEPRECATED: send_findings_to_program() called - function does nothing")
    logger.error("⚠️  Migrate to HiL approval system: see stakeholder_communicator.py docstring")

    return False


async def send_status_update(
    program: Dict[str, Any],
    scan_id: str,
    status: str,
    message: str,
    notification_service: Any
) -> bool:
    """
    ⚠️  DEPRECATED: Auto-send function violates HiL approval policy.

    Status updates should be sent through HiL approval workflow if needed.
    Platform NEVER auto-sends emails without user review.

    MIGRATION:
        Generate draft using email_draft_generator, then create approval
        request using HiLApprovalSystem.

    Args:
        program: BBP program details
        scan_id: Scan ID
        status: Status message
        message: Detailed message
        notification_service: Notification service (unused)

    Returns:
        False - Function is deprecated and does nothing
    """

    warnings.warn(
        "send_status_update() is DEPRECATED. Use HiL approval system.",
        DeprecationWarning,
        stacklevel=2
    )

    logger.error("⚠️  DEPRECATED: send_status_update() called - function does nothing")

    return False


async def send_follow_up_request(
    program: Dict[str, Any],
    scan_id: str,
    findings_requiring_feedback: List[Dict[str, Any]],
    notification_service: Any
) -> bool:
    """
    ⚠️  DEPRECATED: Auto-send function violates HiL approval policy.

    Follow-up emails should be sent through HiL approval workflow.
    Platform NEVER auto-sends emails without user review.

    MIGRATION:
        Generate draft reply using email_draft_generator, then create
        approval request using HiLApprovalSystem.request_email_reply_approval()

    Args:
        program: BBP program details
        scan_id: Scan ID
        findings_requiring_feedback: Findings needing feedback
        notification_service: Notification service (unused)

    Returns:
        False - Function is deprecated and does nothing
    """

    warnings.warn(
        "send_follow_up_request() is DEPRECATED. Use HiL approval system.",
        DeprecationWarning,
        stacklevel=2
    )

    logger.error("⚠️  DEPRECATED: send_follow_up_request() called - function does nothing")

    return False


# ============================================================================
# LEGACY EMAIL GENERATION - Use email_draft_generator.py Instead
# ============================================================================


async def generate_findings_email(
    program: Dict[str, Any],
    scan_result: Any
) -> str:
    """
    ⚠️  LEGACY: Use email_draft_generator.generate_initial_findings_draft() instead.

    This function generates HTML email content but is superseded by the
    email_draft_generator module which provides better formatting and
    integrates with the HiL approval workflow.

    Kept for backward compatibility only.

    Args:
        program: BBP program details
        scan_result: Full scan result

    Returns:
        str: HTML email content (legacy format)
    """

    warnings.warn(
        "generate_findings_email() is LEGACY. "
        "Use email_draft_generator.generate_initial_findings_draft()",
        PendingDeprecationWarning,
        stacklevel=2
    )

    program_name = program.get("name", "Unknown Program")
    target = scan_result.target
    total_findings = scan_result.total_findings
    critical = scan_result.critical_findings
    high = scan_result.high_findings
    medium = scan_result.medium_findings
    low = scan_result.low_findings

    # Get findings details from phases
    findings = []
    for phase in scan_result.phases:
        if phase.phase == "analysis":
            findings = phase.output.get("findings", [])
            break

    # Generate findings table
    findings_html = ""
    for i, finding in enumerate(findings[:10], 1):  # Top 10 findings
        severity = finding.get("severity", "unknown").upper()
        severity_color = {
            "CRITICAL": "#D32F2F",
            "HIGH": "#F57C00",
            "MEDIUM": "#FBC02D",
            "LOW": "#388E3C"
        }.get(severity, "#757575")

        findings_html += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 12px; color: #B0B0B0;">#{i}</td>
            <td style="padding: 12px;">
                <strong>{finding.get('type', 'Unknown').replace('_', ' ').title()}</strong><br>
                <span style="color: #9E9E9E; font-size: 0.85rem;">{finding.get('url', '')}</span>
            </td>
            <td style="padding: 12px; text-align: center;">
                <span style="
                    background: {severity_color}22;
                    color: {severity_color};
                    border: 1px solid {severity_color};
                    padding: 4px 12px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 0.875rem;
                ">{severity}</span>
            </td>
            <td style="padding: 12px; text-align: center; color: #E0E0E0;">
                {finding.get('cvss', 0.0):.1f}
            </td>
        </tr>
        """

    if not findings_html:
        findings_html = """
        <tr>
            <td colspan="4" style="padding: 20px; text-align: center; color: #9E9E9E;">
                No findings to display
            </td>
        </tr>
        """

    # Generate full email HTML
    email_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="
        margin: 0;
        padding: 0;
        font-family: 'JetBrains Mono', 'Courier New', monospace;
        background: #0A0A0A;
        color: #E0E0E0;
    ">
        <div style="max-width: 800px; margin: 0 auto; padding: 40px 20px;">

            <!-- Header -->
            <div style="
                background: linear-gradient(135deg, #00FF4111 0%, #00FF4122 100%);
                border: 2px solid #00FF41;
                border-radius: 12px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 0 30px #00FF4133;
            ">
                <h1 style="
                    margin: 0 0 10px 0;
                    color: #00FF41;
                    font-size: 2rem;
                    text-shadow: 0 0 10px #00FF4166;
                ">
                    🔒 Security Findings Report
                </h1>
                <p style="
                    margin: 0;
                    color: #9E9E9E;
                    font-size: 1rem;
                ">
                    Automated Security Assessment by Kaison K1 Platform
                </p>
            </div>

            <!-- Program Info -->
            <div style="
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 24px;
                margin-bottom: 24px;
            ">
                <h2 style="
                    margin: 0 0 16px 0;
                    color: #00FF41;
                    font-size: 1.25rem;
                ">
                    📋 Program Details
                </h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #9E9E9E; width: 150px;">Program:</td>
                        <td style="padding: 8px 0; color: #E0E0E0; font-weight: bold;">{program_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9E9E9E;">Target:</td>
                        <td style="padding: 8px 0; color: #E0E0E0;">{target}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9E9E9E;">Scan ID:</td>
                        <td style="padding: 8px 0; color: #757575; font-family: monospace;">{scan_result.scan_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9E9E9E;">Scan Date:</td>
                        <td style="padding: 8px 0; color: #E0E0E0;">{scan_result.started_at.strftime('%Y-%m-%d %H:%M UTC')}</td>
                    </tr>
                </table>
            </div>

            <!-- Summary Cards -->
            <div style="
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 16px;
                margin-bottom: 24px;
            ">
                <div style="
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                ">
                    <div style="color: #9E9E9E; font-size: 0.875rem; margin-bottom: 8px;">Total Findings</div>
                    <div style="color: #00FF41; font-size: 2.5rem; font-weight: bold;">{total_findings}</div>
                </div>

                <div style="
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                ">
                    <div style="color: #9E9E9E; font-size: 0.875rem; margin-bottom: 8px;">Critical</div>
                    <div style="color: #D32F2F; font-size: 2.5rem; font-weight: bold;">{critical}</div>
                </div>

                <div style="
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                ">
                    <div style="color: #9E9E9E; font-size: 0.875rem; margin-bottom: 8px;">High</div>
                    <div style="color: #F57C00; font-size: 2.5rem; font-weight: bold;">{high}</div>
                </div>

                <div style="
                    background: #1A1A1A;
                    border: 1px solid #2A2A2A;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                ">
                    <div style="color: #9E9E9E; font-size: 0.875rem; margin-bottom: 8px;">Medium/Low</div>
                    <div style="color: #FBC02D; font-size: 2.5rem; font-weight: bold;">{medium + low}</div>
                </div>
            </div>

            <!-- Findings Table -->
            <div style="
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 24px;
                margin-bottom: 24px;
                overflow-x: auto;
            ">
                <h2 style="
                    margin: 0 0 20px 0;
                    color: #00FF41;
                    font-size: 1.25rem;
                ">
                    🔍 Key Findings
                </h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="border-bottom: 2px solid #00FF41;">
                            <th style="padding: 12px; text-align: left; color: #00FF41; font-weight: bold;">#</th>
                            <th style="padding: 12px; text-align: left; color: #00FF41; font-weight: bold;">Finding</th>
                            <th style="padding: 12px; text-align: center; color: #00FF41; font-weight: bold;">Severity</th>
                            <th style="padding: 12px; text-align: center; color: #00FF41; font-weight: bold;">CVSS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {findings_html}
                    </tbody>
                </table>
            </div>

            <!-- Next Steps -->
            <div style="
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 24px;
                margin-bottom: 24px;
            ">
                <h2 style="
                    margin: 0 0 16px 0;
                    color: #00FF41;
                    font-size: 1.25rem;
                ">
                    📝 Next Steps
                </h2>
                <ol style="margin: 0; padding-left: 24px; color: #E0E0E0; line-height: 1.8;">
                    <li>Review detailed findings in the attached comprehensive report</li>
                    <li>Prioritize remediation for Critical and High severity issues</li>
                    <li>Verify findings in your environment</li>
                    <li>Apply security patches and fixes as recommended</li>
                    <li>Request detailed exploitation steps for validation (if needed)</li>
                </ol>
            </div>

            <!-- Report Access -->
            <div style="
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 24px;
                margin-bottom: 24px;
            ">
                <h2 style="
                    margin: 0 0 16px 0;
                    color: #00FF41;
                    font-size: 1.25rem;
                ">
                    📄 Full Report
                </h2>
                <p style="margin: 0 0 16px 0; color: #E0E0E0; line-height: 1.6;">
                    A comprehensive report with detailed findings, exploitation steps, remediation guidance,
                    and proof-of-concept code has been generated.
                </p>
                <div style="
                    background: #0F0F0F;
                    border: 1px solid #00FF41;
                    border-radius: 6px;
                    padding: 16px;
                    font-family: monospace;
                    color: #00FF41;
                ">
                    Report Path: {scan_result.final_report_path or 'Report generation in progress'}
                </div>
            </div>

            <!-- Communication -->
            <div style="
                background: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 24px;
                margin-bottom: 24px;
            ">
                <h2 style="
                    margin: 0 0 16px 0;
                    color: #00FF41;
                    font-size: 1.25rem;
                ">
                    💬 Communication
                </h2>
                <p style="margin: 0 0 12px 0; color: #E0E0E0; line-height: 1.6;">
                    For questions, clarifications, or to request additional information:
                </p>
                <ul style="margin: 0; padding-left: 24px; color: #E0E0E0; line-height: 1.8;">
                    <li>Reply to this email with your questions</li>
                    <li>Request detailed exploitation demonstrations</li>
                    <li>Ask for remediation assistance</li>
                    <li>Schedule a remediation coordination call</li>
                </ul>
            </div>

            <!-- Footer -->
            <div style="
                text-align: center;
                padding: 24px;
                color: #757575;
                font-size: 0.875rem;
                border-top: 1px solid #2A2A2A;
            ">
                <p style="margin: 0 0 8px 0;">
                    This report was generated by <strong style="color: #00FF41;">Kaison K1 Platform</strong>
                </p>
                <p style="margin: 0 0 8px 0;">
                    Autonomous Security Testing & Vulnerability Management
                </p>
                <p style="margin: 0;">
                    Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
                </p>
            </div>

        </div>
    </body>
    </html>
    """

    return email_html
