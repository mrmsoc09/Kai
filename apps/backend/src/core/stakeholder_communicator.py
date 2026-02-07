"""
Stakeholder Communication System
Autonomous email correspondence with BBP program stakeholders
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


async def send_findings_to_program(
    program: Dict[str, Any],
    scan_result: Any,  # FullScanResult
    notification_service: Any
) -> bool:
    """
    Send findings report to program stakeholders

    Args:
        program: BBP program details
        scan_result: Full scan result with findings
        notification_service: Notification service for sending emails

    Returns:
        bool: True if email sent successfully
    """

    program_name = program.get("name", "Unknown Program")
    contact_email = program.get("contact_email")

    if not contact_email:
        logger.warning(f"No contact email for program {program_name}")
        return False

    logger.info(f"Sending findings report to {contact_email} for {program_name}")

    # Generate email content
    subject = f"[Kaison K1] Security Findings Report - {program_name}"
    body = await generate_findings_email(program, scan_result)

    # Send email
    try:
        success = await notification_service.send_notification(
            to=contact_email,
            subject=subject,
            body=body,
            priority="high",
            html=True
        )

        if success:
            logger.info(f"✓ Findings report sent to {contact_email}")
        else:
            logger.error(f"Failed to send findings report to {contact_email}")

        return success

    except Exception as e:
        logger.error(f"Error sending findings report: {str(e)}")
        return False


async def generate_findings_email(
    program: Dict[str, Any],
    scan_result: Any
) -> str:
    """
    Generate HTML email content for findings report

    Args:
        program: BBP program details
        scan_result: Full scan result

    Returns:
        str: HTML email content
    """

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


async def send_status_update(
    program: Dict[str, Any],
    scan_id: str,
    status: str,
    message: str,
    notification_service: Any
) -> bool:
    """
    Send status update to program stakeholders

    Args:
        program: BBP program details
        scan_id: Scan ID
        status: Status message
        message: Detailed message
        notification_service: Notification service

    Returns:
        bool: True if sent successfully
    """

    contact_email = program.get("contact_email")
    if not contact_email:
        return False

    program_name = program.get("name", "Unknown Program")
    subject = f"[Kaison K1] Scan Status Update - {program_name}"

    body = f"""
    <html>
    <body style="font-family: 'JetBrains Mono', monospace; background: #121212; color: #E0E0E0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #00FF41; text-shadow: 0 0 10px #00FF4155;">
                Kaison K1 - Scan Status Update
            </h1>

            <div style="background: #1E1E1E; border: 1px solid #00FF41; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <p><strong>Program:</strong> {program_name}</p>
                <p><strong>Scan ID:</strong> <code>{scan_id}</code></p>
                <p><strong>Status:</strong> <span style="color: #00FF41;">{status}</span></p>
                <p><strong>Message:</strong></p>
                <p style="margin-left: 20px;">{message}</p>
            </div>

            <p style="color: #9E9E9E; font-size: 0.875rem;">
                This is an automated status update from Kaison K1 Platform.<br>
                Timestamp: {datetime.utcnow().isoformat()}
            </p>
        </div>
    </body>
    </html>
    """

    try:
        return await notification_service.send_notification(
            to=contact_email,
            subject=subject,
            body=body,
            priority="normal",
            html=True
        )
    except Exception as e:
        logger.error(f"Failed to send status update: {str(e)}")
        return False


async def send_follow_up_request(
    program: Dict[str, Any],
    scan_id: str,
    findings_requiring_feedback: List[Dict[str, Any]],
    notification_service: Any
) -> bool:
    """
    Send follow-up request for findings that need stakeholder feedback

    Args:
        program: BBP program details
        scan_id: Scan ID
        findings_requiring_feedback: Findings needing feedback
        notification_service: Notification service

    Returns:
        bool: True if sent successfully
    """

    contact_email = program.get("contact_email")
    if not contact_email:
        return False

    program_name = program.get("name", "Unknown Program")
    subject = f"[Kaison K1] Follow-up Required - {program_name}"

    findings_list = ""
    for i, finding in enumerate(findings_requiring_feedback, 1):
        findings_list += f"""
        <li style="margin-bottom: 12px;">
            <strong>{finding.get('type', 'Unknown')}</strong>
            ({finding.get('severity', 'unknown').upper()})<br>
            <span style="color: #9E9E9E; font-size: 0.875rem;">
                {finding.get('description', 'No description')}
            </span>
        </li>
        """

    body = f"""
    <html>
    <body style="font-family: 'JetBrains Mono', monospace; background: #121212; color: #E0E0E0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #00FF41; text-shadow: 0 0 10px #00FF4155;">
                Kaison K1 - Follow-up Required
            </h1>

            <p>Hello,</p>

            <p>
                We have identified {len(findings_requiring_feedback)} findings that require
                additional information or feedback from your team.
            </p>

            <div style="background: #1E1E1E; border: 1px solid #00FF41; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <h2 style="color: #00FF41; margin-top: 0;">Findings Requiring Feedback:</h2>
                <ol style="margin: 0; padding-left: 20px;">
                    {findings_list}
                </ol>
            </div>

            <p>
                Please reply to this email with:
            </p>
            <ul>
                <li>Confirmation of findings</li>
                <li>Remediation timeline</li>
                <li>Any questions or concerns</li>
            </ul>

            <p style="color: #9E9E9E; font-size: 0.875rem; margin-top: 40px;">
                Scan ID: <code>{scan_id}</code><br>
                Timestamp: {datetime.utcnow().isoformat()}
            </p>
        </div>
    </body>
    </html>
    """

    try:
        return await notification_service.send_notification(
            to=contact_email,
            subject=subject,
            body=body,
            priority="high",
            html=True
        )
    except Exception as e:
        logger.error(f"Failed to send follow-up request: {str(e)}")
        return False
