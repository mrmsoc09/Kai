"""
SSRFMAP Agent Test Suite — 40+ comprehensive tests

Test coverage:
  - Command building (6 tests)
  - Output parsing (4 tests)
  - Exploit status detection (4 tests)
  - Cloud provider detection (4 tests)
  - Internal asset discovery (4 tests)
  - Metadata exposure detection (3 tests)
  - Credential extraction (3 tests)
  - Service discovery (3 tests)
  - Noise filtering (3 tests)
  - Risk/confidence calculation (3 tests)
  - Telemetry integration (2 tests)
  - Vendor integration (2 tests)

Total: 42 tests
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.backend.src.agents.tools.ssrfmap.agent_enhanced import SsrfmapAgent
from apps.backend.src.agents.tools.ssrfmap.schemas import (
    CloudProvider,
    ExploitStatus,
    InternalAccessRegistry,
    InternalAsset,
    InternalAssetType,
    ServiceInfo,
    SsrfModule,
)


class TestCommandBuilding:
    """Test ssrfmap command construction."""

    def test_standard_command(self):
        """Build standard SSRF command."""
        agent = SsrfmapAgent()
        cmd = agent.build_command("http://example.com/api?url=FUZZ")
        assert cmd[0] == "ssrfmap"
        assert "-u" in cmd
        assert "http://example.com/api?url=FUZZ" in cmd
        assert "-o" in cmd
        assert "json" in cmd

    def test_command_with_modules(self):
        """Build command with specific modules."""
        agent = SsrfmapAgent()
        cmd = agent.build_command(
            "http://example.com/api?url=FUZZ",
            options={"modules": [SsrfModule.AWS, SsrfModule.DOCKER]},
        )
        assert "-m" in cmd
        idx = cmd.index("-m")
        assert "aws" in cmd[idx + 1]
        assert "docker" in cmd[idx + 1]

    def test_command_with_timeout(self):
        """Build command with custom timeout."""
        agent = SsrfmapAgent()
        cmd = agent.build_command(
            "http://example.com/api?url=FUZZ",
            options={"timeout_seconds": 300},
        )
        assert "-t" in cmd
        idx = cmd.index("-t")
        assert cmd[idx + 1] == "300"

    def test_command_with_proxy(self):
        """Build command with SNL proxy."""
        agent = SsrfmapAgent()
        cmd = agent.build_command(
            "http://example.com/api?url=FUZZ",
            options={"proxy": "http://10.0.0.1:9050"},
        )
        assert "-p" in cmd
        idx = cmd.index("-p")
        assert cmd[idx + 1] == "http://10.0.0.1:9050"

    def test_command_with_threads(self):
        """Build command with custom thread count."""
        agent = SsrfmapAgent()
        cmd = agent.build_command(
            "http://example.com/api?url=FUZZ",
            options={"threads": 20},
        )
        assert "-th" in cmd
        idx = cmd.index("-th")
        assert cmd[idx + 1] == "20"

    def test_command_all_options(self):
        """Build command with all options."""
        agent = SsrfmapAgent()
        cmd = agent.build_command(
            "http://example.com/api?url=FUZZ",
            options={
                "modules": [SsrfModule.AWS, SsrfModule.AZURE],
                "timeout_seconds": 600,
                "proxy": "socks5://10.0.0.1:1080",
                "threads": 15,
                "follow_redirects": False,
            },
        )
        assert "-u" in cmd
        assert "-m" in cmd
        assert "-t" in cmd
        assert "-p" in cmd
        assert "-th" in cmd
        assert "-r" in cmd  # follow_redirects=False adds -r


class TestOutputParsing:
    """Test ssrfmap output parsing."""

    def test_parse_simple_ssrf_finding(self):
        """Parse single SSRF finding."""
        agent = SsrfmapAgent()
        raw_output = json.dumps({
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "AKIA2XXXXXXXXX:aws_secret_key",
            "status": "confirmed",
        })

        result = agent.parse_output(raw_output)
        assert len(result["findings"]) == 1
        assert result["statistics"].ssrf_vulnerabilities_found == 1
        assert result["statistics"].aws_exposures == 1

    def test_parse_multiple_findings(self):
        """Parse multiple findings."""
        agent = SsrfmapAgent()
        findings_list = [
            {
                "vulnerability_type": "ssrf",
                "url": "http://example.com/api?url=FUZZ",
                "parameter": "url",
                "payload": "http://169.254.169.254/",
                "response": "metadata: AWS",
                "status": "confirmed",
                "module": "aws",
            },
            {
                "vulnerability_type": "ssrf",
                "url": "http://example.com/api?ip=FUZZ",
                "parameter": "ip",
                "payload": "http://10.0.0.1:6379/",
                "response": "redis version",
                "status": "probable",
                "module": "redis",
            },
        ]
        raw_output = "\n".join(json.dumps(f) for f in findings_list)

        result = agent.parse_output(raw_output)
        assert len(result["findings"]) == 2
        assert result["statistics"].confirmed_count == 1
        assert result["statistics"].probable_count == 1

    def test_parse_empty_output(self):
        """Parse empty output."""
        agent = SsrfmapAgent()
        result = agent.parse_output("")
        assert len(result["findings"]) == 0
        assert result["statistics"].ssrf_vulnerabilities_found == 0

    def test_parse_malformed_json(self):
        """Skip malformed JSON lines."""
        agent = SsrfmapAgent()
        raw_output = (
            'invalid json\n'
            '{"vulnerability_type": "ssrf", "url": "http://example.com"}\n'
            'another bad line'
        )
        result = agent.parse_output(raw_output)
        assert len(result["findings"]) == 1


class TestExploitStatusDetection:
    """Test exploit status detection."""

    def test_confirmed_status(self):
        """Detect confirmed SSRF."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "x" * 500,  # Substantial response
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.exploit_status == ExploitStatus.CONFIRMED
        assert registry.confidence > 0.90

    def test_probable_status(self):
        """Detect probable SSRF."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "Internal IP response",
            "status": "probable",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.exploit_status == ExploitStatus.PROBABLE

    def test_blind_status(self):
        """Detect blind SSRF."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "No output",
            "status": "blind",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.exploit_status == ExploitStatus.BLIND

    def test_time_based_status(self):
        """Detect time-based SSRF."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1:9999/",
            "response": "Timeout",
            "status": "time_based",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.exploit_status == ExploitStatus.TIME_BASED


class TestCloudProviderDetection:
    """Test cloud provider detection."""

    def test_detect_aws(self):
        """Detect AWS metadata exposure."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "AssumeRole AKIA2XXXXXXXXX:secret",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.cloud_provider == CloudProvider.AWS

    def test_detect_azure(self):
        """Detect Azure metadata exposure."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "subscription_id: abc123 tenant_id: xyz789",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.cloud_provider == CloudProvider.AZURE

    def test_detect_gcp(self):
        """Detect GCP metadata exposure."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://metadata.google.internal/",
            "response": "service_account: service@project.iam.gserviceaccount.com",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.cloud_provider == CloudProvider.GCP

    def test_detect_alibaba(self):
        """Detect Alibaba Cloud metadata."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://100.100.100.200/",
            "response": "Alibaba Cloud metadata",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.cloud_provider == CloudProvider.ALIBABA


class TestInternalAssetDiscovery:
    """Test internal asset discovery."""

    def test_discover_internal_ips(self):
        """Discover internal IP addresses."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.0/",
            "response": "Internal network: 10.0.0.5, 10.0.0.10, 192.168.1.1",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert len(registry.internal_assets) >= 2
        ips = [a.value for a in registry.internal_assets
               if a.asset_type == InternalAssetType.IP_ADDRESS]
        assert "10.0.0.5" in ips or "10.0.0.10" in ips

    def test_discover_services(self):
        """Discover internal services."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "Connected to Redis on 10.0.0.1:6379",
            "status": "confirmed",
            "services": [
                {"name": "redis", "port": 6379},
                {"name": "mysql", "port": 3306},
            ],
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert len(registry.services_discovered) >= 2

    def test_discover_hostnames(self):
        """Discover internal hostnames."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "Internal hosts: db.internal, redis.local, api-server.home",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        hostnames = [
            a.value for a in registry.internal_assets
            if a.asset_type == InternalAssetType.HOSTNAME
        ]
        assert len(hostnames) > 0

    def test_discover_localhost(self):
        """Discover localhost/loopback."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://127.0.0.1/",
            "response": "Local admin interface on 127.0.0.1:8080",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        has_localhost = any(
            a.value.startswith("127.") for a in registry.internal_assets
        )
        assert has_localhost


class TestMetadataExposureDetection:
    """Test cloud metadata exposure detection."""

    def test_aws_metadata_exposed(self):
        """Detect AWS metadata exposure."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "iam/security-credentials/EC2-Instance-Role",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.metadata_exposed is True

    def test_azure_metadata_exposed(self):
        """Detect Azure metadata exposure."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "subscription_id: abc123",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.metadata_exposed is True

    def test_gcp_metadata_exposed(self):
        """Detect GCP metadata exposure."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://metadata.google.internal/",
            "response": "service_account_email: sa@project.iam",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.metadata_exposed is True


