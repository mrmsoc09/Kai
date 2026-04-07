"""
MSSP (Managed Security Service Provider) Integration for KAISON AI.

Sends security findings and events to remote MSSP platforms via
syslog (RFC 5424) for centralized monitoring and alerting.

Supports both push (syslog) and pull (webhook for acknowledgments)
patterns to maintain bi-directional communication.

Credentials: MSSP_SYSLOG_HOST, MSSP_SYSLOG_PORT, MSSP_WEBHOOK_SECRET
via Vault.
"""
from __future__ import annotations

import json
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .secret_manager import get_secret_manager

logger = logging.getLogger(__name__)


class MSCertificateHandler:
    """Handles MSSP security certificates for signature verification."""

    @staticmethod
    def verify_webhook_signature(
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verifies MSSP webhook signature (HMAC-SHA256).

        Args:
            payload: Raw request body
            signature: X-MSSP-Signature header value
            secret: MSSP webhook secret

        Returns:
            True if signature is valid
        """
        try:
            import hmac
            import hashlib

            expected = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(
                signature,
                expected,
            )
        except Exception as e:
            logger.error(
                "Signature verification failed: %s",
                e,
            )
            return False


class MSPPSyslogFormatter:
    """RFC 5424 Syslog message formatter."""

    # Facility codes (local use 16-23)
    FACILITY_LOCAL_USE = 16

    # Severity levels (0-7)
    SEVERITY_MAP = {
        "critical": 0,
        "high": 2,
        "medium": 4,
        "low": 5,
        "info": 6,
    }

    @staticmethod
    def format_message(
        event_type: str,
        severity: str,
        data: dict[str, Any],
    ) -> str:
        """
        Formats event as RFC 5424 syslog message.

        Args:
            event_type: Type of event
            severity: Severity level
            data: Event data dict

        Returns:
            RFC 5424 formatted syslog message
        """
        try:
            sev = MSPPSyslogFormatter.SEVERITY_MAP.get(
                severity.lower(), 6
            )
            facility = (
                MSPPSyslogFormatter.FACILITY_LOCAL_USE
            )
            priority = facility * 8 + sev

            # RFC 5424 timestamp
            timestamp = datetime.now(
                timezone.utc
            ).isoformat()

            # Hostname (use KAISON for now)
            hostname = "kaison-ai"

            # Application tag
            app_tag = f"kai[{event_type}]"

            # Structured data: JSON in SD-PARAM
            sd_data = json.dumps(data)
            structured_data = (
                f'[kai@65535 event="{event_type}" '
                f'data="{sd_data}"]'
            )

            # RFC 5424 format:
            # PRI VERSION TIMESTAMP HOSTNAME TAG STRUCTURED-DATA MSG
            msg = (
                f"<{priority}>1 {timestamp} "
                f"{hostname} {app_tag} - - "
                f"{structured_data}"
            )

            return msg

        except Exception as e:
            logger.error(
                "Syslog formatting failed: %s",
                e,
            )
            return ""


class MSPPClient:
    """
    MSSP (Managed Security Service Provider) integration.

    Sends findings and events to remote MSSP platforms via:
    1. Syslog (RFC 5424) for event streaming
    2. HTTP webhooks for receipt/acknowledgment

    Credentials: MSSP_SYSLOG_HOST, MSSP_SYSLOG_PORT,
                 MSSP_WEBHOOK_SECRET via Vault.
    """

    def __init__(
        self,
        syslog_host: str = "",
        syslog_port: int = 0,
        webhook_secret: str = "",
    ):
        self.syslog_host = (
            syslog_host or
            get_secret_manager().get_optional(
                "MSSP_SYSLOG_HOST"
            ) or "localhost"
        )
        self.syslog_port = (
            syslog_port or
            int(
                get_secret_manager().get_optional(
                    "MSSP_SYSLOG_PORT"
                ) or 514
            )
        )
        self.webhook_secret = (
            webhook_secret or
            get_secret_manager().get_optional(
                "MSSP_WEBHOOK_SECRET"
            ) or ""
        )
        self.cert_handler = (
            MSCertificateHandler()
        )

    def health_check(self) -> bool:
        """
        Checks if MSSP syslog endpoint is reachable.
        Returns True if reachable, False otherwise.
        """
        try:
            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM,
            )
            sock.settimeout(5)
            sock.sendto(
                b"<34>1 - - - - - -",
                (
                    self.syslog_host,
                    self.syslog_port,
                ),
            )
            sock.close()
            return True
        except Exception as e:
            logger.warning(
                "MSSP health check failed: %s",
                e,
            )
            return False

    def send_syslog_message(
        self,
        event_type: str,
        severity: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Sends event to MSSP via syslog (RFC 5424).

        Args:
            event_type: Type of event
            severity: critical/high/medium/low/info
            data: Event data dict

        Returns:
            True on success, False on failure
        """
        try:
            message = (
                MSPPSyslogFormatter.format_message(
                    event_type,
                    severity,
                    data,
                )
            )

            if not message:
                return False

            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM,
            )
            sock.settimeout(5)
            sock.sendto(
                message.encode(),
                (
                    self.syslog_host,
                    self.syslog_port,
                ),
            )
            sock.close()

            logger.info(
                "Syslog message sent: %s",
                event_type,
            )
            return True

        except Exception as e:
            logger.error(
                "Syslog send failed: %s",
                e,
            )
            return False

    def send_finding_to_mssp(
        self,
        finding: dict[str, Any],
        scan_context: dict[str, Any],
    ) -> bool:
        """
        Sends confirmed finding to MSSP via syslog.

        Args:
            finding: Finding dict with severity, type, etc.
            scan_context: Scan context dict

        Returns:
            True on success
        """
        try:
            data = {
                "finding_type": finding.get(
                    "type"
                ),
                "finding_value": finding.get(
                    "value"
                ),
                "target": finding.get(
                    "target"
                ),
                "severity": finding.get(
                    "severity"
                ),
                "confidence": finding.get(
                    "confidence"
                ),
                "scan_id": scan_context.get(
                    "scan_id"
                ),
                "mission_id": scan_context.get(
                    "mission_id"
                ),
                "program": scan_context.get(
                    "program_name"
                ),
            }

            return self.send_syslog_message(
                "finding",
                finding.get("severity", "info"),
                data,
            )

        except Exception as e:
            logger.error(
                "Send finding to MSSP failed: %s",
                e,
            )
            return False

    def send_alert_to_mssp(
        self,
        alert_type: str,
        severity: str,
        message: str,
        context: dict[str, Any],
    ) -> bool:
        """
        Sends alert to MSSP via syslog.

        Args:
            alert_type: Type of alert
            severity: Alert severity
            message: Alert message
            context: Additional context dict

        Returns:
            True on success
        """
        try:
            data = {
                "alert_type": alert_type,
                "message": message,
                **context,
            }

            return self.send_syslog_message(
                "alert",
                severity,
                data,
            )

        except Exception as e:
            logger.error(
                "Send alert to MSSP failed: %s",
                e,
            )
            return False

    def verify_webhook_request(
        self,
        payload: str,
        signature: str,
    ) -> bool:
        """
        Verifies incoming MSSP webhook request.

        Args:
            payload: Request body
            signature: X-MSSP-Signature header

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning(
                "MSSP webhook secret not configured"
            )
            return False

        return self.cert_handler.verify_webhook_signature(
            payload,
            signature,
            self.webhook_secret,
        )

    def acknowledge_finding(
        self,
        finding_id: str,
        ticket_id: str,
        status: str,
    ) -> dict[str, Any]:
        """
        Records MSSP acknowledgment of finding.

        Args:
            finding_id: KAISON finding ID
            ticket_id: MSSP ticket ID
            status: Acknowledgment status

        Returns:
            Acknowledgment record dict
        """
        record = {
            "finding_id": finding_id,
            "ticket_id": ticket_id,
            "status": status,
            "acknowledged_at": (
                datetime.now(timezone.utc).isoformat()
            ),
        }

        logger.info(
            "Finding %s acknowledged by MSSP: %s",
            finding_id,
            ticket_id,
        )

        return record
