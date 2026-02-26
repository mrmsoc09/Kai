# Human-in-the-Loop (HiL) Approval Workflow

## Overview

The Kaison K1 Platform implements a strict Human-in-the-Loop (HiL) approval system for all stakeholder communications. **The platform NEVER automatically sends emails** - it only creates perfect drafts for user review and approval.

## Critical Principles

1. **Platform NEVER auto-sends emails** - All emails require explicit user approval
2. **Platform ONLY replies to emails, NEVER initiates** - Stakeholders are notified through report submission on BBP platforms
3. **HiL approval required before**:
   - Report submissions to BBP platforms
   - Email replies to stakeholder inquiries
4. **User manually sends all emails** after reviewing and approving drafts

## Workflow

### Phase 1: Autonomous Scanning

```
User Initiates Scan
    ↓
Platform selects BBP programs
    ↓
Platform runs full scan (9 phases)
    ↓
Phase 9: Stakeholder Communication
```

### Phase 2: Draft Creation (Phase 9)

Instead of sending emails, Phase 9 now:

1. **Generates email draft** using `email_draft_generator.py`
   - Creates professional HTML email
   - Includes findings summary, severity breakdown, CVSS scores
   - Adds report access information

2. **Creates approval request** using `hil_approval_system.py`
   - Approval type: `REPORT_SUBMISSION`
   - Status: `PENDING`
   - Contains complete draft ready for review

3. **Returns phase result** indicating draft created
   - ✅ Phase completes successfully
   - ⚠️ Email draft ready for user approval
   - User notified via API response

### Phase 3: User Review & Approval

User reviews draft via HiL Approval API:

```bash
# List pending approvals
GET /api/v1/approval/pending

# Get specific approval details
GET /api/v1/approval/{approval_id}

# Review draft content
# - Email subject
# - Email body (HTML)
# - Recipient
# - Findings summary
# - Report attachment

# Option 1: Approve draft
POST /api/v1/approval/{approval_id}/approve
{
  "user_id": "user123",
  "notes": "Looks good, ready to send"
}

# Option 2: Edit draft before approving
PUT /api/v1/approval/{approval_id}/update
{
  "content": {
    "email_draft": {
      "subject": "Updated subject",
      "body": "Updated HTML body..."
    }
  },
  "notes": "Fixed typo in findings description"
}

# Option 3: Reject draft
POST /api/v1/approval/{approval_id}/reject
{
  "user_id": "user123",
  "reason": "Need to verify findings before disclosure"
}
```

### Phase 4: Manual Email Sending

After approving the draft:

1. **User copies email content** from approval request
2. **User manually sends email** via their email client
3. **User marks communication complete** in platform

## Email Reply Workflow

When stakeholders reply with questions:

```
Stakeholder sends email with questions
    ↓
Platform monitors incoming email (future feature)
    ↓
Platform analyzes email and extracts questions
    ↓
Platform generates draft reply using email_draft_generator
    ↓
Platform creates HiL approval request (EMAIL_REPLY type)
    ↓
User reviews draft reply via API
    ↓
User approves/edits/rejects draft
    ↓
User manually sends reply via email client
```

## Architecture

### Core Components

1. **`full_scan_orchestrator.py`** (Updated)
   - Phase 9 creates drafts instead of auto-sending
   - Uses `HiLApprovalSystem` for approval workflow
   - Uses `email_draft_generator` for draft creation

2. **`hil_approval_system.py`** (New)
   - Manages approval workflow
   - Tracks pending approvals and history
   - Supports approve, reject, update operations
   - ApprovalType: `REPORT_SUBMISSION`, `EMAIL_REPLY`
   - ApprovalStatus: `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`

3. **`email_draft_generator.py`** (New)
   - Generates initial findings report drafts
   - Generates reply drafts to stakeholder inquiries
   - Professional HTML email templates
   - NEVER sends automatically

4. **`hil_approval.py`** (New API Router)
   - REST API for approval management
   - Endpoints for list, get, approve, reject, update
   - Statistics and filtering

### API Endpoints

#### Approval Management

```
GET    /api/v1/approval/pending          # List pending approvals
GET    /api/v1/approval/all              # List all approvals (with filters)
GET    /api/v1/approval/{approval_id}    # Get specific approval
POST   /api/v1/approval/{approval_id}/approve    # Approve draft
POST   /api/v1/approval/{approval_id}/reject     # Reject draft
PUT    /api/v1/approval/{approval_id}/update     # Update draft content
DELETE /api/v1/approval/{approval_id}    # Cancel approval request
GET    /api/v1/approval/stats/summary    # Get approval statistics
```

## Code Changes

### 1. `full_scan_orchestrator.py`

