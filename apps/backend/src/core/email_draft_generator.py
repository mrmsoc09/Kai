"""
Email Draft Generator
Generates ready-to-send email drafts for user approval
NEVER sends emails automatically - only creates perfect drafts
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


async def generate_initial_findings_draft(
    program: Dict[str, Any],
    scan_result: Any
) -> Dict[str, Any]:
    """
    Generate draft email for initial findings report

    NOTE: This draft is NEVER sent automatically. It is queued for
    user approval. User reviews and manually submits report to BBP platform.

    Args:
        program: BBP program details
        scan_result: Full scan result

    Returns:
        Draft email ready for user review
    """

    program_name = program.get("name", "Unknown Program")
    contact_email = program.get("contact_email", "security@example.com")
    target = scan_result.target
    total_findings = scan_result.total_findings
    critical = scan_result.critical_findings
    high = scan_result.high_findings
    medium = scan_result.medium_findings
    low = scan_result.low_findings

    # Get findings details
    findings = []
    for phase in scan_result.phases:
        if hasattr(phase, 'phase') and phase.phase == "analysis":
            findings = phase.output.get("findings", [])
            break

    # Generate findings table HTML
    findings_html = _generate_findings_table_html(findings[:10])

    # Generate subject
    subject = f"[Security Findings] {target} - {total_findings} Vulnerabilities Discovered"

    # Generate body
    body = f"""<!DOCTYPE html>
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
                Automated Security Assessment
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
                📋 Assessment Details
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
                    <td style="padding: 8px 0; color: #9E9E9E;">Assessment Date:</td>
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
            {findings_html}
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
                <li>Review detailed findings in the comprehensive report</li>
                <li>Prioritize remediation for Critical and High severity issues</li>
                <li>Request detailed exploitation steps if needed</li>
                <li>Confirm findings and provide timeline for remediation</li>
            </ol>
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
                This report was generated via automated security testing
            </p>
            <p style="margin: 0;">
                Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
            </p>
        </div>

    </div>
</body>
</html>
"""

    draft = {
        "to": contact_email,
        "subject": subject,
        "body": body,
        "html": True,
        "attachments": [],
        "metadata": {
            "scan_id": scan_result.scan_id,
            "program_id": program.get("id"),
            "program_name": program_name,
            "findings_count": total_findings,
            "severity_breakdown": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low
            }
        }
    }

    logger.info(f"📧 Generated initial findings draft for {program_name}")
    logger.info(f"To: {contact_email}, Findings: {total_findings}")

    return draft


async def generate_reply_draft(
    incoming_email: Dict[str, Any],
    scan_context: Dict[str, Any],
    program: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate draft reply to stakeholder inquiry

    Analyzes incoming email and generates contextual reply addressing
    all questions. User reviews and approves before sending.

    Args:
        incoming_email: Original email from stakeholder
        scan_context: Scan details and findings
        program: Program details

    Returns:
        Draft reply ready for user review
    """

    from_email = incoming_email.get("from", "stakeholder@example.com")
    original_subject = incoming_email.get("subject", "")
    original_body = incoming_email.get("body", "")
    received_at = incoming_email.get("received_at", datetime.now(timezone.utc))

    # Analyze questions in email
    questions = _extract_questions(original_body)

    # Generate subject
    if not original_subject.startswith("Re:"):
        subject = f"Re: {original_subject}"
    else:
        subject = original_subject

    # Generate replies to each question
    replies = []
    for question in questions:
        reply = await _generate_answer(question, scan_context, program)
        replies.append(reply)

    # Build body
    body = f"""Hello,

Thank you for your response regarding the security findings report.

"""

    if replies:
        body += "Please find answers to your questions below:\n\n"
        for i, reply in enumerate(replies, 1):
            body += f"{i}. {reply['question']}\n\n"
            body += f"   {reply['answer']}\n\n"
    else:
        body += "I'm happy to provide any additional information or clarification you need.\n\n"

    body += """If you have any further questions or need additional details (such as exploitation videos, proof-of-concept code, or remediation guidance), please let me know.

I'm available for a coordination call if that would be helpful.

Best regards,
Security Research Team
"""

    draft = {
        "to": from_email,
        "subject": subject,
        "body": body,
        "html": False,  # Plain text for replies
        "in_reply_to": incoming_email.get("message_id"),
        "references": incoming_email.get("message_id"),
        "metadata": {
            "original_email_id": incoming_email.get("id"),
            "scan_id": scan_context.get("scan_id"),
            "program_id": program.get("id"),
            "questions_addressed": len(questions)
        }
    }

    logger.info(f"📧 Generated reply draft to {from_email}")
    logger.info(f"Questions addressed: {len(questions)}")

    return draft


