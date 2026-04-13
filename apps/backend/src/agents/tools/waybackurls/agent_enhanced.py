"""
Enhanced Wayback URLs Agent for K1 Platform

Responsible for historical URL discovery from Internet Archive Wayback Machine.

Features:
- High-velocity URL fetching from Wayback Machine snapshots
- Lifecycle management: fetch() streaming generator
- Single-provider focus: Wayback Machine optimized throughput
- Memory-efficient: Streaming JSON, dedup cache with resource limits
- Smart filtering: Excludes low-value assets (fonts, images, CSS)
- V-RAD integration: ARCHIVE_HITS, SENSITIVE_FILES_DETECTED metrics
- OPSEC layer: Sovereign Network Layer routing for archive requests
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
from ..gau.schemas import (
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

# Sensitive file patterns (potential exposure risk)
_SENSITIVE_PATTERNS = {
    ".env", ".config", ".git", ".aws", ".env.local",
    "config.php", "settings.ini", "web.config",
    "credentials", "secrets", "private_key", "id_rsa",
}


class WaybackurlsAgent(BaseToolAgent):
    """
    Wayback Machine URL Discovery Agent with lifecycle management and memory efficiency.

    Execution modes:
    1. Standard: waybackurls <domain> (direct domain query)
    2. Listener: stdin pipe (chained input)
    3. Versioned: waybackurls -get-versions <domain> (deeper historical analysis)

    Focused exclusively on Internet Archive Wayback Machine for high-velocity discovery.
    """

    TOOL_NAME = "waybackurls"
    DEFAULT_TIMEOUT_SECONDS = 300
    MAX_MEMORY_URLS = 100_000  # Cap for in-memory dedup cache
    CHUNK_SIZE = 5_000  # Export/fetch in chunks to prevent overflow

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._telemetry_hook: Callable | None = None
        self._listener_mode = False
        self._dedup_cache: set[str] = set()
        self._stats = GauArchiveStats()  # Reuse stats model
        self._streaming_mode = True  # Use streaming for large lists
        self._sensitive_files_found: list[str] = []

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
        """Build waybackurls command for historical URL discovery.

        Supports single-provider focus on Wayback Machine with optional versioning.
        """
        opts = options or {}
        self._listener_mode = bool(opts.get("listener_mode", False))

        binary = str(opts.get("binary_path", "waybackurls"))

        # Base command
        cmd = [binary]

        # Versioning flag (optional deeper historical analysis)
        if opts.get("get_versions", False):
            cmd.append("-get-versions")

        # Timeout (waybackurls respects standard timeouts)
        timeout_seconds = int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS))
        if timeout_seconds > 0:
            cmd += ["--timeout", str(timeout_seconds)]

        # Streaming mode for large datasets
        if opts.get("streaming", self._streaming_mode):
            # waybackurls streams by default, no flag needed
            pass

        # Input source (unless listener mode)
        if not self._listener_mode:
            cmd.append(target)

        return cmd

    def fetch(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        """Fetch URLs from Wayback Machine without loading into memory.

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

                url = str(line).strip()

                if not url or url in seen:
                    continue

                seen.add(url)
                urls.append(url)
                self._stats.total_urls += 1

                # Yield in chunks to prevent memory overflow
                if len(urls) >= self.CHUNK_SIZE:
                    yield from urls
                    urls = []

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
        self._sensitive_files_found.clear()

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

                # Track Wayback as source (single provider)
                self._stats.wayback_count += 1

                if registry.is_high_value:
                    self._stats.high_value_count += 1

                # Check for sensitive files
                if self._contains_sensitive_patterns(url):
                    self._sensitive_files_found.append(url)
                    self._push_telemetry("SENSITIVE_FILES_DETECTED", {
                        "url": url,
                        "pattern": self._detect_sensitive_pattern(url),
                    })

                # Push telemetry for high-value endpoints
                if registry.is_high_value:
                    self._push_telemetry("ENDPOINT_DISCOVERED", {
                        "url": registry.endpoint_url,
                        "type": registry.endpoint_type.value,
                        "source": "wayback",
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
        """Parse waybackurls output into findings list.

        Each line is a single URL discovery.
        """
        findings: list[dict[str, Any]] = []
        registries: list[EndpointRegistry] = []
        seen_urls: set[str] = set()

        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue

            url = str(line).strip()
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
                registry = self._build_endpoint_registry(url, target)
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

                # Wayback Machine is single provider
                self._stats.wayback_count += 1

                if registry.is_high_value:
                    self._stats.high_value_count += 1

                # Check for sensitive patterns
                if self._contains_sensitive_patterns(url):
                    self._sensitive_files_found.append(url)

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
                    "source": "wayback",
                    "type": registry.endpoint_type.value,
                },
                "context": {
                    "registry_id": str(registry.endpoint_id),
                    "endpoint_type": registry.endpoint_type.value,
                    "intel_origin": "wayback",
                    "is_high_value": registry.is_high_value,
                    "discovery_date": registry.discovery_date.isoformat(),
                    "http_method": registry.http_method.value,
                    "has_sensitive_patterns": self._contains_sensitive_patterns(registry.endpoint_url),
                },
                "recommended_next_tools": ["httpx"],
                "recommended_next_actions": ["probe_http"],
                "endpoint_registry": registry.model_dump(),
            }
            findings.append(finding)

        # Calculate unique URLs
        self._stats.unique_urls = len(registries)

        # Push telemetry
        self._push_telemetry("ARCHIVE_HITS", self._stats.unique_urls)
        self._push_telemetry("ARCHIVE_STATS", {
            "total_urls": self._stats.total_urls,
            "unique_urls": self._stats.unique_urls,
            "api_endpoints": self._stats.api_endpoints,
            "admin_endpoints": self._stats.admin_endpoints,
            "auth_endpoints": self._stats.auth_endpoints,
            "high_value_count": self._stats.high_value_count,
            "sensitive_files_found": len(self._sensitive_files_found),
        })

        if self._sensitive_files_found:
            self._push_telemetry("SENSITIVE_FILES_DETECTED", {
                "count": len(self._sensitive_files_found),
                "samples": self._sensitive_files_found[:5],
            })

        return findings

    def _build_endpoint_registry(
        self,
        url: str,
        target: str,
    ) -> EndpointRegistry:
        """Build EndpointRegistry from URL and metadata."""
        # Parse URL components
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        hostname = parsed.netloc.lower()
        path = parsed.path or ""
        query = parsed.query or None

        # Wayback Machine is single source
        intel_origin = ArchiveSource.WAYBACK

        # Build registry
        registry = EndpointRegistry(
            target_domain=target,
            endpoint_url=url,
            scheme=scheme,
            hostname=hostname,
            path=path,
            query=query,
            intel_origin=intel_origin,
            discovery_date=datetime.now(UTC),
            http_method=HttpMethod.GET,
            raw_gau_output=json.dumps({"url": url, "source": "wayback"}, ensure_ascii=True),
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

    def _contains_sensitive_patterns(self, url: str) -> bool:
        """Check if URL contains sensitive file patterns."""
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in _SENSITIVE_PATTERNS)

    def _detect_sensitive_pattern(self, url: str) -> str | None:
        """Detect which sensitive pattern matches."""
        url_lower = url.lower()
        for pattern in _SENSITIVE_PATTERNS:
            if pattern in url_lower:
                return pattern
        return None

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Separate signal from noise.

        Signal criteria:
        - High-value endpoints (API, admin, auth, config)
        - Sensitive file patterns detected
        - Non-duplicate URLs

        Noise criteria:
        - Static/low-value assets
        - Duplicate URLs
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

            # Sensitive files → signal
            if ctx.get("has_sensitive_patterns"):
                signal.append(item)
                continue

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
        sensitive = [s for s in signal if s.get("context", {}).get("has_sensitive_patterns")]

        return {
            "next_agent": "httpx",
            "action": "probe_wayback_endpoints",
            "target": target,
            "input_endpoints": endpoints,
            "high_value_endpoints": [e["endpoint"] for e in high_value],
            "sensitive_file_endpoints": [e["endpoint"] for e in sensitive],
            "instructions": (
                f"HTTP probe {len(endpoints)} Wayback Machine endpoints. "
                + (
                    f"PRIORITY: {len(sensitive)} sensitive files (potential exposure): "
                    + ", ".join(e["endpoint"][:50] + "..." if len(e["endpoint"]) > 50 else e["endpoint"] for e in sensitive[:3])
                    if sensitive
                    else (
                        f"PRIORITY: {len(high_value)} high-value endpoints (API/admin/auth): "
                        + ", ".join(e["endpoint"][:50] + "..." if len(e["endpoint"]) > 50 else e["endpoint"] for e in high_value[:3])
                        if high_value
                        else "All endpoints have equal priority."
                    )
                )
            ),
        }
