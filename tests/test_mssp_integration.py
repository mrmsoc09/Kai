"""Tests for MSSP (Managed Security Service Provider) integration."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from core.mssp_client import (
    MSPPClient,
    MSPPSyslogFormatter,
    MSCertificateHandler,
)
from agents.intelligence.mssp_routing_agent import (
    MSPPRoutingAgent,
)


class TestMSPPSyslogFormatter:
    """Test RFC 5424 syslog formatting."""

    def test_format_message_critical(self):
        """format_message formats critical severity correctly."""
        msg = MSPPSyslogFormatter.format_message(
            "finding",
            "critical",
            {"type": "RCE"},
        )

        assert "<" in msg  # Priority
        assert "kai@65535" in msg  # Enterprise number
        assert "event=" in msg
        assert msg.startswith("<")

    def test_format_message_info(self):
        """format_message formats info severity correctly."""
        msg = MSPPSyslogFormatter.format_message(
            "alert",
            "info",
            {"message": "test"},
        )

        assert "<" in msg
        assert "1 " in msg  # RFC 5424 version

    def test_format_message_contains_data(self):
        """format_message includes data in structured format."""
        data = {
            "finding_type": "SQLi",
            "target": "example.com",
        }
        msg = MSPPSyslogFormatter.format_message(
            "finding",
            "high",
            data,
        )

        assert "finding_type" in msg
        assert "SQLi" in msg


class TestMSCertificateHandler:
    """Test MSSP webhook signature verification."""

    def test_verify_webhook_signature_valid(self):
        """verify_webhook_signature validates correct signatures."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        import hmac
        import hashlib
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        result = (
            MSCertificateHandler.verify_webhook_signature(
                payload,
                signature,
                secret,
            )
        )

        assert result is True

    def test_verify_webhook_signature_invalid(self):
        """verify_webhook_signature rejects invalid signatures."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        invalid_sig = "0" * 64

        result = (
            MSCertificateHandler.verify_webhook_signature(
                payload,
                invalid_sig,
                secret,
            )
        )

        assert result is False


class TestMSPPClient:
    """Test MSPPClient basic functionality."""

    def test_health_check_success(self):
        """health_check returns True when reachable."""
        client = MSPPClient()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            result = client.health_check()

            assert result is True

    def test_health_check_failure(self):
        """health_check returns False when unreachable."""
        client = MSPPClient()

        with patch(
            "socket.socket",
            side_effect=Exception("Failed"),
        ):
            result = client.health_check()

            assert result is False

    def test_send_syslog_message_success(self):
        """send_syslog_message sends message successfully."""
        client = MSPPClient()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            result = client.send_syslog_message(
                "finding",
                "critical",
                {"type": "RCE"},
            )

            assert result is True
            assert mock_sock.sendto.called

    def test_send_syslog_message_failure(self):
        """send_syslog_message handles failures."""
        client = MSPPClient()

        with patch(
            "socket.socket",
            side_effect=Exception("Failed"),
        ):
            result = client.send_syslog_message(
                "finding",
                "high",
                {"type": "SQLi"},
            )

            assert result is False

    def test_send_finding_to_mssp(self):
        """send_finding_to_mssp routes finding."""
        client = MSPPClient()

        finding = {
            "type": "RCE",
            "severity": "critical",
            "value": "Remote Code Execution",
            "target": "example.com",
            "confidence": 0.95,
        }
        scan_context = {
            "scan_id": "scan_123",
            "mission_id": "mission_123",
            "program_name": "BugBounty",
        }

        with patch.object(
            client,
            "send_syslog_message",
            return_value=True,
        ):
            result = client.send_finding_to_mssp(
                finding,
                scan_context,
            )

            assert result is True

    def test_send_alert_to_mssp(self):
        """send_alert_to_mssp sends alert."""
        client = MSPPClient()

        with patch.object(
            client,
            "send_syslog_message",
            return_value=True,
        ):
            result = client.send_alert_to_mssp(
                "critical_alert",
                "critical",
                "Critical finding detected",
                {"mission_id": "mission_123"},
            )

            assert result is True

    def test_verify_webhook_request_valid(self):
        """verify_webhook_request validates signatures."""
        client = MSPPClient(
            webhook_secret="test_secret"
        )
        payload = '{"test": "data"}'

        import hmac
        import hashlib
        signature = hmac.new(
            "test_secret".encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        result = client.verify_webhook_request(
            payload,
            signature,
        )

        assert result is True

    def test_verify_webhook_request_invalid_secret(self):
        """verify_webhook_request rejects if secret not configured."""
        client = MSPPClient(webhook_secret="")

        result = client.verify_webhook_request(
            '{"test": "data"}',
            "sig",
        )

        assert result is False

    def test_acknowledge_finding(self):
        """acknowledge_finding records acknowledgment."""
        client = MSPPClient()

        result = client.acknowledge_finding(
            "finding_123",
            "ticket_456",
            "acknowledged",
        )

        assert result["finding_id"] == "finding_123"
        assert result["ticket_id"] == "ticket_456"
        assert result["status"] == "acknowledged"
        assert "acknowledged_at" in result


class TestMSPPRoutingAgent:
    """Test MSPPRoutingAgent."""

    def test_route_finding_to_mssp_success(self):
        """route_finding_to_mssp sends finding."""
        agent = MSPPRoutingAgent()

        finding = {
            "type": "RCE",
            "severity": "critical",
            "value": "Remote Code Execution",
            "target": "example.com",
            "confidence": 0.95,
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
            "program_name": "BugBounty",
        }

        with patch.object(
            agent.client,
            "send_finding_to_mssp",
            return_value=True,
        ):
            result = agent.route_finding_to_mssp(
                finding,
                scan_context,
            )

            assert result["sent"] is True

    def test_route_finding_to_mssp_failure(self):
        """route_finding_to_mssp handles failures."""
        agent = MSPPRoutingAgent()

        finding = {
            "type": "XSS",
            "severity": "medium",
            "value": "Cross-Site Scripting",
            "target": "example.com",
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
        }

        with patch.object(
            agent.client,
            "send_finding_to_mssp",
            return_value=False,
        ):
            result = agent.route_finding_to_mssp(
                finding,
                scan_context,
            )

            assert result["sent"] is False

    def test_route_critical_alert_to_mssp(self):
        """route_critical_alert_to_mssp sends alert."""
        agent = MSPPRoutingAgent()

        with patch.object(
            agent.client,
            "send_alert_to_mssp",
            return_value=True,
        ):
            result = (
                agent.route_critical_alert_to_mssp(
                    "critical",
                    "Critical finding detected",
                    {"mission_id": "mission_123"},
                )
            )

            assert result["sent"] is True

    def test_route_mission_status_to_mssp(self):
        """route_mission_status_to_mssp sends status."""
        agent = MSPPRoutingAgent()

        with patch.object(
            agent.client,
            "send_alert_to_mssp",
            return_value=True,
        ):
            result = (
                agent.route_mission_status_to_mssp(
                    "mission_123",
                    "running",
                    {
                        "total_findings": 5,
                        "critical_findings": 1,
                    },
                )
            )

            assert result["sent"] is True

    def test_handle_mssp_webhook_valid_signature(self):
        """handle_mssp_webhook validates signature."""
        agent = MSPPRoutingAgent()

        payload = json.dumps({
            "event_type": "acknowledgment",
            "finding_id": "finding_123",
            "ticket_id": "ticket_456",
            "status": "acknowledged",
        })

        import hmac
        import hashlib
        signature = hmac.new(
            agent.client.webhook_secret.encode()
            if agent.client.webhook_secret
            else b"",
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Configure agent with test secret
        agent.client.webhook_secret = "test_secret"
        signature = hmac.new(
            "test_secret".encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        result = agent.handle_mssp_webhook(
            payload,
            signature,
        )

        assert result["valid"] is True

    def test_handle_mssp_webhook_invalid_signature(self):
        """handle_mssp_webhook rejects invalid signature."""
        agent = MSPPRoutingAgent()
        agent.client.webhook_secret = "test_secret"

        payload = '{"test": "data"}'
        invalid_sig = "0" * 64

        result = agent.handle_mssp_webhook(
            payload,
            invalid_sig,
        )

        assert result["valid"] is False

    def test_handle_mssp_webhook_acknowledgment(self):
        """handle_mssp_webhook processes acknowledgment."""
        agent = MSPPRoutingAgent()
        agent.client.webhook_secret = "test_secret"

        payload = json.dumps({
            "event_type": "acknowledgment",
            "finding_id": "finding_123",
            "ticket_id": "ticket_456",
            "status": "acknowledged",
        })

        import hmac
        import hashlib
        signature = hmac.new(
            "test_secret".encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        with patch.object(
            agent.client,
            "acknowledge_finding",
        ):
            result = agent.handle_mssp_webhook(
                payload,
                signature,
            )

            assert result["valid"] is True
            assert result["processed"] is True

    def test_handle_mssp_webhook_invalid_json(self):
        """handle_mssp_webhook handles invalid JSON."""
        agent = MSPPRoutingAgent()
        agent.client.webhook_secret = "test_secret"

        payload = "invalid json"
        import hmac
        import hashlib
        signature = hmac.new(
            "test_secret".encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        result = agent.handle_mssp_webhook(
            payload,
            signature,
        )

        assert result["valid"] is True
        assert result["processed"] is False

    def test_pre_mission_check_healthy(self):
        """pre_mission_check returns safe when healthy."""
        agent = MSPPRoutingAgent()

        with patch.object(
            agent.client,
            "health_check",
            return_value=True,
        ):
            result = agent.pre_mission_check({})

            assert (
                result["safe_to_proceed"] is True
            )

    def test_pre_mission_check_unhealthy(self):
        """pre_mission_check returns unsafe when unavailable."""
        agent = MSPPRoutingAgent()

        with patch.object(
            agent.client,
            "health_check",
            return_value=False,
        ):
            result = agent.pre_mission_check({})

            assert (
                result["safe_to_proceed"] is False
            )