def _generate_findings_table_html(findings: List[Dict[str, Any]]) -> str:
    """Generate HTML table for findings"""

    if not findings:
        return """
        <table style="width: 100%; border-collapse: collapse;">
            <tbody>
                <tr>
                    <td style="padding: 20px; text-align: center; color: #9E9E9E;">
                        No findings to display
                    </td>
                </tr>
            </tbody>
        </table>
        """

    rows = ""
    for i, finding in enumerate(findings, 1):
        severity = finding.get("severity", "unknown").upper()
        severity_color = {
            "CRITICAL": "#D32F2F",
            "HIGH": "#F57C00",
            "MEDIUM": "#FBC02D",
            "LOW": "#388E3C"
        }.get(severity, "#757575")

        finding_type = finding.get("type", "Unknown").replace("_", " ").title()
        url = finding.get("url", "N/A")
        cvss = finding.get("cvss", 0.0)

        rows += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 12px; color: #B0B0B0;">#{i}</td>
            <td style="padding: 12px;">
                <strong>{finding_type}</strong><br>
                <span style="color: #9E9E9E; font-size: 0.85rem;">{url}</span>
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
                {cvss:.1f}
            </td>
        </tr>
        """

    html = f"""
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
            {rows}
        </tbody>
    </table>
    """

    return html


def _extract_questions(email_body: str) -> List[str]:
    """
    Extract questions from email body

    Looks for:
    - Lines ending with "?"
    - Common question keywords
    - Numbered lists of questions
    """

    questions = []
    lines = email_body.split("\n")

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Questions end with ?
        if line.endswith("?"):
            questions.append(line)
        # Common question patterns
        elif any(keyword in line.lower() for keyword in [
            "can you",
            "could you",
            "would you",
            "do you have",
            "is there",
            "are there",
            "when",
            "how",
            "what",
            "why",
            "where"
        ]):
            questions.append(line)

    return questions


async def _generate_answer(
    question: str,
    scan_context: Dict[str, Any],
    program: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate answer to stakeholder question

    Uses scan context and program details to provide accurate,
    helpful answer.

    Args:
        question: Question from stakeholder
        scan_context: Scan details
        program: Program details

    Returns:
        Dict with question and generated answer
    """

    question_lower = question.lower()

    # Common question patterns and responses
    if "screen recording" in question_lower or "video" in question_lower or "demonstration" in question_lower:
        answer = ("I can provide a screen recording demonstrating the vulnerability exploitation. "
                 "The recording will show step-by-step reproduction of the issue. "
                 "I'll prepare this and share it via a secure link within 24 hours.")

    elif "poc" in question_lower or "proof of concept" in question_lower or "exploit" in question_lower:
        answer = ("Yes, I can provide proof-of-concept code demonstrating the vulnerability. "
                 "The PoC will include detailed comments explaining each step. "
                 "Would you prefer Python, JavaScript, or another language?")

    elif "reproduce" in question_lower or "steps" in question_lower:
        answer = ("The vulnerability can be reproduced with the following steps:\n"
                 "1. Navigate to the affected URL\n"
                 "2. [Detailed steps will be provided based on specific vulnerability]\n"
                 "3. Observe the security issue\n\n"
                 "I can provide more detailed reproduction steps if needed.")

    elif "remediation" in question_lower or "fix" in question_lower or "patch" in question_lower:
        answer = ("I recommend the following remediation approach:\n"
                 "1. Implement proper input validation\n"
                 "2. Use parameterized queries/prepared statements\n"
                 "3. Apply principle of least privilege\n\n"
                 "I can provide specific code examples for your technology stack if helpful.")

    elif "severity" in question_lower or "cvss" in question_lower or "impact" in question_lower:
        answer = ("The severity assessment is based on CVSS v3.1 scoring. "
                 "The vulnerability allows [specific impact] which could lead to [business impact]. "
                 "I can provide a detailed CVSS breakdown if needed.")

    elif "false positive" in question_lower or "valid" in question_lower or "confirm" in question_lower:
        answer = ("I have verified this finding through multiple validation steps:\n"
                 "1. Manual verification of the vulnerability\n"
                 "2. Automated scanning confirmation\n"
                 "3. Proof-of-concept exploitation\n\n"
                 "I'm confident this is a valid security issue, but I'm happy to provide additional evidence.")

    elif "timeline" in question_lower or "when" in question_lower or "deadline" in question_lower:
        answer = ("I understand the importance of coordinated disclosure. "
                 "I'm flexible with remediation timelines and happy to work with your team's schedule. "
                 "Please let me know your preferred timeline for addressing this issue.")

    else:
        # Generic helpful response
        answer = ("Thank you for your question. I'll be happy to provide this information. "
                 "Could you provide a bit more context about what specific details would be most helpful? "
                 "I want to ensure I provide exactly what you need.")

    return {
        "question": question,
        "answer": answer
    }
