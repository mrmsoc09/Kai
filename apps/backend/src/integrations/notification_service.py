"""
Kaison K1 - Email Notification Service
Supports Gmail OAuth2 and Protonmail OpenPGP for security notifications
"""

import asyncio
import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List, Any
from enum import Enum
from datetime import datetime

import aiosmtplib
from email_validator import validate_email, EmailNotValidError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from apps.backend.src.core.secret_manager import get_secret_manager, SecretManagerError
from apps.backend.src.core.hil_vault_client import VaultClient

logger = logging.getLogger(__name__)


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EmailProvider(str, Enum):
    """Supported email providers"""
    GMAIL = "gmail"
    PROTONMAIL = "protonmail"
    SMTP = "smtp"


class NotificationService:
    """Centralized notification service for Kaison K1"""

    _instance = None

    def __init__(self):
        self.gmail_service = None
        self.gmail_credentials = None
        self.protonmail_config = None
        self.enabled_providers: List[EmailProvider] = []
        self.notification_rules: Dict[str, Any] = {}

        secret_manager = None
        try:
            secret_manager = get_secret_manager()
        except SecretManagerError:
            secret_manager = None

        # Gmail OAuth2 settings
        self.gmail_client_id = (
            secret_manager.get_optional("GMAIL_CLIENT_ID") if secret_manager else None
        )
        self.gmail_client_secret = (
            secret_manager.get_optional("GMAIL_CLIENT_SECRET") if secret_manager else None
        )
        self.gmail_redirect_uri = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/api/v1/notifications/email/gmail/callback")

        # Protonmail settings
        self.protonmail_bridge_host = os.getenv("PROTONMAIL_BRIDGE_HOST", "localhost")
        self.protonmail_bridge_port = int(os.getenv("PROTONMAIL_BRIDGE_PORT", "1025"))

        # Load credentials from storage
        self._load_credentials()

    async def initialize(self):
        """Initialize notification service on startup"""
        logger.info("Initializing Kaison K1 Notification Service")

        # Check Gmail credentials
        if self.gmail_credentials and self.gmail_credentials.valid:
            try:
                self.gmail_service = build('gmail', 'v1', credentials=self.gmail_credentials)
                self.enabled_providers.append(EmailProvider.GMAIL)
                logger.info("Gmail provider initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gmail service: {e}")

        # Check Protonmail bridge
        if await self._test_protonmail_connection():
            self.enabled_providers.append(EmailProvider.PROTONMAIL)
            logger.info("Protonmail provider initialized successfully")

        logger.info(f"Notification service ready with providers: {self.enabled_providers}")

    def _load_credentials(self):
        """Load stored credentials from vault"""
        try:
            vault = VaultClient()
            token_bundle = vault.read_secret(path="notifications/gmail")
            token_json = (token_bundle or {}).get("token_json")
            if token_json:
                self.gmail_credentials = Credentials.from_authorized_user_info(json.loads(token_json))
        except Exception:
            token_path = os.path.join(os.getcwd(), "var/lib/kai/credentials/gmail_token.json")
            if os.path.exists(token_path):
                try:
                    self.gmail_credentials = Credentials.from_authorized_user_file(token_path)
                except Exception as e:
                    logger.error(f"Failed to load Gmail credentials: {e}")

        if self.gmail_credentials and self.gmail_credentials.expired and self.gmail_credentials.refresh_token:
            try:
                self.gmail_credentials.refresh(Request())
                self._save_credentials()
            except Exception as e:
                logger.error(f"Failed refreshing Gmail credentials: {e}")

    def _save_credentials(self):
        """Save credentials to vault"""
        if not self.gmail_credentials:
            return
        token_json = self.gmail_credentials.to_json()
        try:
            vault = VaultClient()
            vault.write_secret(path="notifications/gmail", data={"token_json": token_json})
            return
        except Exception:
            token_path = os.path.join(os.getcwd(), "var/lib/kai/credentials/gmail_token.json")
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, 'w', encoding="utf-8") as token_file:
                token_file.write(token_json)

    async def _test_protonmail_connection(self) -> bool:
        """Test Protonmail Bridge connection"""
        try:
            # Try to connect to Protonmail Bridge
            async with aiosmtplib.SMTP(
                hostname=self.protonmail_bridge_host,
                port=self.protonmail_bridge_port,
                timeout=5
            ) as smtp:
                return True
        except Exception as e:
            logger.debug(f"Protonmail Bridge not available: {e}")
            return False

    def get_gmail_auth_url(self) -> str:
        """Generate Gmail OAuth2 authorization URL"""
        if not self.gmail_client_id or not self.gmail_client_secret:
            raise ValueError("Gmail OAuth2 credentials not configured")

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.gmail_client_id,
                    "client_secret": self.gmail_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.gmail_redirect_uri]
                }
            },
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        flow.redirect_uri = self.gmail_redirect_uri

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )

        return authorization_url

    async def complete_gmail_oauth(self, authorization_code: str) -> bool:
        """Complete Gmail OAuth2 flow"""
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.gmail_client_id,
                        "client_secret": self.gmail_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.gmail_redirect_uri]
                    }
                },
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )
            flow.redirect_uri = self.gmail_redirect_uri

            flow.fetch_token(code=authorization_code)
            self.gmail_credentials = flow.credentials
            self._save_credentials()

            # Initialize Gmail service
            self.gmail_service = build('gmail', 'v1', credentials=self.gmail_credentials)

            if EmailProvider.GMAIL not in self.enabled_providers:
                self.enabled_providers.append(EmailProvider.GMAIL)

            logger.info("Gmail OAuth2 completed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to complete Gmail OAuth: {e}")
            return False

    async def configure_protonmail(self, bridge_user: str, bridge_password: str) -> bool:
        """Configure Protonmail Bridge credentials"""
        try:
            self.protonmail_config = {
                "user": bridge_user,
                "password": bridge_password
            }

            # Test connection
            if await self._test_protonmail_connection():
                if EmailProvider.PROTONMAIL not in self.enabled_providers:
                    self.enabled_providers.append(EmailProvider.PROTONMAIL)
                logger.info("Protonmail configured successfully")
                return True
            else:
                logger.error("Failed to connect to Protonmail Bridge")
                return False

        except Exception as e:
            logger.error(f"Failed to configure Protonmail: {e}")
            return False

    async def send_notification(
        self,
        to: str,
        subject: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        html: bool = True,
        provider: Optional[EmailProvider] = None
    ) -> bool:
        """Send notification email"""

        # Validate email
        try:
            validate_email(to)
        except EmailNotValidError as e:
            logger.error(f"Invalid email address {to}: {e}")
            return False

        # Choose provider
        if provider is None:
            if EmailProvider.GMAIL in self.enabled_providers:
                provider = EmailProvider.GMAIL
            elif EmailProvider.PROTONMAIL in self.enabled_providers:
                provider = EmailProvider.PROTONMAIL
            else:
                logger.error("No email providers configured")
                return False

        # Send based on provider
        try:
            if provider == EmailProvider.GMAIL:
                return await self._send_via_gmail(to, subject, body, priority, html)
            elif provider == EmailProvider.PROTONMAIL:
                return await self._send_via_protonmail(to, subject, body, priority, html)
            else:
                logger.error(f"Unsupported provider: {provider}")
                return False

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def _send_via_gmail(
        self,
        to: str,
        subject: str,
        body: str,
        priority: NotificationPriority,
        html: bool
    ) -> bool:
        """Send email via Gmail API"""
        try:
            if not self.gmail_service:
                raise ValueError("Gmail service not initialized")

            # Create message
            message = MIMEMultipart('alternative')
            message['to'] = to
            message['subject'] = subject

            # Add priority header
            if priority == NotificationPriority.CRITICAL:
                message['X-Priority'] = '1'
                message['Importance'] = 'high'
            elif priority == NotificationPriority.HIGH:
                message['X-Priority'] = '2'
                message['Importance'] = 'high'

            # Add body
            if html:
                msg_part = MIMEText(body, 'html')
            else:
                msg_part = MIMEText(body, 'plain')
            message.attach(msg_part)

            # Send via Gmail API
            raw_message = {'raw': self._base64_encode_message(message)}
            send_result = self.gmail_service.users().messages().send(
                userId='me',
                body=raw_message
            ).execute()

            logger.info(f"Email sent via Gmail to {to}: {send_result.get('id')}")
            return True

        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send via Gmail: {e}")
            return False

    async def _send_via_protonmail(
        self,
        to: str,
        subject: str,
        body: str,
        priority: NotificationPriority,
        html: bool
    ) -> bool:
        """Send email via Protonmail Bridge"""
        try:
            if not self.protonmail_config:
                raise ValueError("Protonmail not configured")

            # Create message
            message = MIMEMultipart('alternative')
            message['From'] = self.protonmail_config['user']
            message['To'] = to
            message['Subject'] = subject
            message['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

            # Add priority header
            if priority == NotificationPriority.CRITICAL:
                message['X-Priority'] = '1'
                message['Importance'] = 'high'
            elif priority == NotificationPriority.HIGH:
                message['X-Priority'] = '2'
                message['Importance'] = 'high'

            # Add body
            if html:
                msg_part = MIMEText(body, 'html')
            else:
                msg_part = MIMEText(body, 'plain')
            message.attach(msg_part)

            # Send via Protonmail Bridge
            async with aiosmtplib.SMTP(
                hostname=self.protonmail_bridge_host,
                port=self.protonmail_bridge_port
            ) as smtp:
                await smtp.login(
                    self.protonmail_config['user'],
                    self.protonmail_config['password']
                )
                await smtp.send_message(message)

            logger.info(f"Email sent via Protonmail to {to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send via Protonmail: {e}")
            return False

    @staticmethod
    def _base64_encode_message(message):
        """Base64 encode message for Gmail API"""
        import base64
        return base64.urlsafe_b64encode(message.as_bytes()).decode()

    async def send_finding_notification(
        self,
        finding_id: str,
        target: str,
        severity: str,
        cvss: float,
        description: str
    ) -> bool:
        """Send notification for new security finding"""

        # Check if notifications are enabled for this severity
        if not self._should_notify_finding(cvss):
            return False

        priority = self._get_priority_for_cvss(cvss)

        subject = f"[Kaison K1] {severity.upper()} Finding Detected: {target}"

        body = f"""
        <html>
        <body style="font-family: 'JetBrains Mono', monospace; background: #121212; color: #E0E0E0;">
            <div style="padding: 20px;">
                <h1 style="color: #00FF41; text-shadow: 0 0 10px #00FF4155;">
                    Kaison K1 Security Alert
                </h1>
                <div style="background: #1E1E1E; border: 1px solid #00FF41; border-radius: 8px; padding: 16px; margin: 16px 0;">
                    <h2 style="color: #00FF41; margin-top: 0;">Finding Details</h2>
                    <p><strong>ID:</strong> {finding_id}</p>
                    <p><strong>Target:</strong> {target}</p>
                    <p><strong>Severity:</strong> <span style="color: {'#FF1744' if cvss >= 9 else '#FF9800' if cvss >= 7 else '#FFC107'};">{severity.upper()}</span></p>
                    <p><strong>CVSS Score:</strong> {cvss}</p>
                    <p><strong>Description:</strong> {description}</p>
                </div>
                <p style="color: #9E9E9E; font-size: 0.875rem;">
                    This is an automated notification from Kaison K1 Platform.<br>
                    Timestamp: {datetime.now().isoformat()}
                </p>
            </div>
        </body>
        </html>
        """

        # Get recipients from notification rules
        recipients = self.notification_rules.get('finding_recipients', [])
        if not recipients:
            logger.warning("No recipients configured for finding notifications")
            return False

        # Send to all recipients
        success = True
        for recipient in recipients:
            result = await self.send_notification(
                to=recipient,
                subject=subject,
                body=body,
                priority=priority,
                html=True
            )
            success = success and result

        return success

    def _should_notify_finding(self, cvss: float) -> bool:
        """Check if finding should trigger notification"""
        min_cvss = self.notification_rules.get('finding_min_cvss', 7.0)
        return cvss >= min_cvss

    def _get_priority_for_cvss(self, cvss: float) -> NotificationPriority:
        """Get notification priority based on CVSS score"""
        if cvss >= 9.0:
            return NotificationPriority.CRITICAL
        elif cvss >= 7.0:
            return NotificationPriority.HIGH
        else:
            return NotificationPriority.NORMAL

    def configure_notification_rules(self, rules: Dict[str, Any]):
        """Configure notification rules"""
        self.notification_rules.update(rules)
        logger.info(f"Notification rules updated: {rules}")

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all email providers"""
        return {
            "gmail": {
                "enabled": EmailProvider.GMAIL in self.enabled_providers,
                "configured": self.gmail_credentials is not None,
                "valid": self.gmail_credentials.valid if self.gmail_credentials else False
            },
            "protonmail": {
                "enabled": EmailProvider.PROTONMAIL in self.enabled_providers,
                "configured": self.protonmail_config is not None,
                "bridge_available": self._test_protonmail_connection()
            }
        }


# Singleton pattern
def get_notification_service() -> NotificationService:
    """Get or create notification service instance"""
    if NotificationService._instance is None:
        NotificationService._instance = NotificationService()
    return NotificationService._instance
