"""Tests for Cortex integration."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from core.cortex_client import CortexClient
from agents.intelligence.cortex_enrichment_agent import (
    CortexEnrichmentAgent,
)


class TestCortexClient:
    """Test CortexClient basic functionality."""

    def test_health_check_success(self):
        """health_check returns True when Cortex responds."""
        client = CortexClient()
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
        """health_check returns False when Cortex is unreachable."""
        client = CortexClient()
        with patch.object(
            client.session,
            "get",
            side_effect=Exception("Connection failed"),
        ):
            result = client.health_check()
            assert result is False

    def test_list_analyzers_success(self):
        """list_analyzers returns list of analyzers."""
        client = CortexClient()
        analyzers = [
            {
                "id": "VirusTotal_GetReport",
                "name": "VirusTotal",
                "dataTypes": ["ip", "domain", "url"],
            },
            {
                "id": "Shodan_DNSResolve",
                "name": "Shodan",
                "dataTypes": ["ip"],
            },
        ]

        with patch.object(
            client.session,
            "get",
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = analyzers
            mock_get.return_value = mock_response

            result = client.list_analyzers()
            assert len(result) == 2
            assert result[0]["id"] == (
                "VirusTotal_GetReport"
            )

    def test_list_analyzers_filter_by_type(self):
        """list_analyzers filters by data type."""
        client = CortexClient()
        analyzers = [
            {
                "id": "VirusTotal_GetReport",
                "name": "VirusTotal",
                "dataTypes": ["ip", "domain"],
            },
            {
                "id": "URLScan",
                "name": "URLScan",
                "dataTypes": ["url"],
            },
        ]

        with patch.object(
            client.session,
            "get",
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = analyzers
            mock_get.return_value = mock_response

            result = client.list_analyzers(
                data_type="url"
            )
            assert len(result) == 1
            assert result[0]["id"] == "URLScan"

    def test_run_analyzer_success(self):
        """run_analyzer returns job_id on success."""
        client = CortexClient()
        with patch.object(
            client.session,
            "post",
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "id": "job_123",
            }
            mock_post.return_value = mock_response

            job_id = client.run_analyzer(
                "VirusTotal_GetReport",
                "domain",
                "example.com",
            )

            assert job_id == "job_123"

    def test_get_job_result_success(self):
        """get_job_result returns result when job completes."""
        client = CortexClient()
        result_dict = {
            "id": "job_123",
            "status": "Success",
            "report": {
                "summary": {
                    "malicious": 5,
                }
            },
        }

        with patch.object(
            client.session,
            "get",
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = (
                result_dict
            )
            mock_get.return_value = mock_response

            result = client.get_job_result(
                "job_123",
                wait=False,
            )

            assert result == result_dict

    def test_get_job_result_timeout(self):
        """get_job_result returns None on timeout."""
        client = CortexClient()

        with patch.object(
            client.session,
            "get",
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "job_123",
                "status": "InProgress",
            }
            mock_get.return_value = mock_response

            result = client.get_job_result(
                "job_123",
                wait=True,
                timeout=0,
            )

            assert result is None

    def test_analyze_observable_default_analyzers(
        self,
    ):
        """analyze_observable selects correct analyzers."""
        client = CortexClient()

        with patch.object(
            client,
            "run_analyzer",
            return_value="job_123",
        ), patch.object(
            client,
            "get_job_result",
            return_value={"status": "Success"},
        ):
            results = client.analyze_observable(
                "ip",
                "1.2.3.4",
                wait=True,
            )

            # Should run 3 IP analyzers by default
            assert client.run_analyzer.call_count == 3


class TestCortexEnrichmentAgent:
    """Test CortexEnrichmentAgent orchestration."""

    def test_enrich_case_observables_success(self):
        """enrich_case_observables enriches observables."""
        agent = CortexEnrichmentAgent()
        observables = [
            {
                "dataType": "ip",
                "data": "1.2.3.4",
            },
            {
                "dataType": "domain",
                "data": "example.com",
            },
        ]

        with patch.object(
            agent.client,
            "analyze_observable",
            return_value=[
                {
                    "status": "Success",
                    "report": {
                        "summary": {
                            "malicious": 5,
                        }
                    },
                }
            ],
        ):
            result = (
                agent.enrich_case_observables(
                    observables,
                    thehive_case_id="case_123",
                )
            )

            assert result[
                "observables_analyzed"
            ] == 2
            assert result[
                "threat_confirmed"
            ] is True
            assert len(result[
                "analyzer_results"
            ]) >= 1

    def test_assess_threat_context_malicious(self):
        """assess_threat_context detects malicious results."""
        agent = CortexEnrichmentAgent()
        results = [
            {
                "status": "Success",
                "report": {
                    "summary": {
                        "malicious": 5,
                        "undetected": 60,
                    }
                },
            }
        ]

        assessment = agent.assess_threat_context(
            results
        )

        assert (
            assessment["threat_confirmed"]
            is True
        )
        assert assessment[
            "confidence_delta"
        ] > 0
        assert assessment[
            "indicators_count"
        ] > 0

    def test_assess_threat_context_suspicious_url(
        self,
    ):
        """assess_threat_context detects suspicious URLs."""
        agent = CortexEnrichmentAgent()
        results = [
            {
                "status": "Success",
                "report": {
                    "summary": {
                        "verdict": "suspicious",
                    }
                },
            }
        ]

        assessment = agent.assess_threat_context(
            results
        )

        assert (
            assessment["threat_confirmed"]
            is True
        )
        assert assessment[
            "severity_escalation"
        ] is not None

    def test_assess_threat_context_clean(self):
        """assess_threat_context handles clean results."""
        agent = CortexEnrichmentAgent()
        results = [
            {
                "status": "Success",
                "report": {
                    "summary": {
                        "malicious": 0,
                        "suspicious": 0,
                    }
                },
            }
        ]

        assessment = agent.assess_threat_context(
            results
        )

        assert (
            assessment["threat_confirmed"]
            is False
        )
        assert assessment[
            "confidence_delta"
        ] == 0

    def test_has_threat_indicator_virustotal(self):
        """_has_threat_indicator detects VirusTotal threats."""
        agent = CortexEnrichmentAgent()
        result = {
            "status": "Success",
            "report": {
                "summary": {
                    "malicious": 5,
                }
            },
        }

        has_threat = agent._has_threat_indicator(
            result
        )
        assert has_threat is True

    def test_has_threat_indicator_urlscan(self):
        """_has_threat_indicator detects URLScan verdicts."""
        agent = CortexEnrichmentAgent()
        result = {
            "status": "Success",
            "report": {
                "summary": {
                    "verdict": "malicious",
                }
            },
        }

        has_threat = agent._has_threat_indicator(
            result
        )
        assert has_threat is True

    def test_has_threat_indicator_shodan(self):
        """_has_threat_indicator detects Shodan suspicious ports."""
        agent = CortexEnrichmentAgent()
        result = {
            "status": "Success",
            "report": {
                "summary": {
                    "ports": [
                        22, 23, 25, 53, 110, 111,
                        135, 139, 445, 993, 995,
                        3306,
                    ],
                }
            },
        }

        has_threat = agent._has_threat_indicator(
            result
        )
        assert has_threat is True

    def test_has_threat_indicator_clean(self):
        """_has_threat_indicator returns False for clean."""
        agent = CortexEnrichmentAgent()
        result = {
            "status": "Success",
            "report": {
                "summary": {
                    "malicious": 0,
                }
            },
        }

        has_threat = agent._has_threat_indicator(
            result
        )
        assert has_threat is False
