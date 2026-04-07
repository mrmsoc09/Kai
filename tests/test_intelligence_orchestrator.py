"""Tests for IntelligenceOrchestrator."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from core.intelligence_orchestrator import (
    IntelligenceOrchestrator,
)


class TestIntelligenceOrchestrator:
    """Test IntelligenceOrchestrator coordination."""

    def test_health_check_all_healthy(self):
        """health_check_all returns healthy status."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        with patch.object(
            orchestrator.thehive,
            "health_check",
            return_value=True,
        ), patch.object(
            orchestrator.cortex,
            "health_check",
            return_value=True,
        ), patch.object(
            orchestrator.wazuh,
            "health_check",
            return_value=True,
        ), patch.object(
            orchestrator.shuffle,
            "health_check",
            return_value=True,
        ), patch.object(
            orchestrator.mssp,
            "health_check",
            return_value=True,
        ):
            result = orchestrator.health_check_all()

            assert result["overall_healthy"] is True
            assert (
                result["integrations"]["thehive"]
                is True
            )
            assert (
                result["integrations"]["cortex"]
                is True
            )
            assert (
                result["integrations"]["wazuh"]
                is True
            )
            assert (
                result["integrations"]["shuffle"]
                is True
            )
            assert (
                result["integrations"]["mssp"]
                is True
            )

    def test_health_check_partial_healthy(self):
        """health_check_all handles partial failures."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        with patch.object(
            orchestrator.thehive,
            "health_check",
            return_value=True,
        ), patch.object(
            orchestrator.cortex,
            "health_check",
            return_value=False,
        ), patch.object(
            orchestrator.wazuh,
            "health_check",
            return_value=True,
        ), patch.object(
            orchestrator.shuffle,
            "health_check",
            return_value=False,
        ), patch.object(
            orchestrator.mssp,
            "health_check",
            return_value=True,
        ):
            result = orchestrator.health_check_all()

            assert result["overall_healthy"] is True
            assert (
                result["integrations"]["cortex"]
                is False
            )
            assert (
                result["integrations"]["shuffle"]
                is False
            )

    def test_health_check_all_unhealthy(self):
        """health_check_all handles complete failure."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        with patch.object(
            orchestrator.thehive,
            "health_check",
            return_value=False,
        ), patch.object(
            orchestrator.cortex,
            "health_check",
            return_value=False,
        ), patch.object(
            orchestrator.wazuh,
            "health_check",
            return_value=False,
        ), patch.object(
            orchestrator.shuffle,
            "health_check",
            return_value=False,
        ), patch.object(
            orchestrator.mssp,
            "health_check",
            return_value=False,
        ):
            result = orchestrator.health_check_all()

            assert result["overall_healthy"] is False

    def test_process_confirmed_finding_full_path(self):
        """process_confirmed_finding routes through all integrations."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        # Set all integrations healthy
        orchestrator.integration_status[
            "thehive"
        ]["healthy"] = True
        orchestrator.integration_status[
            "cortex"
        ]["healthy"] = True
        orchestrator.integration_status[
            "wazuh"
        ]["healthy"] = True
        orchestrator.integration_status[
            "shuffle"
        ]["healthy"] = True
        orchestrator.integration_status[
            "mssp"
        ]["healthy"] = True

        finding = {
            "id": "finding_123",
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
            orchestrator.thehive,
            "create_case_from_finding",
            return_value="case_123",
        ), patch.object(
            orchestrator.thehive,
            "add_observable",
            return_value=True,
        ), patch.object(
            orchestrator.cortex,
            "analyze_observable",
            return_value=[{"status": "Success"}],
        ), patch.object(
            orchestrator.shuffle,
            "trigger_critical_finding_workflow",
            return_value=True,
        ), patch.object(
            orchestrator.wazuh,
            "send_finding_alert",
            return_value=True,
        ), patch.object(
            orchestrator.mssp,
            "send_finding_to_mssp",
            return_value=True,
        ):
            result = orchestrator.process_confirmed_finding(
                finding,
                scan_context,
            )

            assert result["status"] == "completed"
            assert (
                result["thehive_case_id"]
                == "case_123"
            )
            assert (
                result["cortex_enriched"] is True
            )
            assert (
                result["shuffle_routed"] is True
            )
            assert (
                result["wazuh_logged"] is True
            )
            assert result["mssp_sent"] is True
            assert len(result["steps"]) >= 3

    def test_process_confirmed_finding_partial_failure(
        self,
    ):
        """process_confirmed_finding handles partial failures gracefully."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        orchestrator.integration_status[
            "thehive"
        ]["healthy"] = True
        orchestrator.integration_status[
            "cortex"
        ]["healthy"] = True
        orchestrator.integration_status[
            "wazuh"
        ]["healthy"] = False
        orchestrator.integration_status[
            "shuffle"
        ]["healthy"] = True
        orchestrator.integration_status[
            "mssp"
        ]["healthy"] = True

        finding = {
            "id": "finding_123",
            "type": "SQLi",
            "severity": "high",
            "value": "SQL Injection",
            "target": "example.com",
            "confidence": 0.85,
        }
        scan_context = {
            "scan_id": "scan_123",
            "mission_id": "mission_123",
        }

        with patch.object(
            orchestrator.thehive,
            "create_case_from_finding",
            return_value="case_456",
        ), patch.object(
            orchestrator.thehive,
            "add_observable",
            return_value=True,
        ), patch.object(
            orchestrator.cortex,
            "analyze_observable",
            return_value=[],
        ), patch.object(
            orchestrator.shuffle,
            "trigger_critical_finding_workflow",
            return_value=False,
        ), patch.object(
            orchestrator.mssp,
            "send_finding_to_mssp",
            return_value=True,
        ):
            result = orchestrator.process_confirmed_finding(
                finding,
                scan_context,
            )

            assert result["status"] == "completed"
            assert (
                result["thehive_case_id"]
                == "case_456"
            )
            # Wazuh is disabled, so wazuh_logged should be False
            assert result["wazuh_logged"] is False
            # Other integrations should still be processed
            assert result["mssp_sent"] is True

    def test_process_confirmed_finding_no_case(self):
        """process_confirmed_finding handles case creation failure."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        orchestrator.integration_status[
            "thehive"
        ]["healthy"] = True
        orchestrator.integration_status[
            "cortex"
        ]["healthy"] = True
        orchestrator.integration_status[
            "wazuh"
        ]["healthy"] = True
        orchestrator.integration_status[
            "shuffle"
        ]["healthy"] = True
        orchestrator.integration_status[
            "mssp"
        ]["healthy"] = True

        finding = {
            "id": "finding_789",
            "type": "Info",
            "severity": "low",
            "target": "example.com",
        }
        scan_context = {
            "scan_id": "scan_789",
            "mission_id": "mission_789",
        }

        with patch.object(
            orchestrator.thehive,
            "create_case_from_finding",
            return_value=None,
        ), patch.object(
            orchestrator.shuffle,
            "trigger_critical_finding_workflow",
            return_value=True,
        ), patch.object(
            orchestrator.wazuh,
            "send_finding_alert",
            return_value=True,
        ), patch.object(
            orchestrator.mssp,
            "send_finding_to_mssp",
            return_value=True,
        ):
            result = orchestrator.process_confirmed_finding(
                finding,
                scan_context,
            )

            assert result["status"] == "completed"
            assert result["thehive_case_id"] is None
            # Cortex should not be called if no case
            assert result["cortex_enriched"] is False
            # Other integrations should still work
            assert result["wazuh_logged"] is True

    def test_process_host_anomaly_detected(self):
        """process_host_anomaly routes anomalies correctly."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        orchestrator.integration_status[
            "shuffle"
        ]["healthy"] = True
        orchestrator.integration_status[
            "mssp"
        ]["healthy"] = True

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
            orchestrator.shuffle,
            "trigger_host_anomaly_workflow",
            return_value=True,
        ), patch.object(
            orchestrator.mssp,
            "send_alert_to_mssp",
            return_value=True,
        ):
            result = orchestrator.process_host_anomaly(
                anomaly_data,
                scan_context,
            )

            assert result["status"] == "completed"
            assert (
                result["anomalies_detected"] is True
            )
            assert (
                result["shuffle_notified"] is True
            )
            assert (
                result["mssp_notified"] is True
            )

    def test_process_host_anomaly_clean(self):
        """process_host_anomaly handles clean state."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        anomaly_data = {
            "anomalies_detected": False,
            "alert_count": 0,
        }
        scan_context = {
            "mission_id": "mission_123",
            "scan_id": "scan_123",
        }

        result = orchestrator.process_host_anomaly(
            anomaly_data,
            scan_context,
        )

        assert result["status"] == "no_anomalies"
        assert (
            result["anomalies_detected"] is False
        )

    def test_process_host_anomaly_partial_failure(
        self,
    ):
        """process_host_anomaly handles partial failures."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        orchestrator.integration_status[
            "shuffle"
        ]["healthy"] = True
        orchestrator.integration_status[
            "mssp"
        ]["healthy"] = False

        anomaly_data = {
            "anomalies_detected": True,
            "alert_count": 3,
            "summary": "Anomaly detected",
        }
        scan_context = {
            "mission_id": "mission_456",
            "scan_id": "scan_456",
        }

        with patch.object(
            orchestrator.shuffle,
            "trigger_host_anomaly_workflow",
            return_value=True,
        ):
            result = orchestrator.process_host_anomaly(
                anomaly_data,
                scan_context,
            )

            assert result["status"] == "completed"
            assert (
                result["shuffle_notified"] is True
            )
            # MSSP is disabled
            assert (
                result["mssp_notified"] is False
            )

    def test_get_integration_status(self):
        """get_integration_status returns current state."""
        orchestrator = (
            IntelligenceOrchestrator()
        )

        orchestrator.integration_status[
            "thehive"
        ]["healthy"] = True
        orchestrator.integration_status[
            "cortex"
        ]["healthy"] = True
        orchestrator.integration_status[
            "wazuh"
        ]["healthy"] = False
        orchestrator.integration_status[
            "shuffle"
        ]["healthy"] = True
        orchestrator.integration_status[
            "mssp"
        ]["healthy"] = False

        result = orchestrator.get_integration_status()

        assert result["overall_healthy"] is True
        assert result["thehive"]["healthy"] is True
        assert result["wazuh"]["healthy"] is False
        assert result["mssp"]["healthy"] is False