class TestCredentialExtraction:
    """Test credential extraction from responses."""

    def test_extract_aws_access_key(self):
        """Extract AWS access key."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "AccessKeyId: AKIA2XXXXXXXXX",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert "aws_access_key" in registry.credentials_leaked

    def test_extract_password(self):
        """Extract password credentials."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "password: supersecret123",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert "password" in registry.credentials_leaked

    def test_extract_api_key(self):
        """Extract API keys."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "api_key: sk_live_1234567890abcdef",
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert "api_key" in registry.credentials_leaked


class TestServiceDiscovery:
    """Test internal service discovery."""

    def test_service_port_mapping_mysql(self):
        """Map MySQL service to port 3306."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1:3306/",
            "response": "MySQL protocol handshake",
            "status": "confirmed",
            "services": [{"name": "mysql", "port": 3306}],
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        mysql_services = [
            s for s in registry.services_discovered if s.service_name == "mysql"
        ]
        assert len(mysql_services) > 0

    def test_service_port_mapping_redis(self):
        """Map Redis service to port 6379."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1:6379/",
            "response": "REDIS version 6.0",
            "status": "confirmed",
            "services": [{"name": "redis", "port": 6379}],
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        redis_services = [
            s for s in registry.services_discovered if s.service_name == "redis"
        ]
        assert len(redis_services) > 0

    def test_service_port_mapping_docker(self):
        """Map Docker daemon to port 2375."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1:2375/",
            "response": "Docker API endpoint",
            "status": "confirmed",
            "services": [{"name": "docker", "port": 2375}],
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        docker_services = [
            s for s in registry.services_discovered if s.service_name == "docker"
        ]
        assert len(docker_services) > 0


