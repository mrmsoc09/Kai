"""
Enhanced GAU (GetAllUrls) Archive Agent for K1 Platform

Responsible for historical URL discovery and endpoint registry population.

Features:
- Lifecycle management: fetch() and export() for large-scale URL lists
- Multi-provider support: Wayback, CommonCrawl, OTX by default
- Memory-efficient: Streaming JSON, dedup cache with resource limits
- Smart filtering: Excludes low-value assets (fonts, images, CSS)
- V-RAD integration: URL_DISCOVERY_COUNT, SOURCE_DISTRIBUTION metrics
- OPSEC layer: Sovereign Network Layer routing for provider queries
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)

from ..base_tool_agent import BaseToolAgent
from .schemas import (
    ArchiveSource,
    EndpointRegistry,
    EndpointType,
    GauArchiveStats,
    HttpMethod,
)

# Low-value asset extensions to filter
_LOW_VALUE_EXTENSIONS = {
    ".css", ".js", ".json", ".xml",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".webm", ".mov",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}

# High-value endpoint patterns
_HIGH_VALUE_PATTERNS = {
    "/api/", "/v1/", "/v2/", "/v3/", "/graphql", "/rest/",
    "/admin", "/management", "/dashboard", "/console",
    "/login", "/auth", "/sso", "/oauth",
    "/config", "/.well-known", "/internal",
    "/webhook", "/callback", "/upload",
}

# Subdomain wildcard patterns
_WILDCARD_PATTERNS = {
    "*.example.com", "*.target.com", "*.api.", "*.admin.",
}


class GauAgent(BaseToolAgent):
    """
    Archive URL Discovery Agent with lifecycle management and memory efficiency.

    Execution modes:
    1. Standard: gau <domain> (direct domain query)
    2. Listener: stdin pipe (chained input)
    3. Batch: Multiple domains from file

    Supports all providers by default: Wayback, CommonCrawl, OTX
    """

    TOOL_NAME = "gau"
    DEFAULT_TIMEOUT_SECONDS = 600
    MAX_MEMORY_URLS = 100_000  # Cap for in-memory dedup cache
    CHUNK_SIZE = 5_000  # Export/fetch in chunks to prevent overflow

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._telemetry_hook: Callable | None = None
        self._listener_mode = False
        self._dedup_cache: set[str] = set()
        self._stats = GauArchiveStats()
        self._streaming_mode = True  # Use streaming for large lists

    def register_telemetry_hook(self, hook: Callable[[str, str | float | dict], None]) -> None:
        """Register callback for real-time V-RAD telemetry push.

        Args:
            hook: Callable(metric_name: str, value: str | float | dict) -> None
        """
        self._telemetry_hook = hook

    def _push_telemetry(self, metric_name: str, value: str | float | dict) -> None:
        """Push metric to V-RAD dashboard via telemetry hook."""
        if self._telemetry_hook:
            try:
                self._telemetry_hook(metric_name, value)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Telemetry push failed: {e}")

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        """Build gau command for historical URL discovery.

        Supports all archive providers and filters low-value assets.
        """
        opts = options or {}
        self._listener_mode = bool(opts.get("listener_mode", False))

        binary = str(opts.get("binary_path", "gau"))

        # Base command with JSON output
        cmd = [binary, "-json"]

        # All providers by default
        providers = opts.get("providers", ["wayback", "commoncrawl", "otx"])
        if isinstance(providers, list):
            for provider in providers:
                cmd.append(f"--{provider}")

        # Exclude low-value assets (CRITICAL for data quality)
        exclude_patterns = opts.get("exclude_patterns", [
            "\\.(css|js|json|xml|woff|woff2|ttf|otf|eot|png|jpg|jpeg|gif|svg|ico|webp)$",
            "\\.(pdf|zip|gz|tar|bz2|7z|rar|doc|docx|xls|xlsx)$",
        ])
        if exclude_patterns:
            for pattern in exclude_patterns:
                cmd += ["-x", pattern]

        # Timeout (gau has built-in timeout handling)
        timeout_seconds = int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS))
        if timeout_seconds > 0:
            cmd += ["--timeout", str(timeout_seconds)]

        # Streaming mode for large datasets
        if opts.get("streaming", self._streaming_mode):
            # gau streams by default, no flag needed
            pass

        # Input source (unless listener mode)
        if not self._listener_mode:
            cmd.append(target)

        return cmd

    def fetch(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        """Fetch URLs from all archive providers without loading into memory.

        Yields URLs in streaming fashion to prevent memory overflow.
        Returns list of deduplicated URLs (within memory cap).

        Args:
            target: Domain to query
            options: Execution options

        Yields:
            URL strings (one per line)
        """
        opts = options or {}
        command = self.build_command(target, opts)

        urls: list[str] = []
        seen: set[str] = set()

        try:
            import subprocess

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    url = str(data.get("url", "")).strip()

                    if not url or url in seen:
                        continue

                    seen.add(url)
                    urls.append(url)
                    self._stats.total_urls += 1

                    # Yield in chunks to prevent memory overflow
                    if len(urls) >= self.CHUNK_SIZE:
                        yield from urls
                        urls = []

                except (json.JSONDecodeError, ValueError):
                    continue

            # Yield remaining
            if urls:
                yield from urls

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"fetch() error: {e}")

    def export(self, urls: list[str], target: str) -> list[EndpointRegistry]:
        """Export URLs to EndpointRegistry models with deduplication.

        Processes large URL lists in chunks to maintain memory efficiency.

        Args:
            urls: List of URL strings
            target: Target domain

        Returns:
            List of EndpointRegistry models (deduplicated, classified)
        """
        registries: list[EndpointRegistry] = []
        self._dedup_cache.clear()

        for url in urls:
            if url in self._dedup_cache:
                self._stats.duplicates_removed += 1
                continue

            self._dedup_cache.add(url)

            # Skip low-value assets
            if self._is_low_value_url(url):
                self._stats.low_value_filtered += 1
                continue

            try:
                registry = self._build_endpoint_registry(url, target)
                registry.post_init_classify()
                registries.append(registry)

                # Update stats
                if registry.endpoint_type == EndpointType.API:
                    self._stats.api_endpoints += 1
                elif registry.endpoint_type == EndpointType.ADMIN:
                    self._stats.admin_endpoints += 1
                elif registry.endpoint_type == EndpointType.AUTH:
                    self._stats.auth_endpoints += 1
                elif registry.endpoint_type == EndpointType.STATIC:
                    self._stats.static_endpoints += 1

                if registry.is_high_value:
                    self._stats.high_value_count += 1

                # Push telemetry for high-value endpoints
                if registry.is_high_value:
                    self._push_telemetry("ENDPOINT_DISCOVERED", {
                        "url": registry.endpoint_url,
                        "type": registry.endpoint_type.value,
                        "source": registry.intel_origin.value,
                    })

            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to create registry for {url}: {e}")
                continue

        # Cap memory usage
        if len(self._dedup_cache) > self.MAX_MEMORY_URLS:
            self._dedup_cache.clear()

        self._stats.unique_urls = len(registries)
        return registries

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        """Parse gau JSON output into findings list.

        Each JSON line is a single URL discovery:
        {
          "url": "https://api.target.com/v1/users",
          "source": "wayback"
        }
        """
        findings: list[dict[str, Any]] = []
        registries: list[EndpointRegistry] = []
        seen_urls: set[str] = set()

        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            url = str(data.get("url", "")).strip()
            if not url:
                continue

            # Validate URL is for target domain
            if not self._is_url_in_scope(url, target):
                continue

            self._stats.total_urls += 1

            # Skip low-value assets
            if self._is_low_value_url(url):
                self._stats.low_value_filtered += 1
                continue

            # Skip duplicates within this parse run
            url_key = url.lower()
            if url_key in seen_urls:
                self._stats.duplicates_removed += 1
                continue
            seen_urls.add(url_key)

            # Build registry
            try:
                registry = self._build_endpoint_registry(url, target, data)
                registry.post_init_classify()
                registries.append(registry)

                # Update stats by type
                if registry.endpoint_type == EndpointType.API:
                    self._stats.api_endpoints += 1
                elif registry.endpoint_type == EndpointType.ADMIN:
                    self._stats.admin_endpoints += 1
                elif registry.endpoint_type == EndpointType.AUTH:
                    self._stats.auth_endpoints += 1
                elif registry.endpoint_type == EndpointType.STATIC:
                    self._stats.static_endpoints += 1

                # Update stats by source
                source = str(data.get("source", "")).lower()
                if source == "wayback":
                    self._stats.wayback_count += 1
                elif source == "commoncrawl":
                    self._stats.commoncrawl_count += 1
                elif source == "otx":
                    self._stats.otx_count += 1

                if registry.is_high_value:
                    self._stats.high_value_count += 1

            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to parse registry: {e}")
                continue

        # Convert to findings for K1 compatibility
        for registry in registries:
            finding = {
                "type": "endpoint",
                "endpoint": registry.endpoint_url,
                "value": registry.endpoint_url,
                "target": target,
                "severity": "high" if registry.is_high_value else "info",
                "confidence": 0.95,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": {
                    "url": registry.endpoint_url,
                    "source": registry.intel_origin.value,
                    "type": registry.endpoint_type.value,
                },
                "context": {
                    "registry_id": str(registry.endpoint_id),
                    "endpoint_type": registry.endpoint_type.value,
                    "intel_origin": registry.intel_origin.value,
                    "is_high_value": registry.is_high_value,
                    "discovery_date": registry.discovery_date.isoformat(),
                    "http_method": registry.http_method.value,
                },
                "recommended_next_tools": ["httpx"],
                "recommended_next_actions": ["probe_http"],
                "endpoint_registry": registry.model_dump(),
            }
            findings.append(finding)

        # Calculate unique URLs
        self._stats.unique_urls = len(registries)

        # Push telemetry
        self._push_telemetry("URL_DISCOVERY_COUNT", self._stats.unique_urls)
        self._push_telemetry("SOURCE_DISTRIBUTION", self._stats.source_distribution)
        self._push_telemetry("HIGH_VALUE_ENDPOINTS", self._stats.high_value_count)

        return findings

    def _build_endpoint_registry(
        self,
        url: str,
        target: str,
        gau_data: dict[str, Any] | None = None,
    ) -> EndpointRegistry:
        """Build EndpointRegistry from URL and metadata."""
        gau_data = gau_data or {}

        # Parse URL components
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        hostname = parsed.netloc.lower()
        path = parsed.path or ""
        query = parsed.query or None

        # Determine archive source
        source_str = str(gau_data.get("source", "")).lower()
        try:
            intel_origin = ArchiveSource(source_str)
        except ValueError:
            intel_origin = ArchiveSource.UNKNOWN

        # Parse discovery date if available
        discovery_date_str = str(gau_data.get("timestamp", "")).strip()
        if discovery_date_str:
            try:
                discovery_date = datetime.fromisoformat(discovery_date_str)
            except ValueError:
                discovery_date = datetime.now(UTC)
        else:
            discovery_date = datetime.now(UTC)

        # Detect HTTP method (if in metadata)
        http_method_str = str(gau_data.get("method", "GET")).upper()
        try:
            http_method = HttpMethod(http_method_str)
        except ValueError:
            http_method = HttpMethod.GET

        # Build registry
        registry = EndpointRegistry(
            target_domain=target,
            endpoint_url=url,
            scheme=scheme,
            hostname=hostname,
            path=path,
            query=query,
            intel_origin=intel_origin,
            discovery_date=discovery_date,
            http_method=http_method,
            http_status_code=gau_data.get("status_code"),
            response_size=gau_data.get("response_size"),
            content_type=gau_data.get("content_type"),
            raw_gau_output=json.dumps(gau_data, ensure_ascii=True) if gau_data else "",
        )

        return registry

    def _is_low_value_url(self, url: str) -> bool:
        """Check if URL is low-value (static asset)."""
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in _LOW_VALUE_EXTENSIONS)

    def _is_url_in_scope(self, url: str, target: str) -> bool:
        """Check if URL is in scope (matches target domain)."""
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc.lower()
            target_lower = target.lower()

            # Exact match or subdomain match
            return hostname == target_lower or hostname.endswith(f".{target_lower}")
        except Exception:
            return False

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Separate signal from noise.

        Signal criteria:
        - High-value endpoints (API, admin, auth, config)
        - Endpoints with fewer than 5 filters crossed
        - Non-duplicate URLs

        Noise criteria:
        - Static/low-value assets
        - Duplicate URLs
        - Suspicious/invalid endpoints
        """
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for item in findings:
            url = item.get("endpoint", item.get("value", "")).lower()
            target = item["target"].lower()
            dedupe_key = f"{target}|endpoint|{url}"

            # Check dedup cache
            if dedupe_key in known:
                noise.append(item)
                continue

            ctx = item["context"]

            # High-value endpoints → signal
            if ctx.get("is_high_value"):
                signal.append(item)
                continue

            # Static assets → noise
            if ctx.get("endpoint_type") == "static":
                item["noise_reason"] = "static_asset"
                noise.append(item)
                continue

            # Default: signal (archive endpoints have inherent value)
            signal.append(item)

        return signal, noise

    def _generate_next_agent_instructions(
        self, signal: list[dict[str, Any]], target: str
    ) -> dict[str, Any]:
        """Generate instructions for next agent (HTTP probing)."""
        endpoints = [s["endpoint"] for s in signal]
        high_value = [s for s in signal if s.get("context", {}).get("is_high_value")]

        return {
            "next_agent": "httpx",
            "action": "probe_historical_endpoints",
            "target": target,
            "input_endpoints": endpoints,
            "high_value_endpoints": [e["endpoint"] for e in high_value],
            "instructions": (
                f"HTTP probe {len(endpoints)} historical endpoints. "
                + (
                    f"PRIORITY: {len(high_value)} high-value endpoints (API/admin/auth): "
                    + ", ".join(e["endpoint"][:50] + "..." if len(e["endpoint"]) > 50 else e["endpoint"] for e in high_value[:3])
                    if high_value
                    else "All endpoints have equal priority."
                )
            ),
        }
