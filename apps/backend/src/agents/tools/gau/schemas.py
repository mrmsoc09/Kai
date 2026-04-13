"""
Endpoint Registry Schemas for GAU (GetAllUrls) Agent
Normalizes gau JSON output into canonical EndpointRegistry models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArchiveSource(str, Enum):
    """Archive data sources supported by gau."""
    WAYBACK = "wayback"          # Internet Archive Wayback Machine
    COMMONCRAWL = "commoncrawl"  # Common Crawl dataset
    OTX = "otx"                  # AlienVault Open Threat Exchange
    URLSCAN = "urlscan"          # URLScan.io
    UNKNOWN = "unknown"


class EndpointType(str, Enum):
    """Endpoint classification for filtering/prioritization."""
    API = "api"                  # /api/*, /v1/*, /graphql, /rest
    ADMIN = "admin"              # /admin*, /management, /dashboard
    CONFIG = "config"            # /config, /settings, /.well-known
    AUTH = "auth"                # /login, /auth, /sso, /oauth
    STATIC = "static"            # CSS, JavaScript, images (low-value)
    UPLOAD = "upload"            # /upload, /file, /media (takeover risk)
    SUBDOMAIN = "subdomain"      # Entire subdomain path
    UNKNOWN = "unknown"           # Unclassified


class HttpMethod(str, Enum):
    """HTTP methods observed in historical records."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    UNKNOWN = "UNKNOWN"