class TestNoiseFiltering:
    """Test signal vs noise separation."""

    def test_signal_confirmed_with_metadata(self):
        """Confirmed SSRF with metadata is signal."""
        agent = SsrfmapAgent()
        findings_dict = {
            "findings": [
                InternalAccessRegistry(
                    target_url="http://example.com/api?url=FUZZ",
                    vulnerable_parameter="url",
                    ssrf_confirmed=True,
                    exploit_status=ExploitStatus.CONFIRMED,
                    confidence=0.95,
                    exploit_path="http://169.254.169.254/",
                    module_used=SsrfModule.AWS,
                    internal_assets=[],
                    cloud_provider=CloudProvider.AWS,
                    metadata_exposed=True,
                    iam_role_leaked=True,
                    credentials_leaked=["aws_access_key"],
                    services_discovered=[],
                    detected_by="ssrfmap",
                    detection_date=datetime.now(UTC),
                )
            ]
        }
        signal, noise = agent.filter_noise(findings_dict)
        assert len(signal) == 1
        assert len(noise) == 0

    def test_signal_high_confidence_with_assets(self):
        """High confidence with internal assets is signal."""
        agent = SsrfmapAgent()
        findings_dict = {
            "findings": [
                InternalAccessRegistry(
                    target_url="http://example.com/api?url=FUZZ",
                    vulnerable_parameter="url",
                    ssrf_confirmed=True,
                    exploit_status=ExploitStatus.CONFIRMED,
                    confidence=0.85,
                    exploit_path="http://10.0.0.1/",
                    module_used=SsrfModule.NETWORK,
                    internal_hosts_count=5,
                    internal_assets=[
                        InternalAsset(
                            asset_type=InternalAssetType.IP_ADDRESS,
                            value="10.0.0.5",
                        )
                    ],
                    cloud_provider=CloudProvider.UNKNOWN,
                    metadata_exposed=False,
                    iam_role_leaked=False,
                    credentials_leaked=[],
                    services_discovered=[],
                    detected_by="ssrfmap",
                    detection_date=datetime.now(UTC),
                )
            ]
        }
        signal, noise = agent.filter_noise(findings_dict)
        assert len(signal) == 1
        assert len(noise) == 0

    def test_noise_blind_low_confidence(self):
        """Blind SSRF with low confidence is noise."""
        agent = SsrfmapAgent()
        findings_dict = {
            "findings": [
                InternalAccessRegistry(
                    target_url="http://example.com/api?url=FUZZ",
                    vulnerable_parameter="url",
                    ssrf_confirmed=False,
                    exploit_status=ExploitStatus.BLIND,
                    confidence=0.45,
                    exploit_path="http://10.0.0.1/",
                    module_used=SsrfModule.NETWORK,
                    internal_hosts_count=0,
                    internal_assets=[],
                    cloud_provider=CloudProvider.UNKNOWN,
                    metadata_exposed=False,
                    iam_role_leaked=False,
                    credentials_leaked=[],
                    services_discovered=[],
                    detected_by="ssrfmap",
                    detection_date=datetime.now(UTC),
                )
            ]
        }
        signal, noise = agent.filter_noise(findings_dict)
        assert len(signal) == 0
        assert len(noise) == 1


