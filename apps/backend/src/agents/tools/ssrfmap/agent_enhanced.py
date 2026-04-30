"""
SSRFMAP Agent for K1 — SSRF Vulnerability Discovery and Internal Infrastructure Mapping

Orchestrates ssrfmap binary to discover Server-Side Request Forgery (SSRF) vulnerabilities
and map internal infrastructure (IPs, services, cloud metadata, credentials).

Implements:
  - Modular SSRF testing (network, AWS, Azure, GCP, cloud metadata)
  - Internal asset discovery (IPs, hostnames, services)
  - Cloud metadata exposure detection (IAM roles, credentials)
  - Recursive NaabuAgent port scanning trigger on discovered IPs
  - OPSEC sanitization (no K1-identifiable markers)
  - V-RAD telemetry (INTERNAL_HOSTS_DISCOVERED, CLOUD_METADATA_EXPOSED)
  - Non-blocking evidence dispatch to HiL queue on findings
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from ..base_tool_agent import BaseToolAgent

from .schemas import (
    CloudProvider,
    ExploitStatus,
    InternalAccessRegistry,
    InternalAsset,
    InternalAssetType,
    ServiceInfo,
    SsrfModule,
    SsrfStatistics,
)

logger = logging.getLogger(__name__)


class SsrfmapAgent(BaseToolAgent):
    """
    SSRFMAP Agent for SSRF vulnerability discovery and internal infrastructure mapping.

    Discovers Server-Side Request Forgery vulnerabilities across multiple modules:
    - Network-level SSRF (local IP enumeration)
    - Cloud provider metadata exposure (AWS, Azure, GCP, Alibaba)
    - Database and service enumeration (MySQL, PostgreSQL, MongoDB, Redis, Memcached, Elasticsearch)
    - Docker daemon access and compromise vectors

    Key Features:
      - Multi-module targeting (12+ module types)
      - Internal asset discovery (IPs, hostnames, services)
      - Cloud metadata exposure detection
      - Credential harvesting and IAM role detection
      - OPSEC: No K1-identifiable markers in payloads
      - V-RAD telemetry: Real-time metrics on internal discovery
      - Recursive NaabuAgent integration for port scanning discovered IPs
    """

    TOOL_NAME = "ssrfmap"

    # Cloud metadata endpoints targeted by SSRF probes
    CLOUD_METADATA_TARGETS = [
        "169.254.169.254",
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/latest/user-data",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://169.254.169.254/metadata/instance",
    ]

    # SSRF module priorities
    _MODULES = [
        SsrfModule.NETWORK,
        SsrfModule.AWS,
        SsrfModule.AZURE,
        SsrfModule.GCP,
        SsrfModule.ALIBABA,
        SsrfModule.DOCKER,
        SsrfModule.REDIS,
        SsrfModule.MEMCACHED,
        SsrfModule.ELASTICSEARCH,
        SsrfModule.MONGODB,
        SsrfModule.MYSQL,
        SsrfModule.POSTGRESQL,
    ]

    # Cloud provider patterns for metadata detection
    _AWS_METADATA_PATTERNS = [
        r"(aws|assume|accesskey)",
        r"AssumeRole",
        r"AKIA[0-9A-Z]{6,}",
        r'"InstanceMetadata"',
        r"X-aws-ec2-metadata-token",
        r"169\.254\.169\.254",
        r"security-credentials",
        r"ec2-instance-role",
    ]

    _AZURE_PATTERNS = [
        r"azure",
        r"subscription[_-]?id",
        r"tenant[_-]?id",
        r"ManagedIdentity",
        r"169\.254\.169\.254",
    ]

    _GCP_PATTERNS = [
        r"service[_-]?account",
        r"google\.oauth2",
        r"compute\.googleapis",
        r"metadata\.google",
        r"http://metadata\.google",
    ]

    # Internal IP patterns
    _INTERNAL_IP_PATTERNS = [
        r"^10\.\d+\.\d+\.\d+$",
        r"^172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+$",
        r"^192\.168\.\d+\.\d+$",
        r"^127\.\d+\.\d+\.\d+$",
        r"^localhost$",
    ]

    # Service port mappings
    _SERVICE_PORTS = {
        3306: ("mysql", "MySQL Database"),
        5432: ("postgresql", "PostgreSQL Database"),
        27017: ("mongodb", "MongoDB"),
        6379: ("redis", "Redis Cache"),
        11211: ("memcached", "Memcached"),
        9200: ("elasticsearch", "Elasticsearch"),
        2375: ("docker", "Docker Daemon"),
        2376: ("docker", "Docker Daemon (TLS)"),
    }

    def build_command(
        self,
        target_url: str,
        options: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Build ssrfmap command.

        Args:
            target_url: Target URL with SSRF parameter
            options: Execution options
              - modules: List of SsrfModule values to test (default: all)
              - timeout_seconds: Command timeout (default: 600)
              - proxy: HTTP(S) proxy URL (SNL routing)
              - follow_redirects: Follow HTTP redirects (default: True)
              - threads: Number of concurrent threads (default: 10)

        Returns:
            Command as list of strings for subprocess execution
        """
        options = options or {}
        cmd = [self.TOOL_NAME, "-u", target_url, "read", "-l", target_url]

        # Module selection — default to cloud provider modules
        modules = options.get("modules")
        if modules:
            module_list = ",".join([m.value if hasattr(m, "value") else str(m) for m in modules])
        else:
            module_list = "aws,gcp,azure"
        cmd.extend(["-m", module_list])

        # Timeout
        timeout = options.get("timeout_seconds", 600)
        if timeout:
            cmd.extend(["-t", str(timeout)])

        # Proxy (SNL routing)
        proxy = options.get("proxy")
        if proxy:
            cmd.extend(["-p", proxy])

        # Follow redirects
        if not options.get("follow_redirects", True):
            cmd.append("-r")

        # Threads
        threads = options.get("threads", 10)
        if threads:
            cmd.extend(["-th", str(threads)])

        # OPSEC: No user-agent randomization needed for SSRF (server-side)
        # Output format
        cmd.extend(["-o", "json"])

        return cmd

    def parse_output(self, raw_output: str, target: str = "") -> dict[str, Any]:
        """
        Parse ssrfmap JSON output and normalize to InternalAccessRegistry.

        Args:
            raw_output: Raw ssrfmap command output
            target: Target URL (optional, for context)

        Returns:
            Dictionary with keys:
              - findings: List[InternalAccessRegistry] — discovered SSRF vulnerabilities
              - statistics: SsrfStatistics — aggregated metrics
              - internal_hosts: List[str] — unique internal IPs/hostnames for recursive scanning
        """
        findings = []
        statistics = SsrfStatistics()
        internal_hosts = set()

        if not raw_output.strip():
            return {
                "findings": findings,
                "statistics": statistics,
                "internal_hosts": list(internal_hosts),
            }

        # Parse each line as JSON (streaming format)
        for line in raw_output.split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                finding = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse ssrfmap JSON line: {line[:100]}")
                continue

            # Skip non-SSRF findings
            if not self._is_ssrf_finding(finding):
                continue

            # Build InternalAccessRegistry
            try:
                registry = self._build_registry(finding)
                findings.append(registry)
                statistics.total_urls_tested += 1
                statistics.ssrf_vulnerabilities_found += 1

                # Track by exploit status
                if registry.exploit_status == ExploitStatus.CONFIRMED:
                    statistics.confirmed_count += 1
                elif registry.exploit_status == ExploitStatus.PROBABLE:
                    statistics.probable_count += 1
                elif registry.exploit_status == ExploitStatus.BLIND:
                    statistics.blind_count += 1

                # Track cloud exposures
                if registry.cloud_provider == CloudProvider.AWS:
                    statistics.aws_exposures += 1
                elif registry.cloud_provider == CloudProvider.AZURE:
                    statistics.azure_exposures += 1
                elif registry.cloud_provider == CloudProvider.GCP:
                    statistics.gcp_exposures += 1

                # Track credential leaks
                statistics.credentials_leaked += len(registry.credentials_leaked)

                # Collect internal hosts
                for asset in registry.internal_assets:
                    statistics.internal_ips_discovered += 1
                    if asset.asset_type == InternalAssetType.IP_ADDRESS:
                        internal_hosts.add(asset.value)

                # Collect services
                statistics.internal_services_discovered += len(
                    registry.services_discovered
                )

            except ValidationError as e:
                logger.warning(f"Failed to build registry for finding: {e}")
                continue

        return {
            "findings": findings,
            "statistics": statistics,
            "internal_hosts": list(internal_hosts),
        }

    def _is_ssrf_finding(self, finding: dict[str, Any]) -> bool:
        """Check if finding represents an SSRF vulnerability."""
        return (
            finding.get("vulnerability_type") == "ssrf"
            or finding.get("type") == "ssrf"
        )

    def _build_registry(self, finding: dict[str, Any]) -> InternalAccessRegistry:
        """Build InternalAccessRegistry from ssrfmap finding."""
        target_url = finding.get("url", finding.get("target", ""))
        vulnerable_parameter = finding.get("parameter", "")
        exploit_path = finding.get("payload", finding.get("path", ""))
        response = finding.get("response", "")

        # Determine exploit status
        exploit_status = self._determine_exploit_status(finding, response)

        # Detect cloud provider
        cloud_provider = self._detect_cloud_provider(response)

        # Detect metadata exposure
        metadata_exposed = self._detect_metadata_exposure(
            response, cloud_provider
        )

        # Detect IAM role leakage
        iam_role_leaked = self._detect_iam_role_leak(response, cloud_provider)

        # Extract credentials
        credentials_leaked = self._extract_credentials(response)

        # Discover internal assets
        internal_assets = self._discover_internal_assets(
            response, finding
        )

        # Discover services
        services_discovered = self._discover_services(
            internal_assets, finding
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            exploit_status, response, len(internal_assets)
        )

        # Determine module used
        module_used = self._determine_module_used(finding)

        # Detect WAF/filter bypass
        bypass_technique = finding.get("bypass", "")

        return InternalAccessRegistry(
            target_url=target_url,
            vulnerable_parameter=vulnerable_parameter,
            ssrf_confirmed=exploit_status in (
                ExploitStatus.CONFIRMED,
                ExploitStatus.PROBABLE,
            ),
            exploit_status=exploit_status,
            confidence=confidence,
            exploit_path=exploit_path,
            module_used=module_used,
            response_time_ms=finding.get("response_time", 0),
            internal_assets=internal_assets,
            internal_hosts_count=len(
                {a.value for a in internal_assets
                 if a.asset_type == InternalAssetType.IP_ADDRESS}
            ),
            cloud_provider=cloud_provider,
            metadata_exposed=metadata_exposed,
            iam_role_leaked=iam_role_leaked,
            credentials_leaked=credentials_leaked,
            services_discovered=services_discovered,
            port_scan_recommended=len(internal_assets) > 0,
            detected_by="ssrfmap",
            detection_date=datetime.now(UTC),
            raw_response=response[:5000],
            raw_ssrfmap_output=json.dumps(finding),
            request_payload=exploit_path,
            request_headers=finding.get("headers", {}),
            stealthy=True,
            bypass_technique=bypass_technique,
        )

    def _determine_exploit_status(
        self,
        finding: dict[str, Any],
        response: str,
    ) -> ExploitStatus:
        """Determine exploit confirmation status."""
        status_str = finding.get("status", "").lower()

        if status_str == "confirmed" or (response and len(response) > 100):
            return ExploitStatus.CONFIRMED
        elif status_str == "probable" or "likely" in status_str:
            return ExploitStatus.PROBABLE
        elif "blind" in status_str or "time_based" in status_str:
            if "time" in status_str:
                return ExploitStatus.TIME_BASED
            return ExploitStatus.BLIND
        elif "reflected" in status_str or "output" in status_str:
            return ExploitStatus.REFLECTED

        return ExploitStatus.UNKNOWN

    def _detect_cloud_provider(self, response: str) -> CloudProvider:
        """Detect cloud provider from response."""
        response_lower = response.lower()

        # Check GCP first (more specific patterns)
        for pattern in self._GCP_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                return CloudProvider.GCP

        # Then check AWS
        for pattern in self._AWS_METADATA_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                return CloudProvider.AWS

        # Then Azure
        for pattern in self._AZURE_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                return CloudProvider.AZURE

        if "alibaba" in response_lower:
            return CloudProvider.ALIBABA

        return CloudProvider.UNKNOWN

    def _detect_metadata_exposure(
        self,
        response: str,
        cloud_provider: CloudProvider,
    ) -> bool:
        """Detect cloud metadata exposure."""
        response_lower = response.lower()

        if cloud_provider == CloudProvider.AWS:
            aws_metadata = ["iam", "role", "credential", "instance"]
            return any(m in response_lower for m in aws_metadata)

        elif cloud_provider == CloudProvider.AZURE:
            azure_metadata = [
                "subscription",
                "tenant",
                "managed",
                "identity",
            ]
            return any(m in response_lower for m in azure_metadata)

        elif cloud_provider == CloudProvider.GCP:
            gcp_metadata = [
                "service_account",
                "compute",
                "googleapis",
                "metadata",
            ]
            return any(m in response_lower for m in gcp_metadata)

        return False

    def _detect_iam_role_leak(
        self,
        response: str,
        cloud_provider: CloudProvider,
    ) -> bool:
        """Detect IAM role credential leakage."""
        response_lower = response.lower()

        if cloud_provider == CloudProvider.AWS:
            return (
                "akia" in response
                or "assume" in response_lower
                or "accesskey" in response_lower
            )

        elif cloud_provider == CloudProvider.AZURE:
            return (
                "tenant_id" in response_lower
                or "subscription_id" in response_lower
            )

        elif cloud_provider == CloudProvider.GCP:
            return "service_account" in response_lower

        return False

    def _extract_credentials(self, response: str) -> list[str]:
        """Extract credential types found in response."""
        credentials = []

        if re.search(r"AKIA[0-9A-Z]{6,}", response):
            credentials.append("aws_access_key")
        if re.search(r"aws_secret_access_key", response, re.IGNORECASE):
            credentials.append("aws_secret_key")
        if re.search(r"password|passwd", response, re.IGNORECASE):
            credentials.append("password")
        if re.search(r"token|jwt|bearer", response, re.IGNORECASE):
            credentials.append("token")
        if re.search(r"api[_-]?key", response, re.IGNORECASE):
            credentials.append("api_key")
        if re.search(r"connection[_-]?string", response, re.IGNORECASE):
            credentials.append("connection_string")
        if re.search(r"private[_-]?key", response, re.IGNORECASE):
            credentials.append("private_key")

        return list(set(credentials))

    def _discover_internal_assets(
        self,
        response: str,
        finding: dict[str, Any],
    ) -> list[InternalAsset]:
        """Discover internal assets from response."""
        assets = []
        seen = set()

        # Extract IPs
        ip_pattern = r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}" \
                     r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        for ip in re.findall(ip_pattern, response):
            if ip not in seen and self._is_internal_ip(ip):
                assets.append(
                    InternalAsset(
                        asset_type=InternalAssetType.IP_ADDRESS,
                        value=ip,
                        confidence=0.95,
                        sensitive=self._is_sensitive_service(ip),
                    )
                )
                seen.add(ip)

        # Extract hostnames
        hostname_pattern = r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)" \
                          r"+(?:[a-zA-Z]{2,})"
        for hostname in re.findall(hostname_pattern, response):
            if hostname not in seen and not hostname.endswith(
                (".com", ".org", ".net")
            ):
                assets.append(
                    InternalAsset(
                        asset_type=InternalAssetType.HOSTNAME,
                        value=hostname,
                        confidence=0.85,
                    )
                )
                seen.add(hostname)

        # Extract services from finding
        services = finding.get("services", [])
        for service in services:
            if isinstance(service, dict) and service.get("name") not in seen:
                assets.append(
                    InternalAsset(
                        asset_type=InternalAssetType.SERVICE,
                        value=service.get("name", "unknown"),
                        service_name=service.get("name"),
                        port=service.get("port"),
                        confidence=0.80,
                        sensitive=True,
                    )
                )
                seen.add(service.get("name"))

        return assets

    def _discover_services(
        self,
        internal_assets: list[InternalAsset],
        finding: dict[str, Any],
    ) -> list[ServiceInfo]:
        """Discover service details from internal assets and finding services list."""
        services = []
        seen = set()

        # Process explicit services from finding
        for service in finding.get("services", []):
            if isinstance(service, dict):
                service_name = service.get("name", "unknown")
                port = service.get("port", 0)
                host = service.get("host", "")

                # Try to find the host from internal_assets
                if not host:
                    for asset in internal_assets:
                        if asset.asset_type == InternalAssetType.IP_ADDRESS:
                            host = asset.value
                            break

                key = f"{host}:{port}:{service_name}"
                if key not in seen and port > 0:
                    services.append(
                        ServiceInfo(
                            service_name=service_name,
                            host=host or "unknown",
                            port=port,
                            protocol="TCP",
                        )
                    )
                    seen.add(key)

        # Also process ports from internal assets
        for asset in internal_assets:
            if asset.asset_type == InternalAssetType.IP_ADDRESS and asset.port:
                service_name, service_desc = self._SERVICE_PORTS.get(
                    asset.port,
                    ("unknown", f"Service on port {asset.port}"),
                )
                key = f"{asset.value}:{asset.port}:{service_name}"
                if key not in seen:
                    services.append(
                        ServiceInfo(
                            service_name=service_name,
                            host=asset.value,
                            port=asset.port,
                            protocol="TCP",
                        )
                    )
                    seen.add(key)

        return services

    def _is_internal_ip(self, ip: str) -> bool:
        """Check if IP is internal/private."""
        for pattern in self._INTERNAL_IP_PATTERNS:
            if re.match(pattern, ip):
                return True
        return False

    def _is_sensitive_service(self, ip: str) -> bool:
        """Check if IP likely runs sensitive service."""
        return ip.startswith(("10.", "172.", "192.")) or ip.startswith(
            "127."
        )

    def _calculate_confidence(
        self,
        exploit_status: ExploitStatus,
        response: str,
        asset_count: int,
    ) -> float:
        """Calculate confidence score."""
        confidence = 0.5

        if exploit_status == ExploitStatus.CONFIRMED:
            confidence = 0.95
        elif exploit_status == ExploitStatus.PROBABLE:
            confidence = 0.80
        elif exploit_status == ExploitStatus.REFLECTED:
            confidence = 0.75
        elif exploit_status == ExploitStatus.BLIND:
            confidence = 0.65
        elif exploit_status == ExploitStatus.TIME_BASED:
            confidence = 0.70

        # Boost confidence if assets discovered
        if asset_count > 0:
            confidence = min(1.0, confidence + 0.10)

        # Boost confidence if response is substantial
        if len(response) > 500:
            confidence = min(1.0, confidence + 0.05)

        return confidence

    def _determine_module_used(
        self,
        finding: dict[str, Any],
    ) -> SsrfModule:
        """Determine which SSRFMAP module was used."""
        module_str = finding.get("module", "").lower()

        if "network" in module_str:
            return SsrfModule.NETWORK
        elif "aws" in module_str:
            return SsrfModule.AWS
        elif "azure" in module_str:
            return SsrfModule.AZURE
        elif "gcp" in module_str:
            return SsrfModule.GCP
        elif "alibaba" in module_str:
            return SsrfModule.ALIBABA
        elif "docker" in module_str:
            return SsrfModule.DOCKER
        elif "redis" in module_str:
            return SsrfModule.REDIS
        elif "memcached" in module_str:
            return SsrfModule.MEMCACHED
        elif "elasticsearch" in module_str:
            return SsrfModule.ELASTICSEARCH
        elif "mongodb" in module_str:
            return SsrfModule.MONGODB
        elif "mysql" in module_str:
            return SsrfModule.MYSQL
        elif "postgresql" in module_str:
            return SsrfModule.POSTGRESQL

        return SsrfModule.UNKNOWN

    def filter_noise(self, findings: "dict[str, Any] | list") -> tuple[list, list]:
        """
        Separate signal from noise.

        Signal (high-confidence findings):
          - CONFIRMED SSRF with metadata/credentials exposed
          - High confidence (>0.8) with internal asset discovery

        Noise (low-value findings):
          - BLIND SSRF with low confidence (<0.6)
          - Unknown status with <0.5 confidence
          - No internal assets discovered

        Returns:
            Tuple of (signal_findings, noise_findings)
        """
        signal = []
        noise = []

        raw = findings if isinstance(findings, list) else findings.get("findings", [])
        for finding in raw:
            is_signal = (
                finding.ssrf_confirmed
                and (
                    finding.metadata_exposed
                    or finding.iam_role_leaked
                    or len(finding.credentials_leaked) > 0
                )
            ) or (
                finding.confidence > 0.8
                and finding.internal_hosts_count > 0
            )

            if is_signal:
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def register_telemetry_hook(self, callback: callable) -> None:
        """Register V-RAD telemetry callback."""
        self._telemetry_callback = callback

    async def _push_telemetry(self, metric_name: str, value: Any) -> None:
        """Push telemetry to V-RAD."""
        if hasattr(self, "_telemetry_callback"):
            try:
                await self._telemetry_callback(metric_name, value)
            except Exception as e:
                logger.warning(f"Failed to push telemetry {metric_name}: {e}")
