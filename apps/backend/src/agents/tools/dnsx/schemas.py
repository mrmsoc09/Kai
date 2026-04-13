"""
DNS Record Schemas for DNSX Agent
Normalizes dnsx JSON output into canonical DnsRegistry models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DnsRecordType(str, Enum):
    """DNS record types that dnsx can resolve."""
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    NS = "NS"
    PTR = "PTR"
    TXT = "TXT"
    SOA = "SOA"
    SRV = "SRV"


class ResolutionStatus(str, Enum):
    """Resolution success/failure status codes."""
    RESOLVED = "resolved"
    NXDOMAIN = "nxdomain"
    TIMEOUT = "timeout"
    REFUSED = "refused"
    SERVFAIL = "servfail"
    NODATA = "nodata"
    WILDCARD = "wildcard"  # Wildcard detected and filtered
    UNKNOWN = "unknown"


class DnsRecord(BaseModel):
    """Canonical DNS record payload."""

    model_config = ConfigDict(extra="forbid", strict=True)

    record_id: UUID = Field(default_factory=uuid4, description="Unique record identifier")
    fqdn: str = Field(min_length=1, max_length=253, description="Fully qualified domain name")
    record_type: DnsRecordType = Field(description="DNS record type (A, AAAA, CNAME, etc)")
    value: str = Field(min_length=1, description="Record value (IP, hostname, etc)")
    ttl: int | None = Field(default=None, ge=0, le=2147483647, description="Time-to-live in seconds")
    status_code: int | None = Field(default=None, ge=0, description="HTTP status code if from HTTP response")
    raw_evidence: dict[str, Any] = Field(default_factory=dict, description="Raw dnsx output for audit")
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Timestamp of discovery")

    @field_validator("fqdn")
    @classmethod
    def validate_fqdn(cls, value: str) -> str:
        """Validate and normalize FQDN."""
        normalized = value.strip().lower()
        if not normalized or len(normalized) > 253:
            raise ValueError("FQDN must be 1-253 characters")
        # Basic FQDN validation (simplified)
        if ".." in normalized or normalized.startswith(".") or normalized.endswith("."):
            raise ValueError("Invalid FQDN format")
        return normalized

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        """Normalize record value."""
        return value.strip().lower() if value else value


class DnsRegistry(BaseModel):
    """DNS resolution registry for a target subdomain."""

    model_config = ConfigDict(extra="forbid", strict=True)

    registry_id: UUID = Field(default_factory=uuid4, description="Unique registry identifier")
    fqdn: str = Field(min_length=1, max_length=253, description="Resolved FQDN")
    target_domain: str = Field(description="Parent domain target")
    resolution_status: ResolutionStatus = Field(description="Resolution success status")

    # Record categories (deduplicated)
    a_records: list[str] = Field(default_factory=list, description="IPv4 addresses (A records)")
    aaaa_records: list[str] = Field(default_factory=list, description="IPv6 addresses (AAAA records)")
    cname_records: list[str] = Field(default_factory=list, description="CNAME targets")
    mx_records: list[str] = Field(default_factory=list, description="Mail exchange servers")
    ns_records: list[str] = Field(default_factory=list, description="Nameservers")
    txt_records: list[str] = Field(default_factory=list, description="TXT records")
    ptr_records: list[str] = Field(default_factory=list, description="Reverse PTR records")

    # Metadata
    is_wildcard: bool = Field(default=False, description="True if wildcard detected and filtered")
    ip_count: int = Field(default=0, ge=0, description="Total unique IP addresses")
    record_count: int = Field(default=0, ge=0, description="Total unique DNS records")
    http_status_code: int | None = Field(default=None, ge=0, description="HTTP status if probed")
    has_takeover_risk: bool = Field(default=False, description="True if subdomain takeover pattern detected")
    takeover_cname: str | None = Field(default=None, description="CNAME indicating takeover risk")

    # Audit trail
    dns_probes: int = Field(default=1, ge=1, description="Number of DNS resolution attempts")
    resolver_used: str = Field(default="system", description="Resolver used (system/doh/custom)")
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Resolution timestamp")
    last_verified_at: datetime | None = Field(default=None, description="Last verification timestamp")

    # Evidence
    raw_dnsx_output: str = Field(default="", description="Raw dnsx JSON output")
    discovery_notes: str = Field(default="", description="Human-readable resolution notes")

    @field_validator("a_records", "aaaa_records", "cname_records", "mx_records", "ns_records", "txt_records", "ptr_records", mode="before")
    @classmethod
    def deduplicate_records(cls, value: Any) -> list[str]:
        """Deduplicate and normalize record lists."""
        if not isinstance(value, list):
            return []
        seen = set()
        result = []
        for item in value:
            if isinstance(item, str):
                normalized = item.strip().lower()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    result.append(normalized)
        return result

    @field_validator("ip_count", mode="before")
    @classmethod
    def calculate_ip_count(cls, value: Any, info) -> int:
        """Calculate unique IP count from A + AAAA records."""
        if isinstance(value, int) and value >= 0:
            return value
        # Get from context during validation
        return 0

    @field_validator("record_count", mode="before")
    @classmethod
    def calculate_record_count(cls, value: Any) -> int:
        """Calculate total unique record count."""
        if isinstance(value, int) and value >= 0:
            return value
        return 0

    def post_init_calculate_counts(self) -> None:
        """Recalculate counts after initialization (must be called manually)."""
        self.ip_count = len(set(self.a_records + self.aaaa_records))
        self.record_count = (
            len(set(self.a_records))
            + len(set(self.aaaa_records))
            + len(set(self.cname_records))
            + len(set(self.mx_records))
            + len(set(self.ns_records))
            + len(set(self.txt_records))
            + len(set(self.ptr_records))
        )

    @property
    def all_ips(self) -> set[str]:
        """Return all resolved IP addresses."""
        return set(self.a_records + self.aaaa_records)

    @property
    def all_records(self) -> dict[str, list[str]]:
        """Return all records organized by type."""
        return {
            "a": self.a_records,
            "aaaa": self.aaaa_records,
            "cname": self.cname_records,
            "mx": self.mx_records,
            "ns": self.ns_records,
            "txt": self.txt_records,
            "ptr": self.ptr_records,
        }

    @property
    def is_alive(self) -> bool:
        """Check if subdomain is alive (has any records or non-NXDOMAIN status)."""
        if self.resolution_status == ResolutionStatus.NXDOMAIN:
            return False
        if self.resolution_status == ResolutionStatus.WILDCARD:
            return False
        return bool(self.a_records or self.aaaa_records or self.cname_records)


class DnsProbeResult(BaseModel):
    """Aggregated result of DNS probing a subdomain."""

    model_config = ConfigDict(extra="forbid", strict=True)

    fqdn: str
    target: str
    status: ResolutionStatus
    records: DnsRegistry
    error_message: str | None = None
    probe_duration_ms: int = 0
    deduped: bool = False  # True if this record was deduplicated
    normalized: bool = False  # True if output was normalized

    @property
    def success(self) -> bool:
        """Check if probe was successful."""
        return self.status in {ResolutionStatus.RESOLVED, ResolutionStatus.NODATA}