**Before (WRONG - Auto-sends):**
```python
async def _phase_stakeholder_communication(...):
    # Send findings to program contact
    from .stakeholder_communicator import send_findings_to_program

    success = await send_findings_to_program(
        program=program,
        scan_result=scan_result,
        notification_service=self.notification_service
    )

    return PhaseResult(
        status=COMPLETED if success else FAILED,
        output={"email_sent": success}
    )
```

**After (CORRECT - Creates Draft):**
```python
async def _phase_stakeholder_communication(...):
    """
    IMPORTANT: This phase NEVER sends emails automatically.
    It creates a draft email and approval request for user review.
    """

    # Generate draft email
    from .email_draft_generator import generate_initial_findings_draft
    draft = await generate_initial_findings_draft(program, scan_result)

    # Create HiL approval request
    approval_request = await self.hil_system.request_report_submission_approval(
        scan_id=scan_id,
        program_id=program.get("id"),
        program_name=program.get("name"),
        report_content={
            "email_draft": draft,
            "findings_count": scan_result.total_findings,
            ...
        },
        submission_platform=program.get("platform")
    )

    logger.info("⚠️  EMAIL DRAFT READY - User approval required before sending")

    return PhaseResult(
        status=COMPLETED,
        output={
            "draft_created": True,
            "approval_id": approval_request.approval_id,
            "note": "Email draft created and queued for user approval"
        }
    )
```

### 2. Initialization Changes

**`full_scan_orchestrator.py` `__init__`:**
```python
# Before
from ..integrations.notification_service import get_notification_service
self.notification_service = get_notification_service()

# After
from .hil_approval_system import HiLApprovalSystem
self.hil_system = HiLApprovalSystem()
```

**`main.py` startup:**
```python
# Added HiL Approval router
from ..routers import hil_approval
app.include_router(hil_approval.router)

# Added HiL Approval System initialization
from ..routers.hil_approval import get_hil_system
hil_system = get_hil_system()
print("[✓] HiL Approval System initialized")
```

## Data Models

### ApprovalRequest

```python
@dataclass
class ApprovalRequest:
    approval_id: str           # Unique approval ID
    approval_type: ApprovalType  # REPORT_SUBMISSION, EMAIL_REPLY
    status: ApprovalStatus     # PENDING, APPROVED, REJECTED, CANCELLED
    created_at: datetime

    # Content
    title: str                 # "Report Submission: Example Corp"
    description: str           # Detailed description
    content: Dict[str, Any]    # Draft email, report, etc.

    # Context
    scan_id: Optional[str]
    program_id: Optional[str]
    program_name: Optional[str]

    # Approval details
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]

    # User notes/edits
    user_notes: str
    user_edits: Dict[str, Any]
```

### Email Draft

```python
{
  "to": "security@example.com",
  "subject": "[Security Findings] example.com - 5 Vulnerabilities Discovered",
  "body": "<html>...</html>",  # Professional HTML email
  "attachments": [
    {
      "filename": "security_report.md",
      "path": "/path/to/report.md"
    }
  ]
}
```

## Security Considerations

1. **No Auto-Send Risk** - Platform cannot accidentally send emails
2. **User Review Required** - All communications reviewed before sending
3. **Audit Trail** - Complete approval history tracked
4. **Edit Capability** - User can modify drafts before approval
5. **Rejection Option** - User can reject inappropriate drafts

## Future Enhancements

1. **Incoming Email Monitoring** - Detect stakeholder replies
2. **Question Extraction** - Parse questions from stakeholder emails
3. **Contextual Reply Generation** - Generate replies based on scan context
4. **Email Template Customization** - User-configurable templates
5. **Multi-User Approvals** - Require multiple approvals for critical communications
6. **Email Client Integration** - Direct send from platform after approval

## Testing

### Test Workflow

1. **Run autonomous scan:**
```bash
POST /api/v1/autonomous/scan/execute
{
  "program_id": "test_program",
  "user_id": "test_user"
}
```

2. **Verify draft creation:**
```bash
GET /api/v1/approval/pending
# Should return 1 pending approval with email draft
```

3. **Review draft:**
```bash
GET /api/v1/approval/{approval_id}
# Inspect email subject, body, findings
```

4. **Approve draft:**
```bash
POST /api/v1/approval/{approval_id}/approve
{
  "user_id": "test_user"
}
```

5. **Verify approval:**
```bash
GET /api/v1/approval/{approval_id}
# Status should be "approved"
```

## Summary

The HiL approval workflow ensures that:

✅ Platform NEVER auto-sends emails
✅ All communications reviewed by user
✅ User maintains full control over disclosures
✅ Draft quality maintained (platform creates perfect drafts)
✅ User efficiency preserved (minimal edits needed)
✅ Audit trail for all communications
✅ Compliance with security disclosure best practices

**Bottom Line:** Platform creates perfect drafts → User reviews → User approves → User manually sends.
