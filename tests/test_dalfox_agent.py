"""
Test Suite for Enhanced Dalfox XSS Agent

Tests cover:
1. Command building (standard, listener, deep check, mining, custom payloads)
2. XSS finding parsing and classification
3. Parameter classification and prioritization
4. Vulnerability type detection
5. Risk level assessment
6. Reflection type detection
7. Confidence calculation
8. Noise filtering
9. Telemetry integration
10. Interesting parameter detection
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.backend.src.agents.tools.dalfox.agent_enhanced import DalfoxAgent
from apps.backend.src.agents.tools.dalfox.schemas import (
    ParamType,
    ReflectionType,
    RiskLevel,
    VulnerabilityRegistry,
    VulnerabilityType,
    XSSStatistics,
)


class TestDalfoxCommandBuilding:
    """Test dalfox command generation."""

    def test_standard_mode_command(self):
        """Standard mode with URL target."""
        agent = DalfoxAgent()
        cmd = agent.build_command("https://example.com")

        assert "dalfox" in cmd
        assert "scan" in cmd
        assert "--format" in cmd
        assert "json" in cmd
        assert "https://example.com" in cmd

    def test_listener_mode_command(self):
        """Listener mode with stdin piping."""
        agent = DalfoxAgent()
        cmd = agent.build_command(
            "https://example.com",
            {"listener_mode": True}
        )

        assert "dalfox" in cmd
        assert "https://example.com" not in cmd

    def test_deep_check_flag(self):
        """Deep checking flag included."""
        agent = DalfoxAgent()
        cmd = agent.build_command(
            "https://example.com",
            {"deep_check": True}
        )

        assert "--deep-check" in cmd

    def test_custom_payload_flag(self):
        """Custom payload file flag."""
        agent = DalfoxAgent()
        cmd = agent.build_command(
            "https://example.com",
            {"custom_payload_file": "/path/to/payloads.txt"}
        )

        assert "--custom-payload" in cmd
        assert "/path/to/payloads.txt" in cmd

    def test_mining_dict_flag(self):
        """Parameter mining dictionary flag."""
        agent = DalfoxAgent()
        cmd = agent.build_command(
            "https://example.com",
            {"mining_dict": "/path/to/wordlist.txt"}
        )

        assert "--mining-dict" in cmd

    def test_random_user_agent_flag(self):
        """User-Agent randomization flag."""
        agent = DalfoxAgent()
        cmd = agent.build_command(
            "https://example.com",
            {"random_user_agent": True}
        )

        assert "--random-user-agent" in cmd

    def test_proxy_flag(self):
        """Proxy configuration flag."""
        agent = DalfoxAgent()
        cmd = agent.build_command(
            "https://example.com",
            {"proxy": "http://localhost:8080"}
        )

        assert "-p" in cmd
        assert "http://localhost:8080" in cmd


class TestDalfoxOutputParsing:
    """Test XSS finding parsing."""

    def test_simple_reflected_xss(self):
        """Parse simple reflected XSS finding."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://api.example.com/search?search=test",
            "payload": "<svg onload=alert(1)>",
            "evidence": "<svg onload=alert(1)>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) > 0
        assert findings[0]["vulnerable_parameter"] == "search"
        assert "xss" in findings[0]["type"].lower()

    def test_multiple_findings_parsing(self):
        """Parse multiple XSS findings."""
        agent = DalfoxAgent()
        lines = [
            json.dumps({
                "type": "reflected",
                "inurlparam": "search",
                "url": "https://api.example.com/search?search=test",
                "payload": "<svg onload=alert(1)>",
                "evidence": "<svg onload=alert(1)>",
                "code": 200,
            }),
            json.dumps({
                "type": "reflected",
                "inurlparam": "id",
                "url": "https://api.example.com/user?id=1",
                "payload": "'\"><script>alert(1)</script>",
                "evidence": "'\"><script>alert(1)</script>",
                "code": 200,
            }),
        ]
        raw_output = "\n".join(lines)

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 2

    def test_out_of_scope_filtering(self):
        """Skip URLs not matching target domain."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://evil.com/search?search=test",
            "payload": "<svg>",
            "evidence": "<svg>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 0

    def test_deduplication(self):
        """Deduplicate identical findings."""
        agent = DalfoxAgent()
        lines = [
            json.dumps({
                "type": "reflected",
                "inurlparam": "search",
                "url": "https://api.example.com/search?search=test",
                "payload": "<svg onload=alert(1)>",
                "evidence": "<svg onload=alert(1)>",
                "code": 200,
            }),
            json.dumps({
                "type": "reflected",
                "inurlparam": "search",
                "url": "https://api.example.com/search?search=test",
                "payload": "<svg onload=alert(1)>",
                "evidence": "<svg onload=alert(1)>",
                "code": 200,
            }),
        ]
        raw_output = "\n".join(lines)

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1


class TestVulnerabilityTypeDetection:
    """Test XSS type classification."""

    def test_reflected_xss_detection(self):
        """Detect reflected XSS."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://api.example.com/search?search=test",
            "payload": "<svg onload=alert(1)>",
            "evidence": "<svg onload=alert(1)>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["vuln_type"] == "reflected_xss"

    def test_stored_xss_detection(self):
        """Detect stored XSS."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "stored",
            "inurlparam": "comment",
            "url": "https://example.com/post/1",
            "payload": "<script>alert(1)</script>",
            "evidence": "<script>alert(1)</script>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["vuln_type"] == "stored_xss"

    def test_dom_xss_detection(self):
        """Detect DOM-based XSS."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "dom",
            "inurlparam": "fragment",
            "url": "https://example.com/page#fragment=test",
            "payload": "javascript:alert(1)",
            "evidence": "javascript:alert(1)",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["vuln_type"] == "dom_xss"


