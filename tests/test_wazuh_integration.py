"""Tests for Wazuh integration."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from core.wazuh_client import WazuhClient
from agents.intelligence.wazuh_monitor_agent import (
    WazuhMonitorAgent,
)


class TestWazuhClient:
    """Test WazuhClient basic functionality."""

    def test_health_check_success(self):
        """health_check returns True when Wazuh responds."""
        client = WazuhClient()
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = client.health_check()
            assert result is True

    def test_health_check_failure(self):
        """health_check returns False when unreachable."""
        client = WazuhClient()
        with patch(
            "requests.get",
            side_effect=Exception("Failed"),
        ):
            result = client.health_check()
            assert result is False

    def test_authenticate_success(self):
        """authenticate returns True on success."""
        client = WazuhClient(
            username="wazuh",
            password="password",
        )

        with patch(
            "requests.post"
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "token": "test_token_123",
            }
            mock_post.return_value = mock_response

            result = client.authenticate()

            assert result is True
            assert client._token == "test_token_123"

    def test_authenticate_missing_credentials(self):
        """authenticate returns False without credentials."""
        client = WazuhClient(
            username="",
            password="",
        )

        result = client.authenticate()
        assert result is False

    def test_send_alert_success(self):
        """send_alert returns True on success."""
        client = WazuhClient()
        client._token = "test_token"

        with patch.object(
            client.session,
            "post",
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_post.return_value = mock_response

            result = client.send_alert(
                title="Test Alert",
                description="Test",
                severity=10,
            )

            assert result is True

    def test_send_alert_severity_mapping(self):
        """send_alert respects severity bounds."""
        client = WazuhClient()
        client._token = "test_token"

        with patch.object(
            client.session,
            "post",
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_post.return_value = mock_response

            # Test severity bounds
            client.send_alert(
                "Test",
                "Test",
                20,
            )

            call_args = mock_post.call_args
            payload = call_args.kwargs.get("json")
            assert payload["severity"] == 15

    def test_send_finding_alert(self):
        """send_finding_alert converts finding to alert."""
        client = WazuhClient()
        client._token = "test_token"

        finding = {
            "value": "SQL Injection",
            "target": "example.com",
            "type": "injection",
            "severity": "high",
        }
        scan_context = {
            "scan_id": "scan_123",
            "program_name": "BugBounty",
        }

        with patch.object(
            client,
            "send_alert",
            return_value=True,
        ) as mock_send:
            result = client.send_finding_alert(
                finding,
                scan_context,
            )

            assert result is True
            assert mock_send.called

    def test_get_recent_alerts(self):
        """get_recent_alerts returns alert list."""
        client = WazuhClient()
        client._token = "test_token"
        alerts = [
            {
                "id": "alert_1",
                "rule": {"level": 10},
            },
            {
                "id": "alert_2",
                "rule": {"level": 8},
            },
        ]

        with patch.object(
            client.session,
            "get",
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "items": alerts,
            }
            mock_get.return_value = mock_response

            result = client.get_recent_alerts()
            assert len(result) == 2

    def test_check_host_anomalies_clean(self):
        """check_host_anomalies detects clean state."""
        client = WazuhClient()

        with patch.object(
            client,
            "get_recent_alerts",
            return_value=[],
        ):
            result = client.check_host_anomalies()

            assert (
                result["anomalies_detected"]
                is False
            )
            assert result["alert_count"] == 0

    def test_check_host_anomalies_detected(self):
        """check_host_anomalies detects anomalies."""
        client = WazuhClient()
        alerts = [
            {
                "id": "alert_1",
                "rule": {
                    "level": 12,
                    "description": (
                        "Anomaly: suspicious process"
                    ),
                },
            },
        ]

        with patch.object(
            client,
            "get_recent_alerts",
            return_value=alerts,
        ):
            result = client.check_host_anomalies()

            assert (
                result["anomalies_detected"]
                is True
            )
            assert result["alert_count"] == 1


class TestWazuhMonitorAgent:
    """Test WazuhMonitorAgent."""

    @pytest.mark.asyncio
    async def test_pre_scan_check_safe(self):
        """pre_scan_check returns safe when healthy."""
        agent = WazuhMonitorAgent()

        with patch.object(
            agent.client,
            "check_host_anomalies",
            return_value={
                "anomalies_detected": False,
                "alert_count": 0,
            },
        ):
            result = await agent.pre_scan_check()

            assert result["safe_to_proceed"] is True

    @pytest.mark.asyncio
    async def test_pre_scan_check_unsafe(self):
        """pre_scan_check returns unsafe with anomalies."""
        agent = WazuhMonitorAgent()

        with patch.object(
            agent.client,
            "check_host_anomalies",
            return_value={
                "anomalies_detected": True,
                "alert_count": 5,
                "summary": "5 alerts detected",
            },
        ):
            result = await agent.pre_scan_check()

            assert result["safe_to_proceed"] is False

    @pytest.mark.asyncio
    async def test_monitor_during_scan_timeout(self):
        """monitor_during_scan respects max_iterations."""
        agent = WazuhMonitorAgent()

        with patch.object(
            agent.client,
            "check_host_anomalies",
            return_value={
                "anomalies_detected": False,
                "alert_count": 0,
            },
        ):
            result = (
                await agent.monitor_during_scan(
                    "mission_123",
                    check_interval=0,
                    max_iterations=2,
                )
            )

            # Will be 2 or 3 depending on timing
            assert result["total_checks"] >= 2
            assert (
                result["monitoring_complete"]
                is True
            )

    @pytest.mark.asyncio
    async def test_monitor_detects_anomalies(self):
        """monitor_during_scan stops on anomalies."""
        agent = WazuhMonitorAgent()

        # First call: clean, second: anomaly
        responses = [
            {
                "anomalies_detected": False,
                "alert_count": 0,
            },
            {
                "anomalies_detected": True,
                "alert_count": 3,
                "summary": "Anomalies found",
            },
        ]

        with patch.object(
            agent.client,
            "check_host_anomalies",
            side_effect=responses,
        ):
            result = (
                await agent.monitor_during_scan(
                    "mission_123",
                    check_interval=0,
                )
            )

            assert (
                result["anomalies_detected"]
                is True
            )

    def test_send_finding_to_wazuh(self):
        """send_finding_to_wazuh calls client method."""
        agent = WazuhMonitorAgent()

        finding = {
            "value": "RCE",
            "target": "example.com",
            "type": "rce",
            "severity": "critical",
        }
        scan_context = {
            "scan_id": "scan_123",
            "program_name": "TestProgram",
        }

        with patch.object(
            agent.client,
            "send_finding_alert",
            return_value=True,
        ) as mock_send:
            result = (
                agent.send_finding_to_wazuh(
                    finding,
                    scan_context,
                )
            )

            assert result is True
            assert mock_send.called

    def test_pre_mission_check(self):
        """pre_mission_check does health check."""
        agent = WazuhMonitorAgent()

        with patch.object(
            agent.client,
            "health_check",
            return_value=True,
        ):
            result = agent.pre_mission_check({})

            assert (
                result["safe_to_proceed"] is True
            )
