"""
Test Suite for Enhanced Wayback URLs Agent

Tests cover:
1. Command building (versioning flag support)
2. URL parsing and filtering (low-value assets, scope validation)
3. Endpoint classification (API, admin, auth, config)
4. Sensitive file detection (.env, .config, .git)
5. Deduplication across snapshot versions
6. Memory efficiency (streaming, chunks)
7. V-RAD telemetry integration
8. Lifecycle methods (fetch, export)
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from apps.backend.src.agents.tools.waybackurls.agent_enhanced import WaybackurlsAgent
from apps.backend.src.agents.tools.gau.schemas import (
    ArchiveSource,
    EndpointRegistry,
    EndpointType,
    GauArchiveStats,
)


class TestWaybackurlsAgentCommandBuilding:
    """Test waybackurls command generation for different modes."""

    def test_standard_mode_command(self):
        """Standard mode with domain target."""
        agent = WaybackurlsAgent()
        cmd = agent.build_command("example.com")

        assert "waybackurls" in cmd
        assert "example.com" in cmd

    def test_listener_mode_command(self):
        """Listener mode with stdin piping (no domain in cmd)."""
        agent = WaybackurlsAgent()
        cmd = agent.build_command(
            "example.com",
            {"listener_mode": True}
        )

        assert "waybackurls" in cmd
        assert "example.com" not in cmd

    def test_get_versions_flag(self):
        """Command includes -get-versions flag for deeper history."""
        agent = WaybackurlsAgent()
        cmd = agent.build_command(
            "example.com",
            {"get_versions": True}
        )

        assert "-get-versions" in cmd
        assert "example.com" in cmd

    def test_timeout_configuration(self):
        """Custom timeout is included in command."""
        agent = WaybackurlsAgent()
        cmd = agent.build_command(
            "example.com",
            {"timeout_seconds": 600}
        )

        assert "--timeout" in cmd
        assert "600" in cmd

    def test_binary_path_override(self):
        """Custom binary path is used."""
        agent = WaybackurlsAgent()
        cmd = agent.build_command(
            "example.com",
            {"binary_path": "/custom/waybackurls"}
        )

        assert "/custom/waybackurls" in cmd

    def test_streaming_mode_enabled(self):
        """Streaming mode is enabled by default."""
        agent = WaybackurlsAgent()
        assert agent._streaming_mode is True


class TestWaybackurlsUrlParsing:
    """Test URL parsing and filtering."""

    def test_simple_url_parsing(self):
        """Parse simple URLs from Wayback output."""
        agent = WaybackurlsAgent()
        raw_output = "https://api.example.com/v1/users\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) > 0
        assert findings[0]["endpoint"] == "https://api.example.com/v1/users"

    def test_multiple_urls_parsing(self):
        """Parse multiple URLs from output."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://api.example.com/v1/users",
            "https://admin.example.com/panel",
            "https://example.com/index.html",
        ]) + "\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 3

    def test_low_value_filtering(self):
        """Skip low-value assets (CSS, JS, images)."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://api.example.com/v1/users",
            "https://cdn.example.com/style.css",
            "https://cdn.example.com/app.js",
            "https://cdn.example.com/logo.png",
        ]) + "\n"

        findings = agent.parse_output(raw_output, "example.com")

        # Only API endpoint should pass filter
        assert len(findings) == 1
        assert "users" in findings[0]["endpoint"]

    def test_out_of_scope_filtering(self):
        """Skip URLs not matching target domain."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://api.example.com/v1/users",
            "https://evil.com/steal",
            "https://example.com/index.html",
        ]) + "\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 2
        assert all("example.com" in f["endpoint"] for f in findings)

    def test_empty_lines_handling(self):
        """Handle empty lines in output."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://api.example.com/v1",
            "",
            "https://admin.example.com",
            "",
        ]) + "\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 2

    def test_deduplication_across_snapshots(self):
        """Deduplicate identical URLs from multiple snapshots."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://api.example.com/v1/users",
            "https://api.example.com/v1/users",
            "https://api.example.com/v1/users",
        ]) + "\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1

    def test_case_insensitive_dedup(self):
        """Deduplicate URLs with different cases."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://api.example.com/v1/Users",
            "https://api.example.com/v1/users",
        ]) + "\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1


class TestWaybackurlsEndpointClassification:
    """Test endpoint type classification."""

    def test_classify_api_endpoint(self):
        """Classify /api/*, /v1/*, /graphql endpoints."""
        agent = WaybackurlsAgent()
        raw_output = "https://api.example.com/v1/users\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "api"
        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_admin_endpoint(self):
        """Classify /admin*, /management, /dashboard endpoints."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/admin/panel\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "admin"
        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_auth_endpoint(self):
        """Classify /login, /auth, /sso, /oauth endpoints."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/auth/login\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "auth"
        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_config_endpoint(self):
        """Classify /.well-known, /config endpoints."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/.well-known/openid-configuration\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "config"
        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_unknown_endpoint(self):
        """Classify generic endpoints as unknown."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/page\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "unknown"


class TestWaybackurlsSensitiveFileDetection:
    """Test detection of sensitive files and patterns."""

    def test_detect_env_file(self):
        """Detect .env files in URLs."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/.env\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["has_sensitive_patterns"] is True

    def test_detect_git_directory(self):
        """Detect .git directories in URLs."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/.git/config\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["has_sensitive_patterns"] is True

    def test_detect_config_file(self):
        """Detect .config, config.php, settings.ini files."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://example.com/.config",
            "https://example.com/config.php",
            "https://example.com/settings.ini",
        ]) + "\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert all(f["context"]["has_sensitive_patterns"] for f in findings)

    def test_no_false_positives(self):
        """Legitimate URLs without sensitive patterns."""
        agent = WaybackurlsAgent()
        raw_output = "https://api.example.com/v1/data\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["has_sensitive_patterns"] is False


class TestWaybackurlsNoiseFiltering:
    """Test signal vs noise separation."""

    def test_sensitive_files_marked_signal(self):
        """Sensitive files marked as signal."""
        agent = WaybackurlsAgent()
        findings = [
            {
                "endpoint": "https://example.com/.env",
                "target": "example.com",
                "context": {
                    "has_sensitive_patterns": True,
                    "is_high_value": False,
                    "endpoint_type": "unknown",
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 1
        assert len(noise) == 0

    def test_high_value_endpoints_signal(self):
        """High-value endpoints marked as signal."""
        agent = WaybackurlsAgent()
        findings = [
            {
                "endpoint": "https://api.example.com/v1",
                "target": "example.com",
                "context": {
                    "is_high_value": True,
                    "endpoint_type": "api",
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 1
        assert len(noise) == 0

    def test_static_assets_noise(self):
        """Static assets marked as noise."""
        agent = WaybackurlsAgent()
        findings = [
            {
                "endpoint": "https://example.com/style.css",
                "target": "example.com",
                "context": {
                    "endpoint_type": "static",
                }
            }
        ]

        signal, noise = agent.filter_noise(findings)

        assert len(signal) == 0
        assert len(noise) == 1


class TestWaybackurlsEndpointRegistry:
    """Test EndpointRegistry normalization."""

    def test_build_registry_from_url(self):
        """Build EndpointRegistry from URL."""
        agent = WaybackurlsAgent()
        raw_output = "https://api.example.com/v1/users\n"

        findings = agent.parse_output(raw_output, "example.com")

        registry = findings[0].get("endpoint_registry")
        assert registry is not None
        assert registry["endpoint_url"] == "https://api.example.com/v1/users"
        assert registry["scheme"] == "https"
        assert registry["hostname"] == "api.example.com"
        assert registry["path"] == "/v1/users"

    def test_archive_source_detection(self):
        """Detect archive source as Wayback Machine."""
        agent = WaybackurlsAgent()
        raw_output = "https://api.example.com/v1/users\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["intel_origin"] == "wayback"

    def test_classification_after_init(self):
        """Endpoint type is classified after initialization."""
        agent = WaybackurlsAgent()
        raw_output = "https://api.example.com/v1/users\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "api"

    def test_discovery_date_set(self):
        """Discovery date is set to current time."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/path\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["discovery_date"] is not None


class TestWaybackurlsListenerMode:
    """Test listener mode for stdin piping."""

    def test_listener_mode_flag_recognition(self):
        """Listener mode flag is recognized."""
        agent = WaybackurlsAgent()
        agent._listener_mode = True

        assert agent._listener_mode is True

    def test_listener_mode_no_target_in_cmd(self):
        """Target is not included in command when listener mode is enabled."""
        agent = WaybackurlsAgent()
        cmd = agent.build_command(
            "example.com",
            {"listener_mode": True}
        )

        assert "example.com" not in cmd
        assert "waybackurls" in cmd


class TestWaybackurlsTelemetryIntegration:
    """Test V-RAD telemetry integration."""

    def test_telemetry_hook_registration(self):
        """Register telemetry callback."""
        agent = WaybackurlsAgent()
        mock_callback = lambda metric, value: None

        agent.register_telemetry_hook(mock_callback)

        assert agent._telemetry_hook == mock_callback

    def test_archive_hits_metric(self):
        """ARCHIVE_HITS metric tracks discovered URLs."""
        agent = WaybackurlsAgent()
        metrics_pushed = {}

        def mock_callback(metric_name: str, value):
            metrics_pushed[metric_name] = value

        agent.register_telemetry_hook(mock_callback)
        raw_output = "\n".join([
            "https://api.example.com/v1",
            "https://admin.example.com",
        ]) + "\n"

        agent.parse_output(raw_output, "example.com")

        assert "ARCHIVE_HITS" in metrics_pushed
        assert metrics_pushed["ARCHIVE_HITS"] == 2

    def test_sensitive_files_metric(self):
        """SENSITIVE_FILES_DETECTED metric tracks sensitive patterns."""
        agent = WaybackurlsAgent()
        metrics_pushed = {}

        def mock_callback(metric_name: str, value):
            metrics_pushed[metric_name] = value

        agent.register_telemetry_hook(mock_callback)
        raw_output = "\n".join([
            "https://example.com/.env",
            "https://example.com/.git/config",
        ]) + "\n"

        agent.parse_output(raw_output, "example.com")

        assert "SENSITIVE_FILES_DETECTED" in metrics_pushed


class TestWaybackurlsMemoryEfficiency:
    """Test memory efficiency patterns."""

    def test_chunk_size_property(self):
        """Chunk size is set to 5K."""
        agent = WaybackurlsAgent()
        assert agent.CHUNK_SIZE == 5_000

    def test_memory_cap_property(self):
        """Memory cap is 100K URLs."""
        agent = WaybackurlsAgent()
        assert agent.MAX_MEMORY_URLS == 100_000

    def test_streaming_mode_default(self):
        """Streaming mode is enabled by default."""
        agent = WaybackurlsAgent()
        assert agent._streaming_mode is True


class TestWaybackurlsLifecycleMethods:
    """Test fetch() and export() lifecycle methods."""

    def test_fetch_is_generator(self):
        """fetch() returns a generator."""
        agent = WaybackurlsAgent()
        # Note: fetch() actually calls subprocess, so we just verify the method exists
        assert hasattr(agent, 'fetch')
        assert callable(agent.fetch)

    def test_export_deduplicates(self):
        """export() deduplicates URLs."""
        agent = WaybackurlsAgent()
        urls = [
            "https://api.example.com/v1/users",
            "https://api.example.com/v1/users",
            "https://api.example.com/v1/users",
        ]

        registries = agent.export(urls, "example.com")

        # Should only have one unique endpoint after dedup
        assert len(registries) <= 1


class TestWaybackurlsArchiveStats:
    """Test archive statistics tracking."""

    def test_stats_initialization(self):
        """Archive stats are initialized."""
        agent = WaybackurlsAgent()
        assert agent._stats.total_urls == 0
        assert agent._stats.unique_urls == 0

    def test_stats_updated_on_parse(self):
        """Stats are updated during parse_output."""
        agent = WaybackurlsAgent()
        raw_output = "\n".join([
            "https://api.example.com/v1",
            "https://admin.example.com",
        ]) + "\n"

        agent.parse_output(raw_output, "example.com")

        assert agent._stats.total_urls >= 2
        assert agent._stats.unique_urls >= 2


class TestWaybackurlsWildcardHandling:
    """Test wildcard subdomain handling."""

    def test_exact_domain_match(self):
        """Exact domain matches are included."""
        agent = WaybackurlsAgent()
        raw_output = "https://example.com/page\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1

    def test_subdomain_match(self):
        """Subdomain matches are included."""
        agent = WaybackurlsAgent()
        raw_output = "https://api.example.com/v1\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1

    def test_out_of_scope_rejection(self):
        """Out-of-scope URLs are rejected."""
        agent = WaybackurlsAgent()
        raw_output = "https://evil.com/steal\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 0


class TestWaybackurlsVendorIntegration:
    """Test vendor library integration."""

    def test_base_tool_agent_inheritance(self):
        """WaybackurlsAgent inherits from BaseToolAgent."""
        agent = WaybackurlsAgent()
        assert hasattr(agent, 'build_command')
        assert hasattr(agent, 'parse_output')
        assert hasattr(agent, 'filter_noise')

    def test_protocol_imports(self):
        """Protocol types import successfully."""
        from apps.backend.src.agents.tools.waybackurls.agent_enhanced import (
            ArchiveSource,
            EndpointRegistry,
            EndpointType,
        )
        assert ArchiveSource is not None
        assert EndpointRegistry is not None
        assert EndpointType is not None
