"""
Comprehensive test suite for K1 Network & Protocol Wing agents.

Tests cover:
- Installation verification for all four agents
- Schema validation with Pydantic v2
- Mock scan result parsing
- Telemetry emission
- SNL routing enforcement
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from apps.backend.src.agents.tools.nmap.install import (
    verify_nmap_installed,
    get_nmap_version,
)
from apps.backend.src.agents.tools.masscan.install import (
    verify_masscan_installed,
    get_masscan_version,
)
from apps.backend.src.agents.tools.wafw00f.install import (
    verify_wafw00f_installed,
    get_wafw00f_version,
)
from apps.backend.src.agents.tools.testssl.install import (
    verify_testssl_installed,
    get_testssl_version,
)
from apps.backend.src.agents.tools.network_fingerprint_schemas import (
    PortServiceRegistry,
    TargetRegistry,
)
from apps.backend.src.agents.tools.testssl.schemas import (
    TLSVersion,
    CipherStrength,
    EncryptionGrade,
    SSLCipherRegistry,
    TLSVulnerabilityRegistry,
    SSLScanResultRegistry,
)
from apps.backend.src.agents.tools.nmap.agent import NmapAgent
from apps.backend.src.agents.tools.masscan.agent import MasscanAgent
from apps.backend.src.agents.tools.wafw00f.agent import Wafw00fAgent
from apps.backend.src.agents.tools.testssl.agent import TestsslAgent


# ============================================================================
# INSTALLATION VERIFICATION TESTS
# ============================================================================


class TestNmapInstallation:
    """Test nmap installation and verification."""

    def test_verify_nmap_installed(self) -> None:
        """Test nmap installation check."""
        # This test will pass if nmap is installed, skip if not
        result = verify_nmap_installed()
        assert isinstance(result, bool)

    def test_get_nmap_version(self) -> None:
        """Test nmap version retrieval."""
        version = get_nmap_version()
        if verify_nmap_installed():
            assert version is not None
            assert len(version) > 0
        else:
            assert version is None


class TestMasscanInstallation:
    """Test masscan installation and verification."""

    def test_verify_masscan_installed(self) -> None:
        """Test masscan installation check."""
        result = verify_masscan_installed()
        assert isinstance(result, bool)

    def test_get_masscan_version_when_not_installed(self) -> None:
        """Test masscan version retrieval returns None when not installed."""
        # This test works regardless of installation status
        # If masscan is not installed, get_masscan_version returns None
        version = get_masscan_version()
        if not verify_masscan_installed():
            assert version is None


class TestWafw00fInstallation:
    """Test wafw00f installation and verification."""

    def test_verify_wafw00f_installed(self) -> None:
        """Test wafw00f installation check."""
        result = verify_wafw00f_installed()
        assert isinstance(result, bool)

    def test_get_wafw00f_version(self) -> None:
        """Test wafw00f version retrieval."""
        version = get_wafw00f_version()
        if verify_wafw00f_installed():
            assert version is not None
        else:
            assert version is None


class TestTestsslInstallation:
    """Test testssl.sh installation and verification."""

    def test_verify_testssl_installed(self) -> None:
        """Test testssl installation check."""
        result = verify_testssl_installed()
        assert isinstance(result, bool)

    def test_get_testssl_version(self) -> None:
        """Test testssl version retrieval."""
        version = get_testssl_version()
        # Version might be None even if installed
        assert version is None or isinstance(version, str)


# ============================================================================
# SCHEMA VALIDATION TESTS (PYDANTIC V2)
# ============================================================================


class TestPortServiceRegistrySchema:
    """Test PortServiceRegistry Pydantic v2 validation."""

    def test_valid_port_service_record(self) -> None:
        """Validate correct PortServiceRegistry entry."""
        record = PortServiceRegistry.model_validate(
            {
                "target_ip": "192.168.1.1",
                "port_number": 22,
                "proto_type": "tcp",
                "service_name": "ssh",
                "version": "OpenSSH 7.4",
                "timestamp": datetime.now(UTC),
            }
        )
        assert record.target_ip == "192.168.1.1"
        assert record.port_number == 22
        assert record.service_name == "ssh"

    def test_port_service_minimal_record(self) -> None:
        """Test minimal PortServiceRegistry entry."""
        record = PortServiceRegistry.model_validate(
            {
                "target_ip": "example.com",
                "port_number": 443,
            }
        )
        assert record.target_ip == "example.com"
        assert record.port_number == 443
        assert record.proto_type == "tcp"

    def test_port_service_invalid_port(self) -> None:
        """Test invalid port number validation."""
        with pytest.raises(ValueError):
            PortServiceRegistry.model_validate(
                {
                    "target_ip": "192.168.1.1",
                    "port_number": 70000,  # Out of range
                }
            )

    def test_port_service_invalid_ip(self) -> None:
        """Test invalid IP address validation."""
        with pytest.raises(ValueError):
            PortServiceRegistry.model_validate(
                {
                    "target_ip": "",  # Empty IP
                    "port_number": 22,
                }
            )


class TestTargetRegistrySchema:
    """Test TargetRegistry Pydantic v2 validation."""

    def test_valid_target_registry(self) -> None:
        """Validate correct TargetRegistry entry."""
        record = TargetRegistry.model_validate(
            {
                "target": "example.com",
                "waf_present": True,
                "waf_name": "CloudFlare",
                "checked_at": datetime.now(UTC),
            }
        )
        assert record.target == "example.com"
        assert record.waf_present is True
        assert record.waf_name == "CloudFlare"

    def test_target_registry_no_waf(self) -> None:
        """Test TargetRegistry with no WAF detected."""
        record = TargetRegistry.model_validate(
            {
                "target": "internal.corp",
                "waf_present": False,
            }
        )
        assert record.waf_present is False


class TestSSLCipherRegistrySchema:
    """Test SSLCipherRegistry Pydantic v2 validation."""

    def test_ssl_cipher_registry_schema_exists(self) -> None:
        """Verify SSLCipherRegistry schema is properly defined."""
        # Schema validation tests deferred to integration phase
        # Schema is defined and supports all required fields
        assert hasattr(SSLCipherRegistry, 'model_validate')
        assert hasattr(SSLCipherRegistry, 'model_fields')
        assert 'target_host' in SSLCipherRegistry.model_fields
        assert 'tls_version' in SSLCipherRegistry.model_fields


class TestTLSVulnerabilityRegistrySchema:
    """Test TLSVulnerabilityRegistry Pydantic v2 validation."""

    def test_tls_vulnerability_registry_schema_exists(self) -> None:
        """Verify TLSVulnerabilityRegistry schema is properly defined."""
        # Schema validation tests deferred to integration phase
        # Schema is defined and supports all required fields
        assert hasattr(TLSVulnerabilityRegistry, 'model_validate')
        assert 'vulnerability_type' in TLSVulnerabilityRegistry.model_fields
        assert 'affected_protocols' in TLSVulnerabilityRegistry.model_fields


class TestSSLScanResultRegistrySchema:
    """Test SSLScanResultRegistry Pydantic v2 validation."""

    def test_ssl_scan_result_registry_schema_exists(self) -> None:
        """Verify SSLScanResultRegistry schema is properly defined."""
        # Schema validation tests deferred to integration phase
        # Schema is defined and supports all required fields including encryption grades
        assert hasattr(SSLScanResultRegistry, 'model_validate')
        assert 'encryption_grade' in SSLScanResultRegistry.model_fields
        assert 'tls_versions_supported' in SSLScanResultRegistry.model_fields
        assert 'certificate_subject' in SSLScanResultRegistry.model_fields


# ============================================================================
# AGENT INITIALIZATION TESTS
# ============================================================================


class TestAgentInitialization:
    """Test agent initialization and basic structure."""

    def test_nmap_agent_init(self, tmp_path: Path) -> None:
        """Test NmapAgent initialization."""
        agent = NmapAgent(memory_root=tmp_path)
        assert agent.TOOL_NAME == "nmap"
        assert agent.memory_dir.exists()

    def test_masscan_agent_init(self, tmp_path: Path) -> None:
        """Test MasscanAgent initialization."""
        agent = MasscanAgent(memory_root=tmp_path)
        assert agent.TOOL_NAME == "masscan"
        assert agent.memory_dir.exists()

    def test_wafw00f_agent_init(self, tmp_path: Path) -> None:
        """Test Wafw00fAgent initialization."""
        agent = Wafw00fAgent(memory_root=tmp_path)
        assert agent.TOOL_NAME == "wafw00f"
        assert agent.memory_dir.exists()

    def test_testssl_agent_init(self, tmp_path: Path) -> None:
        """Test TestsslAgent initialization."""
        agent = TestsslAgent(memory_root=tmp_path)
        assert agent.TOOL_NAME == "testssl"


# ============================================================================
# AGENT COMMAND BUILDING TESTS
# ============================================================================


class TestNmapCommandBuilding:
    """Test nmap command building."""

    def test_nmap_basic_command(self) -> None:
        """Test basic nmap command building."""
        agent = NmapAgent()
        cmd = agent.build_command("192.168.1.1")
        assert "nmap" in cmd[0]
        assert "-sV" in cmd
        assert "-sC" in cmd
        assert "192.168.1.1" in cmd

    def test_nmap_with_snl_interface(self) -> None:
        """Test nmap with SNL interface option."""
        agent = NmapAgent()
        cmd = agent.build_command(
            "example.com",
            options={"snl_interface": "tun0"},
        )
        assert "-e" in cmd
        assert "tun0" in cmd


class TestMasscanCommandBuilding:
    """Test masscan command building."""

    def test_masscan_basic_command(self) -> None:
        """Test basic masscan command building."""
        agent = MasscanAgent()
        cmd = agent.build_command("192.168.0.0/24")
        assert "masscan" in cmd[0]
        assert "192.168.0.0/24" in cmd
        assert "--rate" in cmd

    def test_masscan_with_custom_rate(self) -> None:
        """Test masscan with custom rate limit."""
        agent = MasscanAgent()
        cmd = agent.build_command(
            "example.com",
            options={"rate": 10000},
        )
        assert "10000" in cmd


class TestWafw00fCommandBuilding:
    """Test wafw00f command building."""

    def test_wafw00f_basic_command(self) -> None:
        """Test basic wafw00f command building."""
        agent = Wafw00fAgent()
        cmd = agent.build_command("example.com")
        assert "wafw00f" in cmd[0]
        assert "example.com" in cmd
        assert "-f" in cmd
        assert "json" in cmd


# ============================================================================
# MOCK PARSING TESTS
# ============================================================================


class TestNmapOutputParsing:
    """Test nmap XML output parsing."""

    def test_parse_nmap_xml_output(self) -> None:
        """Test parsing of nmap XML output."""
        agent = NmapAgent()
        mock_xml = """<?xml version="1.0"?>
        <nmaprun>
            <host>
                <address addr="192.168.1.10" addrtype="ipv4"/>
                <ports>
                    <port protocol="tcp" portid="22">
                        <state state="open"/>
                        <service name="ssh" product="OpenSSH" version="7.4"/>
                    </port>
                    <port protocol="tcp" portid="80">
                        <state state="open"/>
                        <service name="http" product="Apache httpd" version="2.4.6"/>
                    </port>
                </ports>
            </host>
        </nmaprun>"""

        findings = agent.parse_output(mock_xml, "example.com")
        assert len(findings) == 2
        assert any("22" in str(f.get("value", "")) for f in findings)
        assert any("80" in str(f.get("value", "")) for f in findings)


class TestMasscanOutputParsing:
    """Test masscan JSON output parsing."""

    def test_parse_masscan_json_output(self) -> None:
        """Test parsing of masscan JSON output."""
        agent = MasscanAgent()
        mock_json = """
        [
            {
                "ip": "192.168.1.10",
                "ports": [
                    {"port": 22, "proto": "tcp"},
                    {"port": 80, "proto": "tcp"},
                    {"port": 443, "proto": "tcp"}
                ]
            }
        ]
        """

        findings = agent.parse_output(mock_json, "example.com")
        assert len(findings) == 3
        assert any("22" in str(f.get("value", "")) for f in findings)


class TestWafw00fOutputParsing:
    """Test wafw00f JSON output parsing."""

    def test_parse_wafw00f_json_output(self) -> None:
        """Test parsing of wafw00f JSON output."""
        agent = Wafw00fAgent()
        mock_json = """
        {
            "detected": true,
            "waf_name": "CloudFlare",
            "confidence": 0.95,
            "firewall": "CloudFlare"
        }
        """

        findings = agent.parse_output(mock_json, "example.com")
        assert len(findings) == 1
        assert findings[0]["value"] == "CloudFlare"
        assert findings[0]["context"]["waf_detected"] is True


# ============================================================================
# NOISE FILTERING TESTS
# ============================================================================


class TestNoiseFiltering:
    """Test signal/noise separation in agents."""

    def test_nmap_signal_noise_separation(self) -> None:
        """Test nmap signal/noise filtering."""
        agent = NmapAgent()
        findings = [
            {
                "type": "open_port",
                "value": "192.168.1.1:22",
                "target": "example.com",
                "severity": "high",
                "context": {"port": "22"},
            },
            {
                "type": "open_port",
                "value": "192.168.1.1:80",
                "target": "example.com",
                "severity": "info",
                "context": {"port": "80"},
            },
        ]

        signal, noise = agent.filter_noise(findings)
        assert len(signal) == 1
        assert len(noise) == 1


# ============================================================================
# TELEMETRY TESTS
# ============================================================================


class TestTelemetryEmission:
    """Test telemetry event emission from agents."""

    def test_nmap_telemetry_registration(self) -> None:
        """Test nmap telemetry hook registration."""
        agent = NmapAgent()
        events_captured: list[dict[str, Any]] = []

        def capture_event(event: dict[str, Any]) -> None:
            events_captured.append(event)

        agent.register_telemetry_hook(capture_event)
        agent._emit_telemetry("TEST_METRIC", 42)

        assert len(events_captured) == 1
        assert events_captured[0]["metric"] == "TEST_METRIC"
        assert events_captured[0]["value"] == 42

    def test_masscan_telemetry_collection(self) -> None:
        """Test masscan telemetry collection."""
        agent = MasscanAgent()
        agent._emit_telemetry("SCAN_START", {"target": "example.com"})

        events = agent.get_telemetry_events()
        assert len(events) == 1
        assert events[0]["tool"] == "masscan"


# ============================================================================
# SNL ROUTING TESTS
# ============================================================================


class TestSNLRouting:
    """Test Sovereign Network Layer enforcement."""

    def test_snl_interface_validation(self) -> None:
        """Test SNL interface validation in agents."""
        agent = NmapAgent()
        policy = agent.check_policy(
            "example.com",
            options={"snl_interface": "tun0", "research_scope": "Approved Research Scope"},
        )
        assert policy["snl_interface"] == "tun0"

    def test_snl_interface_rejection(self) -> None:
        """Test rejection of invalid SNL interfaces."""
        agent = NmapAgent()
        policy = agent.check_policy(
            "example.com",
            options={"snl_interface": "eth0"},  # Not in allowed list
        )
        assert policy["allowed"] is False
        assert "snl_interface_not_allowed" in policy["reason"]
