"""
Test Suite for Enhanced DNSX Agent

Tests cover:
1. Wildcard detection and filtering
2. Takeover risk identification
3. Output deduplication
4. DNS registry normalization
5. V-RAD telemetry integration
6. Listener mode (piped input)
7. Resolver configuration (DoH/custom)
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from apps.backend.src.agents.tools.dnsx.agent_enhanced import DnsxAgent
from apps.backend.src.agents.tools.dnsx.schemas import (
    DnsRegistry,
    DnsRecordType,
    ResolutionStatus,
)


class TestDnsxAgentCommandBuilding:
    """Test command generation for different modes."""

    def test_standard_mode_command(self):
        """Standard resolver mode with file input."""
        agent = DnsxAgent()
        cmd = agent.build_command(
            "example.com",
            {
                "input_file": "subdomains.txt",
                "threads": 50,
                "wildcard_detection": True,
            }
        )

        assert "dnsx" in cmd
        assert "-l" in cmd
        assert "subdomains.txt" in cmd
        assert "-wd" in cmd
        assert "example.com" in cmd
        assert "-t" in cmd
        assert "50" in cmd
        assert "-silent" in cmd
        assert "-json" in cmd

    def test_listener_mode_command(self):
        """Listener mode for piped stdin input."""
        agent = DnsxAgent()
        cmd = agent.build_command(
            "example.com",
            {"listener_mode": True, "threads": 100}
        )

        assert "dnsx" in cmd
        assert "-l" not in cmd  # No input file in listener mode
        assert "-t" in cmd
        assert "100" in cmd

    def test_brute_mode_command(self):
        """DNS bruteforce mode."""
        agent = DnsxAgent()
        cmd = agent.build_command(
            "example.com",
            {
                "brute": True,
                "wordlist": "wordlist.txt",
                "threads": 100,
            }
        )

        assert "dnsx" in cmd
        assert "-w" in cmd
        assert "wordlist.txt" in cmd
        assert "-d" in cmd
        assert "example.com" in cmd

    def test_doh_resolver_configuration(self):
        """DoH (DNS-over-HTTPS) resolver configuration."""
        agent = DnsxAgent()
        cmd = agent.build_command(
            "example.com",
            {"resolver": "doh"}
        )

        assert "-doh" in cmd

    def test_custom_resolver_configuration(self):
        """Custom resolver configuration."""
        agent = DnsxAgent()
        cmd = agent.build_command(
            "example.com",
            {"resolver": "8.8.8.8"}
        )

        assert "-r" in cmd

    def test_high_concurrency_defaults(self):
        """Verify high-concurrency default settings."""
        agent = DnsxAgent()
        cmd = agent.build_command("example.com")

        # Should have thread count
        assert "-t" in cmd
        assert "-r" in cmd  # Retry flag
        assert "-wd" in cmd  # Wildcard detection


class TestDnsOutputParsing:
    """Test dnsx JSON output parsing."""

    def test_parse_simple_a_record(self):
        """Parse single A record resolution."""
        agent = DnsxAgent()
        raw_output = json.dumps({
            "host": "api.example.com",
            "a": ["1.2.3.4"],
            "status_code": "200"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1
        assert findings[0]["subdomain"] == "api.example.com"
        assert findings[0]["context"]["a_records"] == ["1.2.3.4"]
        assert findings[0]["context"]["resolution_status"] == "resolved"

    def test_parse_multiple_record_types(self):
        """Parse multiple DNS record types."""
        agent = DnsxAgent()
        raw_output = json.dumps({
            "host": "web.example.com",
            "a": ["1.2.3.4", "1.2.3.5"],
            "aaaa": ["::1"],
            "cname": ["target.cloudfront.net"],
            "mx": ["mail.example.com"],
            "status_code": "200"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1
        assert findings[0]["context"]["a_records"] == ["1.2.3.4", "1.2.3.5"]
        assert findings[0]["context"]["aaaa_records"] == ["::1"]
        assert findings[0]["context"]["cname_records"] == ["target.cloudfront.net"]
        assert findings[0]["context"]["mx_records"] == ["mail.example.com"]

    def test_parse_nxdomain_response(self):
        """Parse NXDOMAIN (non-existent domain) response."""
        agent = DnsxAgent()
        raw_output = json.dumps({
            "host": "nonexistent.example.com",
            "status_code": "NXDOMAIN"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1
        assert findings[0]["context"]["resolution_status"] == "nxdomain"

    def test_parse_wildcard_detection(self):
        """Parse wildcard-detected response."""
        agent = DnsxAgent()
        raw_output = json.dumps({
            "host": "any.example.com",
            "a": ["1.2.3.4"],
            "wildcard": True
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1
        assert findings[0]["context"]["is_wildcard"] is True
        assert findings[0]["context"]["resolution_status"] == "wildcard"

    def test_parse_multiline_output(self):
        """Parse multiple JSON lines."""
        agent = DnsxAgent()
        line1 = json.dumps({"host": "api.example.com", "a": ["1.2.3.4"]})
        line2 = json.dumps({"host": "web.example.com", "a": ["5.6.7.8"]})
        raw_output = f"{line1}\n{line2}"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 2
        assert findings[0]["subdomain"] == "api.example.com"
        assert findings[1]["subdomain"] == "web.example.com"

    def test_skip_out_of_scope_fqdn(self):
        """Skip FQDNs not matching target domain."""
        agent = DnsxAgent()
        raw_output = json.dumps({
            "host": "evil.attacker.com",
            "a": ["1.2.3.4"]
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 0  # Filtered out (not subdomain of example.com)

    def test_deduplication_within_parse(self):
        """Deduplicate identical subdomains within same output."""
        agent = DnsxAgent()
        line1 = json.dumps({"host": "api.example.com", "a": ["1.2.3.4"]})
        line2 = json.dumps({"host": "api.example.com", "a": ["1.2.3.4"]})
        raw_output = f"{line1}\n{line2}"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1  # Duplicates removed


class TestNoiseFiltering:
    """Test signal/noise separation."""

    def test_wildcard_is_noise(self):
        """Wildcard responses marked as noise."""
        agent = DnsxAgent()
        findings = [
            {
                "subdomain": "any.example.com",
                "target": "example.com",
                "context": {
                    "is_wildcard": True,
                    "resolution_status": "wildcard",
                    "a_records": ["1.2.3.4"],
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 0
        assert len(noise) == 1
        assert noise[0]["noise_reason"] == "wildcard_detected"

    def test_nxdomain_is_noise(self):
        """NXDOMAIN marked as noise."""
        agent = DnsxAgent()
        findings = [
            {
                "subdomain": "nonexistent.example.com",
                "target": "example.com",
                "context": {
                    "resolution_status": "nxdomain",
                    "a_records": [],
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 0
        assert len(noise) == 1

    def test_cdn_only_ip_is_noise(self):
        """CDN-only IPs marked as noise."""
        agent = DnsxAgent()
        findings = [
            {
                "subdomain": "cdn.example.com",
                "target": "example.com",
                "context": {
                    "resolution_status": "resolved",
                    "a_records": ["104.16.1.1", "104.17.2.2"],  # Cloudflare
                    "cname_records": [],
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 0
        assert len(noise) == 1
        assert noise[0]["noise_reason"] == "cdn_only_ip"

    def test_takeover_candidate_is_signal(self):
        """Subdomain takeover candidates marked as HIGH signal."""
        agent = DnsxAgent()
        findings = [
            {
                "subdomain": "shop.example.com",
                "target": "example.com",
                "context": {
                    "resolution_status": "resolved",
                    "cname_records": ["target.s3.amazonaws.com"],
                    "has_takeover_risk": True,
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 1
        assert len(noise) == 0
        assert signal[0]["signal_reason"] == "subdomain_takeover_candidate"
        assert signal[0]["severity"] == "high"

    def test_resolved_ips_are_signal(self):
        """Resolved subdomains with real IPs marked as signal."""
        agent = DnsxAgent()
        findings = [
            {
                "subdomain": "api.example.com",
                "target": "example.com",
                "context": {
                    "resolution_status": "resolved",
                    "a_records": ["1.2.3.4"],
                    "cname_records": [],
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 1
        assert len(noise) == 0


class TestDnsRegistryNormalization:
    """Test DNS record normalization to DnsRegistry model."""

    def test_build_registry_from_dnsx_output(self):
        """Build DnsRegistry from raw dnsx JSON."""
        agent = DnsxAgent()
        dnsx_output = {
            "host": "api.example.com",
            "a": ["1.2.3.4"],
            "aaaa": ["::1"],
            "cname": ["target.example.com"],
            "status_code": "200"
        }

        registry = agent._build_dns_registry("api.example.com", "example.com", dnsx_output)

        assert registry.fqdn == "api.example.com"
        assert registry.target_domain == "example.com"
        assert registry.a_records == ["1.2.3.4"]
        assert registry.aaaa_records == ["::1"]
        assert registry.cname_records == ["target.example.com"]
        assert registry.resolution_status == ResolutionStatus.RESOLVED
        assert registry.is_alive is True

    def test_registry_takeover_detection(self):
        """Detect subdomain takeover candidates."""
        agent = DnsxAgent()
        dnsx_output = {
            "host": "shop.example.com",
            "cname": ["myshop.s3.amazonaws.com"],
        }

        registry = agent._build_dns_registry("shop.example.com", "example.com", dnsx_output)

        assert registry.has_takeover_risk is True
        assert registry.takeover_cname == "myshop.s3.amazonaws.com"

    def test_registry_wildcard_status(self):
        """Correctly set wildcard status."""
        agent = DnsxAgent()
        dnsx_output = {"host": "any.example.com", "wildcard": True}

        registry = agent._build_dns_registry("any.example.com", "example.com", dnsx_output)

        assert registry.is_wildcard is True
        assert registry.resolution_status == ResolutionStatus.WILDCARD

    def test_registry_ip_count_calculation(self):
        """Calculate unique IP count."""
        agent = DnsxAgent()
        dnsx_output = {
            "host": "multi.example.com",
            "a": ["1.2.3.4", "1.2.3.5"],
            "aaaa": ["::1", "::1"],  # Duplicate
        }

        registry = agent._build_dns_registry("multi.example.com", "example.com", dnsx_output)

        # post_init_calculate_counts() must be called
        assert registry.ip_count == 0  # Not calculated until manual call
        registry.post_init_calculate_counts()
        assert registry.ip_count == 3  # 2 unique A + 1 unique AAAA

    def test_registry_record_deduplication(self):
        """Deduplicate records within registry."""
        agent = DnsxAgent()
        dnsx_output = {
            "host": "dup.example.com",
            "a": ["1.2.3.4", "1.2.3.4"],
            "cname": ["TARGET.EXAMPLE.COM", "target.example.com"],  # Case-insensitive
        }

        registry = agent._build_dns_registry("dup.example.com", "example.com", dnsx_output)

        assert registry.a_records == ["1.2.3.4"]  # Deduped
        assert registry.cname_records == ["target.example.com"]  # Deduped, lowercased


class TestListenerMode:
    """Test piped input (stdin) listener mode."""

    def test_listener_mode_flag(self):
        """Verify listener mode flag is recognized."""
        agent = DnsxAgent()
        agent.build_command("example.com", {"listener_mode": True})

        assert agent._listener_mode is True

    def test_build_input_stream_from_list(self):
        """Build stdin stream from list of subdomains."""
        agent = DnsxAgent()
        agent._listener_mode = True

        stream = agent.build_input_stream(
            "example.com",
            {"input_data": ["api.example.com", "web.example.com", "db.example.com"]}
        )

        assert stream == "api.example.com\nweb.example.com\ndb.example.com"

    def test_build_input_stream_from_string(self):
        """Build stdin stream from newline-delimited string."""
        agent = DnsxAgent()
        agent._listener_mode = True

        stream = agent.build_input_stream(
            "example.com",
            {"input_data": "api.example.com\nweb.example.com"}
        )

        assert "api.example.com" in stream
        assert "web.example.com" in stream


class TestTelemetryIntegration:
    """Test V-RAD telemetry metric push."""

    def test_register_telemetry_hook(self):
        """Register telemetry callback."""
        agent = DnsxAgent()
        metrics = {}

        def hook(metric_name: str, value):
            metrics[metric_name] = value

        agent.register_telemetry_hook(hook)
        agent._push_telemetry("TEST_METRIC", 42.0)

        assert "TEST_METRIC" in metrics
        assert metrics["TEST_METRIC"] == 42.0

    def test_resolution_success_rate_telemetry(self):
        """Push resolution success rate metric."""
        agent = DnsxAgent()
        metrics = {}

        def hook(metric_name: str, value):
            metrics[metric_name] = value

        agent.register_telemetry_hook(hook)

        raw_output = "\n".join([
            json.dumps({"host": "api.example.com", "a": ["1.2.3.4"]}),
            json.dumps({"host": "nxd.example.com", "status_code": "NXDOMAIN"}),
        ])

        agent.parse_output(raw_output, "example.com")

        assert "RESOLUTION_SUCCESS_RATE" in metrics

    def test_node_active_signal_on_success(self):
        """Emit NODE_ACTIVE signal on successful resolution."""
        agent = DnsxAgent()
        metrics = []

        def hook(metric_name: str, value):
            metrics.append((metric_name, value))

        agent.register_telemetry_hook(hook)

        findings = [
            {
                "subdomain": "api.example.com",
                "target": "example.com",
                "context": {
                    "resolution_status": "resolved",
                    "a_records": ["1.2.3.4"],
                }
            }
        ]

        agent.filter_noise(findings)

        # Check if NODE_ACTIVE was pushed
        node_active_signals = [m for m in metrics if m[0] == "NODE_ACTIVE"]
        assert len(node_active_signals) > 0


class TestVendorLibraryIntegration:
    """Test integration with K1 vendor libraries."""

    def test_import_basetoalagent(self):
        """Verify BaseToolAgent inheritance."""
        agent = DnsxAgent()
        assert agent.TOOL_NAME == "dnsx"
        assert hasattr(agent, "execute")
        assert hasattr(agent, "parse_output")

    def test_import_protocol_types(self):
        """Verify protocol imports."""
        from apps.backend.src.core.protocol import (
            KaisonFinding,
            FindingType,
            Severity,
        )

        assert FindingType.SUBDOMAIN is not None
        assert Severity.HIGH is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
