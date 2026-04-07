"""Tests for TheHive integration."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from core.hil_thehive_client import TheHiveClient
from agents.intelligence.thehive_handoff_agent import (
    TheHiveHandoffAgent,
)


class TestTheHiveClient:
    """Test TheHiveClient basic functionality."""

    def test_health_check_success(self):
        """health_check returns True when TheHive responds."""
        client = TheHiveClient()
        with patch.object(
            client.session,
            "get",
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = client.health_check()
            assert result is True
            mock_get.assert_called_once()

    def test_health_check_failure(self):
        """health_check returns False when TheHive is unreachable."""
        client = TheHiveClient()
        with patch.object(
            client.session,
            "get",
            side_effect=Exception("Connection failed"),
        ):
            result = client.health_check()
            assert result is False

    def test_create_case_from_finding_success(self):
        """create_case_from_finding returns case_id on success."""
        client = TheHiveClient()
        finding = {
            "type": "sql_injection",
            "severity": "high",
            "value": "SQL Injection in login form",
            "target": "example.com",
            "raw_evidence": "Test payload returned in response",
        }
        scan_context = {
            "scan_id": "scan_123",
            "program_name": "BugBounty Corp",
        }

        with patch.object(
            client.session,
            "post",
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "id": "case_456",
            }
            mock_post.return_value = mock_response

            case_id = client.create_case_from_finding(
                finding,
                scan_context["scan_id"],
                scan_context["program_name"],
            )

            assert case_id == "case_456"
            assert mock_post.called

    def test_create_case_from_finding_maps_severity(self):
        """create_case_from_finding maps severity correctly."""
        client = TheHiveClient()
        test_cases = [
            ("critical", 3),
            ("high", 3),
            ("medium", 2),
            ("low", 1),
            ("info", 0),
        ]

        for severity_in, severity_out in test_cases:
            with patch.object(
                client.session,
                "post",
            ) as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 201
                mock_response.json.return_value = {
                    "id": f"case_{severity_in}",
                }
                mock_post.return_value = mock_response

                finding = {
                    "type": "test",
                    "severity": severity_in,
                    "value": "test",
                    "target": "test.com",
                    "raw_evidence": "test",
                }

                client.create_case_from_finding(
                    finding,
                    "scan_123",
                    "test_program",
                )

                call_args = mock_post.call_args
                payload = call_args.kwargs.get("json")
                assert payload["severity"] == (
                    severity_out
                )

    def test_add_observable_success(self):
        """add_observable returns True on success."""
        client = TheHiveClient()
        with patch.object(
            client.session,
            "post",
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_post.return_value = mock_response

            result = client.add_observable(
                "case_123",
                "domain",
                "example.com",
                tags=["target"],
            )

            assert result is True

    def test_add_observable_invalid_type(self):
        """add_observable returns False for invalid type."""
        client = TheHiveClient()
        result = client.add_observable(
            "case_123",
            "invalid_type",
            "value",
        )
        assert result is False

    def test_add_observable_all_types(self):
        """add_observable handles all valid types."""
        client = TheHiveClient()
        valid_types = [
            "ip",
            "domain",
            "url",
            "hash",
            "filename",
            "email",
            "user-agent",
        ]

        for obs_type in valid_types:
            with patch.object(
                client.session,
                "post",
            ) as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 201
                mock_post.return_value = mock_response

                result = client.add_observable(
                    "case_123",
                    obs_type,
                    "test_value",
                )

                assert result is True

    def test_create_task_success(self):
        """create_task returns task_id on success."""
        client = TheHiveClient()
        with patch.object(
            client.session,
            "post",
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "id": "task_789",
            }
            mock_post.return_value = mock_response

            task_id = client.create_task(
                "case_123",
                "Analyze Finding",
                "Analyze the finding details",
            )

            assert task_id == "task_789"

    def test_close_case_success(self):
        """close_case returns True on success."""
        client = TheHiveClient()
        with patch.object(
            client.session,
            "patch",
        ) as mock_patch:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_patch.return_value = mock_response

            result = client.close_case(
                "case_123",
                status="Resolved",
                summary="Finding fixed",
            )

            assert result is True


class TestTheHiveHandoffAgent:
    """Test TheHiveHandoffAgent orchestration."""

    def test_process_confirmed_finding_success(self):
        """process_confirmed_finding creates case and observables."""
        agent = TheHiveHandoffAgent()

        finding = {
            "type": "sql_injection",
            "severity": "high",
            "value": "SQL Injection",
            "target": "192.168.1.1",
            "raw_evidence": "evidence",
            "urls": ["http://example.com/test"],
        }
        scan_context = {
            "scan_id": "scan_123",
            "program_name": "TestProgram",
        }

        with patch.object(
            agent.client,
            "create_case_from_finding",
            return_value="case_123",
        ), patch.object(
            agent.client,
            "add_observable",
            return_value=True,
        ), patch.object(
            agent.client,
            "create_task",
            return_value="task_123",
        ):
            result = agent.process_confirmed_finding(
                finding,
                scan_context,
            )

            assert result["success"] is True
            assert result["case_id"] == "case_123"
            assert result["observables_added"] > 0
            assert result["tasks_created"] > 0

    def test_process_confirmed_finding_case_creation_fails(
        self,
    ):
        """process_confirmed_finding handles case creation failure."""
        agent = TheHiveHandoffAgent()

        finding = {
            "type": "test",
            "severity": "medium",
            "value": "test",
            "target": "test.com",
            "raw_evidence": "test",
        }
        scan_context = {
            "scan_id": "scan_123",
            "program_name": "TestProgram",
        }

        with patch.object(
            agent.client,
            "create_case_from_finding",
            return_value=None,
        ):
            result = agent.process_confirmed_finding(
                finding,
                scan_context,
            )

            assert result["success"] is False
            assert result["case_id"] is None

    def test_process_critical_finding(self):
        """process_critical_finding creates alert and case."""
        agent = TheHiveHandoffAgent()

        finding = {
            "type": "rce",
            "severity": "critical",
            "value": "Remote Code Execution",
            "target": "api.example.com",
            "raw_evidence": "critical evidence",
        }
        scan_context = {
            "scan_id": "scan_123",
            "program_name": "TestProgram",
        }

        with patch.object(
            agent.client,
            "create_alert",
            return_value="alert_123",
        ), patch.object(
            agent.client,
            "create_case_from_finding",
            return_value="case_123",
        ), patch.object(
            agent.client,
            "add_observable",
            return_value=True,
        ), patch.object(
            agent.client,
            "create_task",
            return_value="task_123",
        ):
            result = agent.process_critical_finding(
                finding,
                scan_context,
            )

            assert result["alert_id"] == "alert_123"
            assert result["case_id"] == "case_123"
            assert result["success"] is True

    def test_add_observables_extracts_from_finding(self):
        """_add_observables extracts multiple observable types."""
        agent = TheHiveHandoffAgent()

        finding = {
            "target": "example.com",
            "urls": [
                "http://example.com/test1",
                "http://example.com/test2",
            ],
            "hashes": ["abc123", "def456"],
        }

        with patch.object(
            agent.client,
            "add_observable",
            return_value=True,
        ) as mock_add:
            count = agent._add_observables(
                "case_123",
                finding,
            )

            # target + 2 URLs + 2 hashes = 5 observables
            assert count == 5
            assert mock_add.call_count == 5

    def test_create_tasks_creates_multiple(self):
        """_create_tasks creates multiple tasks."""
        agent = TheHiveHandoffAgent()

        finding = {
            "type": "vulnerability",
            "severity": "high",
            "value": "Critical Issue",
        }

        with patch.object(
            agent.client,
            "create_task",
            return_value="task_123",
        ) as mock_task:
            count = agent._create_tasks(
                "case_123",
                finding,
            )

            # For high severity: analysis + remediation + verify
            assert count == 3
            assert mock_task.call_count >= 3
