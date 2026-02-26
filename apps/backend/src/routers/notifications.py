"""
Kaison K1 - Notifications API Router
Email notification management and configuration
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
import logging

from ..integrations.notification_service import (
    get_notification_service,
    NotificationPriority,
    EmailProvider
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# Pydantic Models
class SendNotificationRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    html: bool = True
    provider: Optional[EmailProvider] = None


class GmailAuthResponse(BaseModel):
    authorization_url: str


class GmailCallbackRequest(BaseModel):
    code: str


class ProtonmailSetupRequest(BaseModel):
    bridge_user: EmailStr
    bridge_password: str


class NotificationRulesRequest(BaseModel):
    finding_min_cvss: Optional[float] = None
    finding_recipients: Optional[List[EmailStr]] = None
    daily_summary: Optional[bool] = None
    weekly_statistics: Optional[bool] = None
    approval_notifications: Optional[bool] = None


class NotificationRulesResponse(BaseModel):
    rules: Dict[str, Any]
    status: str


class ProviderStatusResponse(BaseModel):
    gmail: Dict[str, Any]
    protonmail: Dict[str, Any]


class SendNotificationResponse(BaseModel):
    success: bool
    message: str


# Endpoints

@router.post("/send", response_model=SendNotificationResponse)
async def send_notification(request: SendNotificationRequest):
    """Send a notification email"""
    try:
        service = get_notification_service()

        success = await service.send_notification(
            to=request.to,
            subject=request.subject,
            body=request.body,
            priority=request.priority,
            html=request.html,
            provider=request.provider
        )

        if success:
            return SendNotificationResponse(
                success=True,
                message=f"Notification sent successfully to {request.to}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send notification"
            )

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email/gmail/authorize", response_model=GmailAuthResponse)
async def get_gmail_auth_url():
    """Get Gmail OAuth2 authorization URL"""
    try:
        service = get_notification_service()
        auth_url = service.get_gmail_auth_url()

        return GmailAuthResponse(authorization_url=auth_url)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting Gmail auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/gmail/callback")
async def gmail_oauth_callback(request: GmailCallbackRequest):
    """Complete Gmail OAuth2 flow"""
    try:
        service = get_notification_service()
        success = await service.complete_gmail_oauth(request.code)

        if success:
            return {"status": "success", "message": "Gmail authorized successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to complete Gmail authorization"
            )

    except Exception as e:
        logger.error(f"Error completing Gmail OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email/protonmail/setup")
async def setup_protonmail(request: ProtonmailSetupRequest):
    """Configure Protonmail Bridge credentials"""
    try:
        service = get_notification_service()
        success = await service.configure_protonmail(
            bridge_user=request.bridge_user,
            bridge_password=request.bridge_password
        )

        if success:
            return {"status": "success", "message": "Protonmail configured successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to connect to Protonmail Bridge"
            )

    except Exception as e:
        logger.error(f"Error configuring Protonmail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email/status", response_model=ProviderStatusResponse)
async def get_email_status():
    """Get status of all email providers"""
    try:
        service = get_notification_service()
        status = service.get_provider_status()

        return ProviderStatusResponse(**status)

    except Exception as e:
        logger.error(f"Error getting provider status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules", response_model=NotificationRulesResponse)
async def configure_notification_rules(request: NotificationRulesRequest):
    """Configure notification alert rules"""
    try:
        service = get_notification_service()

        # Build rules dict from request
        rules = {}
        if request.finding_min_cvss is not None:
            rules['finding_min_cvss'] = request.finding_min_cvss
        if request.finding_recipients is not None:
            rules['finding_recipients'] = request.finding_recipients
        if request.daily_summary is not None:
            rules['daily_summary'] = request.daily_summary
        if request.weekly_statistics is not None:
            rules['weekly_statistics'] = request.weekly_statistics
        if request.approval_notifications is not None:
            rules['approval_notifications'] = request.approval_notifications

        service.configure_notification_rules(rules)

        return NotificationRulesResponse(
            rules=service.notification_rules,
            status="success"
        )

    except Exception as e:
        logger.error(f"Error configuring notification rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def get_notification_rules():
    """Get current notification rules"""
    try:
        service = get_notification_service()
        return {
            "rules": service.notification_rules,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error getting notification rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def send_test_notification(to: EmailStr = Query(..., description="Email address to send test to")):
    """Send a test notification to verify configuration"""
    try:
        service = get_notification_service()

        success = await service.send_notification(
            to=to,
            subject="[Kaison K1] Test Notification",
            body="""
            <html>
            <body style="font-family: 'JetBrains Mono', monospace; background: #121212; color: #E0E0E0;">
                <div style="padding: 20px;">
                    <h1 style="color: #00FF41; text-shadow: 0 0 10px #00FF4155;">
                        Kaison K1 Test Notification
                    </h1>
                    <div style="background: #1E1E1E; border: 1px solid #00FF41; border-radius: 8px; padding: 16px;">
                        <p>If you're reading this, your email configuration is working correctly!</p>
                        <p style="color: #00FF41;">✓ Email notifications are operational</p>
                    </div>
                </div>
            </body>
            </html>
            """,
            priority=NotificationPriority.NORMAL,
            html=True
        )

        if success:
            return {"status": "success", "message": f"Test email sent to {to}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test email")

    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))