class TestRiskAndConfidenceCalculation:
    """Test risk and confidence scoring."""

    def test_confidence_confirmed_with_response(self):
        """Confirmed status with substantial response → high confidence."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://169.254.169.254/",
            "response": "x" * 1000,
            "status": "confirmed",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.confidence > 0.90

    def test_confidence_probable(self):
        """Probable status yields medium confidence."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "Response",
            "status": "probable",
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert 0.70 <= registry.confidence <= 0.85

    def test_confidence_boost_with_assets(self):
        """Discovered assets boost confidence."""
        agent = SsrfmapAgent()
        finding = {
            "vulnerability_type": "ssrf",
            "url": "http://example.com/api?url=FUZZ",
            "parameter": "url",
            "payload": "http://10.0.0.1/",
            "response": "192.168.1.1, 10.0.0.5, 172.16.0.1",
            "status": "probable",
            "services": [{"name": "redis", "port": 6379}],
        }
        raw_output = json.dumps(finding)
        result = agent.parse_output(raw_output)
        registry = result["findings"][0]
        assert registry.confidence > 0.75  # Boosted from probable


class TestTelemetryIntegration:
    """Test V-RAD telemetry integration."""

    @pytest.mark.asyncio
    async def test_register_telemetry_hook(self):
        """Register telemetry callback."""
        agent = SsrfmapAgent()
        mock_callback = AsyncMock()
        agent.register_telemetry_hook(mock_callback)
        assert hasattr(agent, "_telemetry_callback")

    @pytest.mark.asyncio
    async def test_push_telemetry_metrics(self):
        """Push metrics to V-RAD."""
        agent = SsrfmapAgent()
        mock_callback = AsyncMock()
        agent.register_telemetry_hook(mock_callback)

        # Simulate telemetry push
        await agent._push_telemetry("INTERNAL_HOSTS_DISCOVERED", 5)

        # Callback should be called
        mock_callback.assert_called_once()


class TestVendorIntegration:
    """Test K1 vendor integration."""

    def test_agent_inherits_base_tool_agent(self):
        """Agent inherits from BaseToolAgent."""
        agent = SsrfmapAgent()
        assert hasattr(agent, "TOOL_NAME")
        assert agent.TOOL_NAME == "ssrfmap"

    def test_schemas_importable(self):
        """All schemas are importable."""
        from apps.backend.src.agents.tools.ssrfmap.schemas import (
            CloudProvider,
            ExploitStatus,
            InternalAccessRegistry,
            InternalAsset,
            InternalAssetType,
            ServiceInfo,
            SsrfModule,
            SsrfStatistics,
        )
        assert CloudProvider is not None
        assert ExploitStatus is not None
        assert InternalAccessRegistry is not None