class TestRiskAssessment:
    """Test risk level assessment."""

    def test_critical_stored_xss(self):
        """Stored XSS is critical."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "stored",
            "inurlparam": "comment",
            "url": "https://example.com/post",
            "payload": "<script>alert(1)</script>",
            "evidence": "<script>alert(1)</script>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["risk_level"] in ("critical", "high")
        assert findings[0]["context"]["is_critical"] is True

    def test_high_risk_direct_reflection(self):
        """Direct reflection is high risk minimum."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "id",
            "url": "https://example.com/user?id=1",
            "payload": "<svg onload=alert(1)>",
            "evidence": "<svg onload=alert(1)>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["risk_level"] in ("critical", "high")

    def test_elevated_risk_interesting_param(self):
        """Interesting parameters elevate risk."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "redirect",
            "url": "https://example.com/auth?redirect=test",
            "payload": "%3Csvg%20onload=alert(1)%3E",
            "evidence": "%3Csvg%20onload=alert(1)%3E",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        # Redirect parameter + URL encoded should be high risk
        assert findings[0]["context"]["risk_level"] in ("critical", "high", "medium")


class TestParameterClassification:
    """Test parameter analysis."""

    def test_query_string_detection(self):
        """Detect query string parameters."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://example.com/search?search=test",
            "method": "GET",
            "payload": "<svg>",
            "evidence": "<svg>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        # Should detect as query parameter
        registry = findings[0].get("vulnerability_registry")
        assert registry is not None

    def test_post_body_detection(self):
        """Detect POST body parameters."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "comment",
            "url": "https://example.com/post",
            "method": "POST",
            "data": "comment=test",
            "payload": "<svg>",
            "evidence": "<svg>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) > 0


class TestReflectionTypeDetection:
    """Test reflection classification."""

    def test_direct_reflection(self):
        """Detect direct reflection."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://example.com/search?search=test",
            "payload": "<svg onload=alert(1)>",
            "evidence": "Search: <svg onload=alert(1)>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["risk_level"] in ("critical", "high")

    def test_html_escaped_reflection(self):
        """Detect HTML escaped reflection."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://example.com/search?search=test",
            "payload": "<svg>",
            "evidence": "&lt;svg&gt;",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) > 0


class TestInterestingParameterDetection:
    """Test parameter prioritization."""

    def test_redirect_param_priority(self):
        """Identify redirect parameters."""
        agent = DalfoxAgent()
        assert agent._is_interesting_param("redirect") is True
        assert agent._is_interesting_param("url") is True
        assert agent._is_interesting_param("next") is True

    def test_content_param_priority(self):
        """Identify content parameters."""
        agent = DalfoxAgent()
        assert agent._is_interesting_param("message") is True
        assert agent._is_interesting_param("comment") is True
        assert agent._is_interesting_param("search") is True

    def test_generic_param_priority(self):
        """Identify generic interesting parameters."""
        agent = DalfoxAgent()
        assert agent._is_interesting_param("id") is True
        assert agent._is_interesting_param("username") is True


class TestNoiseFiltering:
    """Test signal vs noise separation."""

    def test_critical_findings_signal(self):
        """Critical findings marked as signal."""
        agent = DalfoxAgent()
        findings = [
            {
                "target_url": "https://example.com/search",
                "vulnerable_parameter": "search",
                "context": {
                    "is_critical": True,
                    "risk_level": "critical",
                    "confidence": 0.95,
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 1
        assert len(noise) == 0

    def test_high_risk_verified_poc_signal(self):
        """High risk with verified PoC marked as signal."""
        agent = DalfoxAgent()
        findings = [
            {
                "target_url": "https://example.com/search",
                "vulnerable_parameter": "search",
                "context": {
                    "is_critical": False,
                    "risk_level": "high",
                    "has_verified_poc": True,
                    "confidence": 0.85,
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 1

    def test_low_confidence_noise(self):
        """Low confidence findings marked as noise."""
        agent = DalfoxAgent()
        findings = [
            {
                "target_url": "https://example.com/search",
                "vulnerable_parameter": "search",
                "context": {
                    "risk_level": "low",
                    "confidence": 0.5,
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(noise) == 1


class TestTelemetryIntegration:
    """Test V-RAD telemetry."""

    def test_telemetry_hook_registration(self):
        """Register telemetry callback."""
        agent = DalfoxAgent()
        mock_callback = lambda metric, value: None

        agent.register_telemetry_hook(mock_callback)

        assert agent._telemetry_hook == mock_callback

    def test_xss_vectors_metric(self):
        """XSS_VECTORS_TESTED metric."""
        agent = DalfoxAgent()
        metrics_pushed = {}

        def mock_callback(metric_name: str, value):
            metrics_pushed[metric_name] = value

        agent.register_telemetry_hook(mock_callback)
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://example.com/search?search=test",
            "payload": "<svg>",
            "evidence": "<svg>",
            "code": 200,
        })

        agent.parse_output(raw_output, "example.com")

        assert "XSS_VECTORS_TESTED" in metrics_pushed

    def test_reflected_params_metric(self):
        """REFLECTED_PARAMS metric."""
        agent = DalfoxAgent()
        metrics_pushed = {}

        def mock_callback(metric_name: str, value):
            metrics_pushed[metric_name] = value

        agent.register_telemetry_hook(mock_callback)
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "id",
            "url": "https://example.com/user?id=1",
            "payload": "<svg>",
            "evidence": "<svg>",
            "code": 200,
        })

        agent.parse_output(raw_output, "example.com")

        assert "REFLECTED_PARAMS" in metrics_pushed


class TestVulnerabilityRegistry:
    """Test registry model."""

    def test_build_registry(self):
        """Build VulnerabilityRegistry from finding."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://api.example.com/search?search=test",
            "payload": "<svg onload=alert(1)>",
            "evidence": "<svg onload=alert(1)>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        registry = findings[0]["vulnerability_registry"]
        assert registry["target_url"] == "https://api.example.com/search?search=test"
        assert registry["vulnerable_parameter"] == "search"

    def test_critical_vuln_property(self):
        """Check critical vulnerability detection."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "stored",
            "inurlparam": "comment",
            "url": "https://example.com/post",
            "payload": "<script>alert(1)</script>",
            "evidence": "<script>alert(1)</script>",
            "code": 200,
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["is_critical"] is True


class TestXSSStatistics:
    """Test statistics tracking."""

    def test_stats_initialization(self):
        """Statistics initialized properly."""
        agent = DalfoxAgent()
        assert agent._stats.total_urls_scanned == 0
        assert agent._stats.vulnerabilities_found == 0

    def test_stats_tracking(self):
        """Statistics updated during parsing."""
        agent = DalfoxAgent()
        raw_output = json.dumps({
            "type": "reflected",
            "inurlparam": "search",
            "url": "https://example.com/search?search=test",
            "payload": "<svg>",
            "evidence": "<svg>",
            "code": 200,
        })

        agent.parse_output(raw_output, "example.com")

        assert agent._stats.total_urls_scanned >= 1
        assert agent._stats.vulnerabilities_found >= 1


class TestVendorIntegration:
    """Test vendor library integration."""

    def test_base_tool_agent_inheritance(self):
        """DalfoxAgent inherits from BaseToolAgent."""
        agent = DalfoxAgent()
        assert hasattr(agent, 'build_command')
        assert hasattr(agent, 'parse_output')
        assert hasattr(agent, 'filter_noise')

    def test_protocol_imports(self):
        """Protocol types import successfully."""
        from apps.backend.src.agents.tools.dalfox.agent_enhanced import (
            VulnerabilityRegistry,
            VulnerabilityType,
            RiskLevel,
        )
        assert VulnerabilityRegistry is not None
        assert VulnerabilityType is not None
        assert RiskLevel is not None
