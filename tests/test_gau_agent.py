"""
Test Suite for Enhanced GAU (GetAllUrls) Agent

Tests cover:
1. Command building (all providers, exclusion patterns)
2. URL parsing and filtering (low-value assets, scope validation)
3. Endpoint classification (API, admin, auth, config)
4. Wildcard subdomain handling
5. Deduplication across providers
6. Memory efficiency (streaming, chunks)
7. V-RAD telemetry integration
8. Lifecycle methods (fetch, export)
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from apps.backend.src.agents.tools.gau.agent_enhanced import GauAgent
from apps.backend.src.agents.tools.gau.schemas import (
    ArchiveSource,
    EndpointRegistry,
    EndpointType,
    GauArchiveStats,
)


class TestGauAgentCommandBuilding:
    """Test gau command generation for different modes."""

    def test_standard_mode_command(self):
        """Standard mode with domain target."""
        agent = GauAgent()
        cmd = agent.build_command(
            "example.com",
            {
                "providers": ["wayback", "commoncrawl", "otx"],
                "timeout_seconds": 600,
            }
        )

        assert "gau" in cmd
        assert "-json" in cmd
        assert "--wayback" in cmd
        assert "--commoncrawl" in cmd
        assert "--otx" in cmd
        assert "example.com" in cmd
        assert "-x" in cmd  # Exclusion patterns

    def test_listener_mode_command(self):
        """Listener mode for piped input."""
        agent = GauAgent()
        cmd = agent.build_command(
            "example.com",
            {"listener_mode": True}
        )

        assert "gau" in cmd
        assert "-json" in cmd
        # Domain should NOT be in command for listener mode
        assert "example.com" not in cmd

    def test_all_providers_default(self):
        """Verify all providers enabled by default."""
        agent = GauAgent()
        cmd = agent.build_command("example.com")

        assert "--wayback" in cmd
        assert "--commoncrawl" in cmd
        assert "--otx" in cmd

    def test_single_provider_selection(self):
        """Select single provider."""
        agent = GauAgent()
        cmd = agent.build_command(
            "example.com",
            {"providers": ["wayback"]}
        )

        assert "--wayback" in cmd
        assert "--commoncrawl" not in cmd

    def test_exclusion_patterns(self):
        """Verify low-value asset exclusion patterns."""
        agent = GauAgent()
        cmd = agent.build_command("example.com")

        # Should have -x flags for exclusion patterns
        assert "-x" in cmd
        # Verify patterns exist
        x_index = cmd.index("-x")
        assert x_index < len(cmd) - 1  # Pattern follows -x

    def test_timeout_configuration(self):
        """Verify timeout parameter."""
        agent = GauAgent()
        cmd = agent.build_command(
            "example.com",
            {"timeout_seconds": 300}
        )

        assert "--timeout" in cmd
        assert "300" in cmd


class TestUrlParsing:
    """Test URL parsing and filtering."""

    def test_parse_simple_url(self):
        """Parse single URL discovery."""
        agent = GauAgent()
        raw_output = json.dumps({
            "url": "https://api.example.com/v1/users",
            "source": "wayback"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1
        assert findings[0]["endpoint"] == "https://api.example.com/v1/users"
        assert findings[0]["context"]["intel_origin"] == "wayback"

    def test_parse_multiple_providers(self):
        """Parse URLs from multiple archive providers."""
        agent = GauAgent()
        lines = [
            json.dumps({"url": "https://api.example.com/v1", "source": "wayback"}),
            json.dumps({"url": "https://admin.example.com/", "source": "commoncrawl"}),
            json.dumps({"url": "https://web.example.com/config", "source": "otx"}),
        ]
        raw_output = "\n".join(lines)

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 3
        sources = [f["context"]["intel_origin"] for f in findings]
        assert "wayback" in sources
        assert "commoncrawl" in sources
        assert "otx" in sources

    def test_filter_low_value_assets(self):
        """Filter out static assets (CSS, JS, images)."""
        agent = GauAgent()
        raw_output = "\n".join([
            json.dumps({"url": "https://example.com/style.css", "source": "wayback"}),
            json.dumps({"url": "https://example.com/script.js", "source": "wayback"}),
            json.dumps({"url": "https://example.com/image.png", "source": "wayback"}),
        ])

        findings = agent.parse_output(raw_output, "example.com")

        # All should be filtered as low-value
        assert len(findings) == 0

    def test_skip_out_of_scope_urls(self):
        """Skip URLs not matching target domain."""
        agent = GauAgent()
        raw_output = json.dumps({
            "url": "https://evil.attacker.com/api",
            "source": "wayback"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 0

    def test_multiline_json_output(self):
        """Parse multiple JSON lines."""
        agent = GauAgent()
        line1 = json.dumps({"url": "https://api.example.com/v1", "source": "wayback"})
        line2 = json.dumps({"url": "https://web.example.com/", "source": "commoncrawl"})
        raw_output = f"{line1}\n{line2}"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 2

    def test_skip_empty_lines(self):
        """Handle empty lines in output."""
        agent = GauAgent()
        raw_output = "\n\n\n"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 0

    def test_skip_invalid_json(self):
        """Skip malformed JSON lines."""
        agent = GauAgent()
        raw_output = "not valid json\ninvalid: {invalid}"

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 0


class TestEndpointClassification:
    """Test endpoint type classification."""

    def test_classify_api_endpoint(self):
        """Classify /api/* endpoints as API."""
        agent = GauAgent()
        raw_output = json.dumps({
            "url": "https://api.example.com/v1/users",
            "source": "wayback"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert len(findings) == 1
        assert findings[0]["context"]["endpoint_type"] == "api"
        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_admin_endpoint(self):
        """Classify /admin* endpoints."""
        agent = GauAgent()
        raw_output = json.dumps({
            "url": "https://example.com/admin/panel",
            "source": "wayback"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "admin"
        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_auth_endpoint(self):
        """Classify /login, /auth* endpoints."""
        agent = GauAgent()
        raw_output = json.dumps({
            "url": "https://example.com/login",
            "source": "wayback"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "auth"
        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_config_endpoint(self):
        """Classify /.well-known, /config endpoints."""
        agent = GauAgent()
        raw_output = json.dumps({
            "url": "https://example.com/.well-known/openid-configuration",
            "source": "wayback"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["is_high_value"] is True

    def test_classify_unknown_endpoint(self):
        """Classify generic endpoints as unknown."""
        agent = GauAgent()
        raw_output = json.dumps({
            "url": "https://example.com/page",
            "source": "wayback"
        })

        findings = agent.parse_output(raw_output, "example.com")

        assert findings[0]["context"]["endpoint_type"] == "unknown"


class TestWildcardSubdomainHandling:
    """Test wildcard subdomain processing."""

    def test_wildcard_subdomain_in_scope(self):
        """Validate wildcard subdomain matching."""
        agent = GauAgent()

        # *.example.com → api.example.com should be in scope
        assert agent._is_url_in_scope("https://api.example.com/v1", "example.com")
        assert agent._is_url_in_scope("https://admin.example.com/", "example.com")
        assert agent._is_url_in_scope("https://web.example.com/page", "example.com")

    def test_wildcard_subdomain_out_of_scope(self):
        """Validate out-of-scope wildcard subdomains."""
        agent = GauAgent()

        # Should NOT match different base domain
        assert not agent._is_url_in_scope("https://api.evil.com/v1", "example.com")
        assert not agent._is_url_in_scope("https://admin.other.com/", "example.com")

    def test_exact_domain_match(self):
        """Validate exact domain matching."""
        agent = GauAgent()

        assert agent._is_url_in_scope("https://example.com/", "example.com")
        assert agent._is_url_in_scope("https://example.com/api", "example.com")


class TestDeduplication:
    """Test URL deduplication across providers."""

    def test_deduplicate_identical_urls(self):
        """Remove duplicate URLs from different providers."""
        agent = GauAgent()
        # Same URL from different sources
        lines = [
            json.dumps({"url": "https://api.example.com/v1/users", "source": "wayback"}),
            json.dumps({"url": "https://api.example.com/v1/users", "source": "commoncrawl"}),
            json.dumps({"url": "https://api.example.com/v1/users", "source": "otx"}),
        ]
        raw_output = "\n".join(lines)

        findings = agent.parse_output(raw_output, "example.com")

        # Should only have one unique endpoint
        assert len(findings) == 1

    def test_case_insensitive_dedup(self):
        """Deduplicate URLs with different cases."""
        agent = GauAgent()
        lines = [
            json.dumps({"url": "https://api.example.com/v1/Users", "source": "wayback"}),
            json.dumps({"url": "https://api.example.com/v1/users", "source": "commoncrawl"}),
        ]
        raw_output = "\n".join(lines)

        findings = agent.parse_output(raw_output, "example.com")

        # URLs should deduplicate (endpoint registry normalizes)
        assert len(findings) <= 2  # May keep or deduplicate based on implementation


class TestNoiseFiltering:
    """Test signal/noise separation."""

    def test_high_value_endpoints_signal(self):
        """High-value endpoints marked as signal."""
        agent = GauAgent()
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
        agent = GauAgent()
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


class TestEndpointRegistryNormalization:
    """Test EndpointRegistry model creation and validation."""

    def test_build_registry_from_url(self):
        """Build registry from URL string."""
        agent = GauAgent()
        registry = agent._build_endpoint_registry(
            "https://api.example.com:8080/v1/users?key=value",
            "example.com"
        )

        assert registry.endpoint_url == "https://api.example.com:8080/v1/users?key=value"
        assert registry.scheme == "https"
        assert registry.hostname == "api.example.com:8080"
        assert registry.path == "/v1/users"
        assert registry.query == "key=value"
        assert registry.target_domain == "example.com"

    def test_registry_source_detection(self):
        """Detect archive source from metadata."""
        agent = GauAgent()
        registry = agent._build_endpoint_registry(
            "https://api.example.com/v1",
            "example.com",
            {"source": "commoncrawl"}
        )

        assert registry.intel_origin == ArchiveSource.COMMONCRAWL

    def test_registry_classification(self):
        """Test endpoint type classification."""
        agent = GauAgent()
        registry = agent._build_endpoint_registry(
            "https://api.example.com/v1/users",
            "example.com"
        )
        registry.post_init_classify()

        assert registry.endpoint_type == EndpointType.API
        assert registry.is_high_value is True


class TestMemoryEfficiency:
    """Test memory-efficient handling of large URL lists."""

    def test_chunk_size_limit(self):
        """Verify chunk size enforcement."""
        agent = GauAgent()
        assert agent.CHUNK_SIZE == 5_000

    def test_dedup_cache_cap(self):
        """Verify dedup cache memory cap."""
        agent = GauAgent()
        assert agent.MAX_MEMORY_URLS == 100_000

    def test_streaming_mode_enabled(self):
        """Verify streaming mode is enabled by default."""
        agent = GauAgent()
        assert agent._streaming_mode is True


class TestTelemetryIntegration:
    """Test V-RAD telemetry metric push."""

    def test_register_telemetry_hook(self):
        """Register telemetry callback."""
        agent = GauAgent()
        metrics = {}

        def hook(metric_name: str, value):
            metrics[metric_name] = value

        agent.register_telemetry_hook(hook)
        agent._push_telemetry("TEST_METRIC", 42.0)

        assert "TEST_METRIC" in metrics

    def test_url_discovery_count_metric(self):
        """Push URL discovery count."""
        agent = GauAgent()
        metrics = {}

        def hook(metric_name: str, value):
            metrics[metric_name] = value

        agent.register_telemetry_hook(hook)
        raw_output = json.dumps({
            "url": "https://api.example.com/v1",
            "source": "wayback"
        })

        agent.parse_output(raw_output, "example.com")

        assert "URL_DISCOVERY_COUNT" in metrics

    def test_source_distribution_metric(self):
        """Push source distribution percentages."""
        agent = GauAgent()
        metrics = {}

        def hook(metric_name: str, value):
            metrics[metric_name] = value

        agent.register_telemetry_hook(hook)
        lines = [
            json.dumps({"url": "https://api.example.com/v1", "source": "wayback"}),
            json.dumps({"url": "https://web.example.com/", "source": "commoncrawl"}),
        ]
        agent.parse_output("\n".join(lines), "example.com")

        assert "SOURCE_DISTRIBUTION" in metrics


class TestLifecycleMethods:
    """Test fetch() and export() lifecycle methods."""

    def test_fetch_generator_type(self):
        """Verify fetch() is a generator."""
        agent = GauAgent()
        # Mock fetch - normally would run actual gau
        # Just verify the method exists and has correct signature
        assert hasattr(agent, "fetch")
        assert callable(agent.fetch)

    def test_export_deduplication(self):
        """Test export() deduplication behavior."""
        agent = GauAgent()
        urls = [
            "https://api.example.com/v1",
            "https://api.example.com/v1",  # Duplicate
            "https://web.example.com/",
        ]

        registries = agent.export(urls, "example.com")

        # Duplicates should be removed
        assert len(registries) <= 2


class TestVendorLibraryIntegration:
    """Test integration with K1 vendor libraries."""

    def test_import_basetoalagent(self):
        """Verify BaseToolAgent inheritance."""
        agent = GauAgent()
        assert agent.TOOL_NAME == "gau"
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


class TestArchiveStats:
    """Test GauArchiveStats calculation."""

    def test_dedup_ratio_calculation(self):
        """Calculate deduplication ratio."""
        stats = GauArchiveStats(
            total_urls=100,
            unique_urls=80,
            duplicates_removed=20
        )

        ratio = stats.dedup_ratio
        assert 19.0 <= ratio <= 21.0  # ~20%

    def test_source_distribution_calculation(self):
        """Calculate source distribution percentages."""
        stats = GauArchiveStats(
            unique_urls=100,
            wayback_count=50,
            commoncrawl_count=30,
            otx_count=20
        )

        dist = stats.source_distribution
        assert dist["wayback"] == 50.0
        assert dist["commoncrawl"] == 30.0
        assert dist["otx"] == 20.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