class EndpointRegistry(BaseModel):
    """Canonical endpoint record from historical URL discovery."""

    model_config = ConfigDict(extra="forbid", strict=True)

    endpoint_id: UUID = Field(default_factory=uuid4, description="Unique endpoint identifier")
    target_domain: str = Field(description="Parent domain target")
    endpoint_url: str = Field(min_length=10, max_length=2048, description="Full URL")

    # URL components
    scheme: str = Field(default="https", description="http or https")
    hostname: str = Field(description="Hostname/subdomain")
    path: str = Field(default="", description="URL path component")
    query: str | None = Field(default=None, description="Query string (if present)")

    # Classification
    endpoint_type: EndpointType = Field(default=EndpointType.UNKNOWN, description="Endpoint classification")
    http_method: HttpMethod = Field(default=HttpMethod.GET, description="Observed HTTP method")
    is_high_value: bool = Field(default=False, description="High-value endpoint (API, admin, config)")

    # Archive sources
    intel_origin: ArchiveSource = Field(description="Archive source (wayback, commoncrawl, otx)")
    source_details: dict[str, Any] = Field(default_factory=dict, description="Provider-specific metadata")

    # Discovery metadata
    discovery_date: datetime = Field(description="When endpoint was first discovered")
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last observation")
    discovery_count: int = Field(default=1, ge=1, description="Times endpoint observed across archives")

    # Response metadata (if captured)
    http_status_code: int | None = Field(default=None, ge=0, le=599, description="HTTP status from archive")
    response_size: int | None = Field(default=None, ge=0, description="Response size in bytes")
    content_type: str | None = Field(default=None, description="Content-Type header (if captured)")

    # Historical tracking
    first_seen_wayback: datetime | None = Field(default=None, description="First Wayback snapshot")
    first_seen_commoncrawl: datetime | None = Field(default=None, description="First CommonCrawl record")
    first_seen_otx: datetime | None = Field(default=None, description="First OTX record")

    # Security indicators
    contains_credentials: bool = Field(default=False, description="URL contains potential credentials")
    contains_api_key: bool = Field(default=False, description="URL contains API key patterns")
    contains_token: bool = Field(default=False, description="URL contains token patterns")

    # Normalization flags
    is_duplicate: bool = Field(default=False, description="Marked if deduplicated")
    is_alive: bool | None = Field(default=None, description="Last HTTP probe status (if probed)")

    # Raw evidence
    raw_gau_output: str = Field(default="", description="Raw gau output for audit")
    discovery_notes: str = Field(default="", description="Discovery context/notes")

    @field_validator("endpoint_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Validate and normalize URL."""
        normalized = value.strip()
        if not (normalized.startswith("http://") or normalized.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return normalized

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        """Normalize hostname to lowercase."""
        return value.strip().lower()

    @property
    def is_low_value(self) -> bool:
        """Check if endpoint is low-value (static assets, images, fonts)."""
        low_value_patterns = {
            ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
            ".woff", ".woff2", ".ttf", ".otf", ".eot", ".ico",
            ".zip", ".tar", ".gz", ".7z", ".rar",
        }
        path_lower = self.path.lower()
        return any(path_lower.endswith(ext) for ext in low_value_patterns)

    @property
    def is_api_endpoint(self) -> bool:
        """Check if endpoint matches API patterns."""
        api_patterns = {
            "/api/", "/v1/", "/v2/", "/v3/", "/graphql", "/rest/",
            "/ws/", "/webhook", "/callback", "/rpc",
        }
        path_lower = self.path.lower()
        return any(pattern in path_lower for pattern in api_patterns)

    @property
    def is_admin_endpoint(self) -> bool:
        """Check if endpoint matches admin patterns."""
        admin_patterns = {
            "/admin", "/management", "/dashboard", "/console",
            "/control", "/cp", "/backend", "/internal",
        }
        path_lower = self.path.lower()
        return any(pattern in path_lower for pattern in admin_patterns)

    @property
    def is_auth_endpoint(self) -> bool:
        """Check if endpoint matches authentication patterns."""
        auth_patterns = {
            "/login", "/auth", "/sso", "/oauth", "/signin",
            "/signup", "/register", "/password", "/2fa",
        }
        path_lower = self.path.lower()
        return any(pattern in path_lower for pattern in auth_patterns)

    @property
    def is_config_endpoint(self) -> bool:
        """Check if endpoint matches configuration patterns."""
        config_patterns = {
            "/.well-known", "/config", "/settings", "/metadata",
            "/environment", "/version", "/.env", "/swagger", "/openapi",
        }
        path_lower = self.path.lower()
        return any(pattern in path_lower for pattern in config_patterns)

    @property
    def is_upload_endpoint(self) -> bool:
        """Check if endpoint matches upload/file patterns (takeover risk)."""
        upload_patterns = {
            "/upload", "/file", "/media", "/files", "/download",
            "/image", "/pic", "/assets", "/static",
        }
        path_lower = self.path.lower()
        return any(pattern in path_lower for pattern in upload_patterns)

    @property
    def has_sensitive_patterns(self) -> bool:
        """Check for sensitive patterns (credentials, keys, tokens)."""
        sensitive_patterns = {
            "password=", "api_key=", "token=", "secret=",
            "access_token=", "bearer=", "auth=",
            "key=", "credential=", "username=",
        }
        query_lower = (self.query or "").lower()
        path_lower = self.path.lower()
        full_lower = query_lower + path_lower
        return any(pattern in full_lower for pattern in sensitive_patterns)

    def post_init_classify(self) -> None:
        """Classify endpoint type after initialization (must be called manually)."""
        if self.is_api_endpoint:
            self.endpoint_type = EndpointType.API
            self.is_high_value = True
        elif self.is_admin_endpoint:
            self.endpoint_type = EndpointType.ADMIN
            self.is_high_value = True
        elif self.is_auth_endpoint:
            self.endpoint_type = EndpointType.AUTH
            self.is_high_value = True
        elif self.is_config_endpoint:
            self.endpoint_type = EndpointType.CONFIG
            self.is_high_value = True
        elif self.is_upload_endpoint:
            self.endpoint_type = EndpointType.UPLOAD
            self.is_high_value = True
        elif self.is_low_value:
            self.endpoint_type = EndpointType.STATIC
            self.is_high_value = False

        # Check for sensitive patterns
        if self.has_sensitive_patterns:
            if "password" in (self.query or "").lower():
                self.contains_credentials = True
            elif "api_key" in (self.query or "").lower():
                self.contains_api_key = True
            elif "token" in (self.query or "").lower():
                self.contains_token = True


class EndpointProbeResult(BaseModel):
    """Result of probing a historical endpoint."""

    model_config = ConfigDict(extra="forbid", strict=True)

    endpoint_url: str
    target: str
    status: str  # "alive" | "dead" | "timeout" | "redirect"
    registry: EndpointRegistry
    error_message: str | None = None
    probe_duration_ms: int = 0
    redirect_target: str | None = None

    @property
    def is_alive(self) -> bool:
        """Check if endpoint is still alive."""
        return self.status == "alive"


class GauArchiveStats(BaseModel):
    """Statistics from GAU archive discovery run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    total_urls: int = 0
    unique_urls: int = 0
    wayback_count: int = 0
    commoncrawl_count: int = 0
    otx_count: int = 0

    api_endpoints: int = 0
    admin_endpoints: int = 0
    auth_endpoints: int = 0
    static_endpoints: int = 0

    high_value_count: int = 0
    low_value_filtered: int = 0

    duplicates_removed: int = 0

    @property
    def dedup_ratio(self) -> float:
        """Calculate deduplication ratio."""
        if self.total_urls == 0:
            return 0.0
        return (self.total_urls - self.unique_urls) / self.total_urls * 100

    @property
    def source_distribution(self) -> dict[str, float]:
        """Calculate source distribution percentages."""
        if self.unique_urls == 0:
            return {"wayback": 0.0, "commoncrawl": 0.0, "otx": 0.0}

        return {
            "wayback": self.wayback_count / self.unique_urls * 100,
            "commoncrawl": self.commoncrawl_count / self.unique_urls * 100,
            "otx": self.otx_count / self.unique_urls * 100,
        }
