"""Tests for Shuffle SOAR integration."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from core.shuffle_client import ShuffleClient
from agents.intelligence.shuffle_orchestration_agent import (
    ShuffleOrchestrationAgent,
)


class TestShuffleClient:
    """Test ShuffleClient basic functionality."""

    def test_health_check_success(self):
        """health_check returns True when Shuffle responds."""
        client = ShuffleClient()
        with patch.object(
            client.session,
            "get",
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = client.health_check()
            assert result is True

    def test_health_check_failure(self):
        """health_check returns False when unreachable."""
        client = ShuffleClient()
        with patch(
            "requests.get",
            side_effect=Exception("Failed"),
        ):
            result = client.health_check()
            assert result is False

    def test_trigger_webhook_success(self):
        """trigger_webhook returns True on success."""
        client = ShuffleClient(
            webhook_token="test_token"
        )
        with patch.object(
            client.session,
            "post",
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = client.trigger_webhook(
                "webhook_123",
                {"event": "test"},
            )

            assert result is True

    def test_trigger_webhook_missing_token(self):
        """trigger_webhook returns False without token."""
        client = ShuffleClient(webhook_token="")
        result = client.trigger_webhook(
            "webhook_123",
            {"event": "test"},
        )
        assert result is False

    def test_trigger_critical_finding_workflow(self):
        """trigger_critical_finding_workflow routes critical finding."""
        client = ShuffleClient(
            webhook_token="test_token"
        )

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
            "trigger_webhook",
            return_value=True,
        ) as mock_trigger:
            with patch(
                "core.shuffle_client.get_secret_manager"
            ) as mock_sm:
                mock_sm_instance = MagicMock()
                mock_sm_instance.get_optional.return_value = (
                    "webhook_crit_123"
                )
                mock_sm.return_value = (
                    mock_sm_instance
                )

                result = (
                    client.trigger_critical_finding_workflow(
                        finding,
                        scan_context,
                    )
                )

                assert result is True
                assert mock_trigger.called

    def test_trigger_mission_complete_workflow(self):
        """trigger_mission_complete_workflow routes completion event."""
        client = ShuffleClient(
            webhook_token="test_token"
        )

        scan_context = {
            "scan_id": "scan_123",
            "program_name": "BugBounty",
        }
        statistics = {
            "total_findings": 5,
            "critical_findings": 1,
            "high_findings": 2,
            "duration_seconds": 3600,
        }

        with patch.object(
            client,
            "trigger_webhook",
            return_value=True,
        ) as mock_trigger:
            with patch(
                "core.shuffle_client.get_secret_manager"
            ) as mock_sm:
                mock_sm_instance = MagicMock()
                mock_sm_instance.get_optional.return_value = (
                    "webhook_complete_123"
                )
                mock_sm.return_value = (
                    mock_sm_instance
                )

                result = (
                    client.trigger_mission_complete_workflow(
                        "mission_123",
                        scan_context,
                        statistics,
                    )
                )

                assert result is True
                assert mock_trigger.called

    def test_trigger_approval_required_workflow(self):
        """trigger_approval_required_workflow routes low confidence."""
        client = ShuffleClient(
            webhook_token="test_token"
        )

        finding = {
            "type": "SQLi",
            "severity": "high",
            "value": "SQL Injection",
            "target": "api.example.com",
            "confidence": 0.55,
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
        }

        with patch.object(
            client,
            "trigger_webhook",
            return_value=True,
        ) as mock_trigger:
            with patch(
                "core.shuffle_client.get_secret_manager"
            ) as mock_sm:
                mock_sm_instance = MagicMock()
                mock_sm_instance.get_optional.return_value = (
                    "webhook_approval_123"
                )
                mock_sm.return_value = (
                    mock_sm_instance
                )

                result = (
                    client.trigger_approval_required_workflow(
                        finding,
                        "Low confidence",
                        scan_context,
                    )
                )

                assert result is True
                assert mock_trigger.called

    def test_trigger_host_anomaly_workflow(self):
        """trigger_host_anomaly_workflow routes anomaly event."""
        client = ShuffleClient(
            webhook_token="test_token"
        )

        anomaly_data = {
            "anomalies_detected": True,
            "alert_count": 5,
            "highest_severity": 12,
            "summary": "Suspicious process activity",
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
        }

        with patch.object(
            client,
            "trigger_webhook",
            return_value=True,
        ) as mock_trigger:
            with patch(
                "core.shuffle_client.get_secret_manager"
            ) as mock_sm:
                mock_sm_instance = MagicMock()
                mock_sm_instance.get_optional.return_value = (
                    "webhook_anomaly_123"
                )
                mock_sm.return_value = (
                    mock_sm_instance
                )

                result = (
                    client.trigger_host_anomaly_workflow(
                        anomaly_data,
                        scan_context,
                    )
                )

                assert result is True
                assert mock_trigger.called


class TestShuffleOrchestrationAgent:
    """Test ShuffleOrchestrationAgent."""

    def test_route_critical_finding(self):
        """route_finding routes critical findings."""
        agent = ShuffleOrchestrationAgent()

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
            "trigger_critical_finding_workflow",
            return_value=True,
        ):
            result = agent.route_finding(
                finding,
                scan_context,
            )

            assert result["routed"] is True
            assert (
                result["workflow_type"]
                == "critical_finding"
            )
            assert result["success"] is True

    def test_route_low_confidence_finding(self):
        """route_finding routes low confidence findings."""
        agent = ShuffleOrchestrationAgent()

        finding = {
            "type": "XSS",
            "severity": "medium",
            "value": "Potential XSS",
            "target": "example.com",
            "confidence": 0.45,
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
        }

        with patch.object(
            agent.client,
            "trigger_approval_required_workflow",
            return_value=True,
        ):
            result = agent.route_finding(
                finding,
                scan_context,
            )

            assert result["routed"] is True
            assert (
                result["workflow_type"]
                == "approval_required"
            )
            assert result["success"] is True

    def test_route_unmatched_finding(self):
        """route_finding does not route normal findings."""
        agent = ShuffleOrchestrationAgent()

        finding = {
            "type": "Info",
            "severity": "low",
            "value": "Information Disclosure",
            "target": "example.com",
            "confidence": 0.85,
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
        }

        result = agent.route_finding(
            finding,
            scan_context,
        )

        assert result["routed"] is False
        assert result["workflow_type"] is None

    def test_route_mission_complete_event(self):
        """route_mission_event routes completion event."""
        agent = ShuffleOrchestrationAgent()

        event_data = {
            "total_findings": 5,
            "critical_findings": 1,
            "high_findings": 2,
            "duration_seconds": 3600,
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
            "program_name": "BugBounty",
        }

        with patch.object(
            agent.client,
            "trigger_mission_complete_workflow",
            return_value=True,
        ):
            result = agent.route_mission_event(
                "mission_complete",
                event_data,
                scan_context,
            )

            assert result["routed"] is True
            assert (
                result["workflow_type"]
                == "mission_complete"
            )
            assert result["success"] is True

    def test_route_host_anomaly_event(self):
        """route_mission_event routes anomaly event."""
        agent = ShuffleOrchestrationAgent()

        event_data = {
            "anomalies_detected": True,
            "alert_count": 5,
            "highest_severity": 12,
            "summary": "Suspicious activity",
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
        }

        with patch.object(
            agent.client,
            "trigger_host_anomaly_workflow",
            return_value=True,
        ):
            result = agent.route_mission_event(
                "host_anomaly",
                event_data,
                scan_context,
            )

            assert result["routed"] is True
            assert (
                result["workflow_type"]
                == "host_anomaly"
            )
            assert result["success"] is True

    def test_route_unknown_event_type(self):
        """route_mission_event rejects unknown event type."""
        agent = ShuffleOrchestrationAgent()

        result = agent.route_mission_event(
            "unknown_event",
            {},
            {"mission_id": "mission_123"},
        )

        assert result["routed"] is False

    def test_pre_mission_check_healthy(self):
        """pre_mission_check returns safe when Shuffle is healthy."""
        agent = ShuffleOrchestrationAgent()

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
        """pre_mission_check returns unsafe when Shuffle unavailable."""
        agent = ShuffleOrchestrationAgent()

        with patch.object(
            agent.client,
            "health_check",
            return_value=False,
        ):
            result = agent.pre_mission_check({})

            assert (
                result["safe_to_proceed"] is False
            )
