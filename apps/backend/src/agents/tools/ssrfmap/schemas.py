"""
Internal Access Registry Schemas for SSRFMAP Agent
Models for tracking SSRF vulnerabilities and internal infrastructure discovery.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SsrfModule(str, Enum):
    """SSRFMAP module types for different environments."""
    NETWORK = "network"           # Internal network discovery
    AWS = "aws"                   # AWS metadata exposure
    AZURE = "azure"               # Azure metadata exposure
    GCP = "gcp"                   # GCP metadata exposure
    ALIBABA = "alibaba"           # Alibaba Cloud metadata
    DOCKER = "docker"             # Docker daemon access
    REDIS = "redis"               # Redis server exposure
    MEMCACHED = "memcached"       # Memcached server exposure
    ELASTICSEARCH = "elasticsearch"  # Elasticsearch cluster
    MONGODB = "mongodb"           # MongoDB database
    MYSQL = "mysql"               # MySQL database
    POSTGRESQL = "postgresql"     # PostgreSQL database
    UNKNOWN = "unknown"


class ExploitStatus(str, Enum):
    """SSRF exploitation status."""
    CONFIRMED = "confirmed"       # SSRF confirmed and exploited
    PROBABLE = "probable"         # Likely SSRF, but unconfirmed
    BLIND = "blind"               # Blind SSRF (no direct output)
    REFLECTED = "reflected"       # Output reflected in response
    TIME_BASED = "time_based"     # Detected via timing differences
    UNKNOWN = "unknown"


class InternalAssetType(str, Enum):
    """Type of internal asset discovered."""
    IP_ADDRESS = "ip"
    HOSTNAME = "hostname"
    SERVICE = "service"
    CLOUD_METADATA = "metadata"
    CREDENTIAL = "credential"
    API_ENDPOINT = "api"
    DATABASE = "database"
    CACHE_SERVICE = "cache"
    UNKNOWN = "unknown"


class CloudProvider(str, Enum):
    """Cloud provider identification."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ALIBABA = "alibaba"
    DIGITAL_OCEAN = "digitalocean"
    LINODE = "linode"
    ON_PREMISE = "on_premise"
    UNKNOWN = "unknown"


class InternalAccessRegistry(BaseModel):
    """Registry of SSRF vulnerabilities and internal infrastructure discovered."""

    model_config = ConfigDict(extra="forbid", strict=True)

    access_id: UUID = Field(default_factory=uuid4, description="Unique access record identifier")
    target_url: str = Field(min_length=10, max_length=2048, description="Target URL with SSRF parameter")
    vulnerable_parameter: str = Field(description="Parameter allowing SSRF")

    # SSRF identification
    ssrf_confirmed: bool = Field(description="SSRF vulnerability confirmed")
    exploit_status: ExploitStatus = Field(description="Exploitation status")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence (0.0-1.0)")

    # Exploitation details
    exploit_path: str = Field(description="Payload/path used for exploitation")
    module_used: SsrfModule = Field(description="SSRFMAP module employed")
    response_time_ms: int = Field(ge=0, default=0, description="Response time in ms")

    # Internal infrastructure discovered
    internal_assets: list[InternalAsset] = Field(default_factory=list, description="Discovered internal assets")
    internal_hosts_count: int = Field(ge=0, default=0, description="Count of internal IPs/hostnames")

    # Cloud metadata exposure
    cloud_provider: CloudProvider = Field(description="Detected cloud provider")
    metadata_exposed: bool = Field(default=False, description="Cloud metadata leaked")
    iam_role_leaked: bool = Field(default=False, description="IAM role credentials exposed")
    credentials_leaked: list[str] = Field(default_factory=list, description="Leaked credential types")

    # Service enumeration
    services_discovered: list[ServiceInfo] = Field(default_factory=list, description="Internal services found")
    port_scan_recommended: bool = Field(default=False, description="Internal port scan recommended")

    # Detection context
    detected_by: str = Field(default="ssrfmap", description="Detection tool")
    detection_date: datetime = Field(description="Discovery timestamp")
    last_verified: datetime | None = Field(default=None, description="Last verification")

    # Raw evidence
    raw_response: str = Field(default="", max_length=5000, description="Response from SSRF")
    raw_ssrfmap_output: str = Field(default="", description="Raw ssrfmap JSON output")
    request_payload: str = Field(default="", description="SSRF payload sent")
    request_headers: dict[str, str] = Field(default_factory=dict, description="Request headers")

    # OPSEC
    stealthy: bool = Field(default=True, description="OPSEC measures applied")
    bypass_technique: str = Field(default="", description="WAF/filter bypass used")
    notes: str = Field(default="", description="Additional findings")

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Validate URL format."""
        normalized = value.strip()
        if not (normalized.startswith("http://") or normalized.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return normalized

    @property
    def is_critical(self) -> bool:
        """Check if finding is critical."""
        return (
            self.ssrf_confirmed and
            self.confidence > 0.85 and
            (self.iam_role_leaked or self.metadata_exposed)
        )

    @property
    def exploitation_difficulty(self) -> str:
        """Estimate exploitation difficulty."""
        if self.exploit_status == ExploitStatus.CONFIRMED:
            return "low"
        elif self.exploit_status == ExploitStatus.PROBABLE:
            return "medium"
        elif self.exploit_status in (ExploitStatus.BLIND, ExploitStatus.TIME_BASED):
            return "high"
        return "unknown"


class InternalAsset(BaseModel):
    """Internal asset discovered via SSRF."""

    model_config = ConfigDict(extra="forbid", strict=True)

    asset_id: UUID = Field(default_factory=uuid4, description="Asset identifier")
    asset_type: InternalAssetType = Field(description="Type of asset")
    value: str = Field(description="IP, hostname, service name, etc.")
    port: int | None = Field(default=None, ge=1, le=65535, description="Port (if applicable)")
    service_name: str = Field(default="", description="Service running (if identified)")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="Discovery confidence")
    sensitive: bool = Field(default=False, description="Sensitive service/data")


class ServiceInfo(BaseModel):
    """Information about internal service discovered."""

    model_config = ConfigDict(extra="forbid", strict=True)

    service_id: UUID = Field(default_factory=uuid4, description="Service identifier")
    service_name: str = Field(description="Service name (Redis, MySQL, etc.)")
    host: str = Field(description="Host/IP of service")
    port: int = Field(ge=1, le=65535, description="Service port")
    protocol: str = Field(description="Protocol (TCP, UDP)")
    version: str = Field(default="", description="Service version (if detected)")
    exposed_data: str = Field(default="", description="Data/config exposed")


class SsrfStatistics(BaseModel):
    """Statistics from SSRF scanning run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    total_urls_tested: int = 0
    ssrf_vulnerabilities_found: int = 0

    confirmed_count: int = 0
    probable_count: int = 0
    blind_count: int = 0

    aws_exposures: int = 0
    azure_exposures: int = 0
    gcp_exposures: int = 0

    internal_ips_discovered: int = 0
    internal_services_discovered: int = 0
    credentials_leaked: int = 0

    @property
    def confirmation_ratio(self) -> float:
        """Percentage of confirmed SSRF findings."""
        if self.ssrf_vulnerabilities_found == 0:
            return 0.0
        return self.confirmed_count / self.ssrf_vulnerabilities_found * 100

    @property
    def critical_exposure_count(self) -> int:
        """Count of critical exposures (credentials/metadata)."""
        return self.aws_exposures + self.azure_exposures + self.gcp_exposures + self.credentials_leaked
