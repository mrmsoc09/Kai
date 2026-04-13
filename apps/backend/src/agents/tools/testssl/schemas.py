"""
TLS/SSL Cryptographic Analysis Schemas for TestSSL Agent

Models for tracking TLS cipher strength, protocol vulnerabilities,
certificate issues, and encryption grade assessment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TLSVersion(str, Enum):
    """TLS/SSL protocol versions."""
    SSLv3 = "SSLv3"
    TLSv10 = "TLSv1.0"
    TLSv11 = "TLSv1.1"
    TLSv12 = "TLSv1.2"
    TLSv13 = "TLSv1.3"
    UNKNOWN = "unknown"


class CipherStrength(str, Enum):
    """Cipher strength classification."""
    STRONG = "strong"
    WEAK = "weak"
    BROKEN = "broken"
    UNKNOWN = "unknown"


class EncryptionGrade(str, Enum):
    """Overall SSL/TLS encryption grade (A+ to F)."""
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    UNKNOWN = "unknown"


class SSLCipherRegistry(BaseModel):
    """Detailed cipher suite analysis from TLS handshake."""

    model_config = ConfigDict(extra="forbid", strict=True)

    # Identification
    cipher_id: UUID = Field(default_factory=uuid4, description="Unique cipher ID")
    target_host: str = Field(min_length=2, max_length=512, description="Target hostname/IP")
    target_port: int = Field(ge=1, le=65535, default=443, description="Target port")

    # Protocol & Cipher Details
    tls_version: TLSVersion = Field(description="TLS version used")
    cipher_suite: str = Field(min_length=5, max_length=256, description="Cipher suite name")
    cipher_strength: CipherStrength = Field(description="Assessed cipher strength")

    @field_validator("tls_version", mode="before")
    @classmethod
    def _normalize_tls_version(cls, value: Any) -> str:
        """Normalize TLS version string to enum value."""
        if isinstance(value, str):
            # Map common string values to enum values (not names)
            mapping = {
                "sslv3": "SSLv3", "ssl3": "SSLv3",
                "tlsv1.0": "TLSv1.0", "tls1.0": "TLSv1.0", "tlsv1": "TLSv1.0",
                "tlsv1.1": "TLSv1.1", "tls1.1": "TLSv1.1",
                "tlsv1.2": "TLSv1.2", "tls1.2": "TLSv1.2",
                "tlsv1.3": "TLSv1.3", "tls1.3": "TLSv1.3",
            }
            normalized = mapping.get(value.lower(), value)
            return normalized
        return value

    @field_validator("cipher_strength", mode="before")
    @classmethod
    def _normalize_cipher_strength(cls, value: Any) -> str:
        """Normalize cipher strength string to enum value."""
        if isinstance(value, str):
            return value.lower()
        return value
    key_exchange: str = Field(min_length=2, max_length=64, description="Key exchange algorithm")
    authentication: str = Field(min_length=2, max_length=64, description="Authentication algorithm")
    encryption: str = Field(min_length=2, max_length=64, description="Encryption algorithm")
    hash_algorithm: str = Field(min_length=2, max_length=64, description="Hash algorithm")

    # Strength Assessment
    bits: int = Field(ge=0, le=4096, description="Key bits")
    is_deprecated: bool = Field(default=False, description="Deprecated protocol")
    is_weak: bool = Field(default=False, description="Weak cipher")
    is_broken: bool = Field(default=False, description="Broken/exploitable cipher")
    supports_forward_secrecy: bool = Field(default=False, description="Perfect forward secrecy")

    # Known Vulnerabilities
    vulnerable_to_heartbleed: bool = Field(default=False, description="Heartbleed vulnerability")
    vulnerable_to_poodle: bool = Field(default=False, description="POODLE attack")
    vulnerable_to_sweet32: bool = Field(default=False, description="SWEET32 attack")
    vulnerable_to_lucky13: bool = Field(default=False, description="Lucky13 attack")
    known_vulnerabilities: list[str] = Field(default_factory=list, description="CVE references")

    # Detection metadata
    detected_at: datetime = Field(description="Detection timestamp")
    certificate_trusted: bool = Field(default=True, description="SSL certificate trusted")
    certificate_self_signed: bool = Field(default=False, description="Self-signed certificate")


class TLSVulnerabilityRegistry(BaseModel):
    """Registry of TLS/SSL vulnerabilities and weak configurations."""

    model_config = ConfigDict(extra="forbid", strict=True)

    # Identification
    vuln_id: UUID = Field(default_factory=uuid4, description="Unique vulnerability ID")
    target_host: str = Field(min_length=2, max_length=512, description="Target hostname/IP")
    target_port: int = Field(ge=1, le=65535, default=443, description="Target port")

    # Vulnerability Details
    vulnerability_type: str = Field(
        min_length=3, max_length=128,
        description="Type (weak_cipher, deprecated_protocol, cert_issue, etc.)"
    )
    severity: str = Field(
        pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$",
        description="Severity level"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")

    # Technical Details
    affected_protocols: list[TLSVersion] = Field(default_factory=list, description="Affected TLS versions")
    affected_ciphers: list[str] = Field(default_factory=list, description="Affected cipher suites")
    root_cause: str = Field(min_length=5, max_length=512, description="Root cause explanation")

    @field_validator("affected_protocols", mode="before")
    @classmethod
    def _normalize_affected_protocols(cls, value: Any) -> list[str]:
        """Normalize TLS versions in affected_protocols list."""
        if not isinstance(value, list):
            return value
        mapping = {
            "sslv3": "SSLv3", "ssl3": "SSLv3",
            "tlsv1.0": "TLSv1.0", "tls1.0": "TLSv1.0", "tlsv1": "TLSv1.0",
            "tlsv1.1": "TLSv1.1", "tls1.1": "TLSv1.1",
            "tlsv1.2": "TLSv1.2", "tls1.2": "TLSv1.2",
            "tlsv1.3": "TLSv1.3", "tls1.3": "TLSv1.3",
        }
        return [mapping.get(v.lower() if isinstance(v, str) else v, v) for v in value]

    # Remediation
    remediation_steps: list[str] = Field(default_factory=list, description="How to fix")
    recommended_actions: list[str] = Field(default_factory=list, description="Next steps")
    cve_references: list[str] = Field(default_factory=list, description="Related CVEs")

    # Detection Context
    detected_by: str = Field(default="testssl", description="Detection tool")
    detection_timestamp: datetime = Field(description="Detection timestamp")
    is_exploitable: bool = Field(default=False, description="Can be actively exploited")
    exploitation_difficulty: str = Field(
        default="unknown",
        pattern="^(trivial|easy|moderate|difficult|unknown)$",
        description="How easy to exploit"
    )


class SSLScanResultRegistry(BaseModel):
    """Complete SSL/TLS scan result normalization."""

    model_config = ConfigDict(extra="forbid", strict=True)

    # Scan Metadata
    scan_id: UUID = Field(default_factory=uuid4, description="Unique scan ID")
    target_host: str = Field(min_length=2, max_length=512, description="Target hostname/IP")
    target_port: int = Field(ge=1, le=65535, default=443, description="Target port")
    scan_timestamp: datetime = Field(description="When scan was performed")

    # Overall Assessment
    encryption_grade: EncryptionGrade = Field(description="Overall SSL/TLS grade (A+ to F)")
    grade_details: str = Field(default="", max_length=512, description="Grade explanation")

    @field_validator("encryption_grade", mode="before")
    @classmethod
    def _normalize_encryption_grade(cls, value: Any) -> str:
        """Normalize encryption grade string."""
        if isinstance(value, str):
            # Map shorthand to enum values
            mapping = {
                "a+": "A_PLUS", "a_plus": "A_PLUS",
                "a": "A",
                "a-": "A_MINUS", "a_minus": "A_MINUS",
                "b": "B", "c": "C", "d": "D", "e": "E", "f": "F",
            }
            normalized = mapping.get(value.lower().replace(" ", "_"), value)
            return normalized
        return value

    # Protocol Support
    tls_versions_supported: list[TLSVersion] = Field(default_factory=list, description="Supported TLS versions")
    min_tls_version: TLSVersion = Field(default=TLSVersion.UNKNOWN, description="Minimum TLS version")
    max_tls_version: TLSVersion = Field(default=TLSVersion.UNKNOWN, description="Maximum TLS version")

    # Cipher Support
    total_ciphers: int = Field(ge=0, description="Total cipher suites supported")
    strong_ciphers: int = Field(ge=0, description="Strong cipher suites")
    weak_ciphers: int = Field(ge=0, description="Weak cipher suites")
    broken_ciphers: int = Field(ge=0, description="Broken cipher suites")

    @field_validator("tls_versions_supported", mode="before")
    @classmethod
    def _normalize_tls_versions_list(cls, value: Any) -> list[str]:
        """Normalize TLS version strings in list."""
        if not isinstance(value, list):
            return value
        mapping = {
            "sslv3": "SSLv3", "ssl3": "SSLv3",
            "tlsv1.0": "TLSv1.0", "tls1.0": "TLSv1.0", "tlsv1": "TLSv1.0",
            "tlsv1.1": "TLSv1.1", "tls1.1": "TLSv1.1",
            "tlsv1.2": "TLSv1.2", "tls1.2": "TLSv1.2",
            "tlsv1.3": "TLSv1.3", "tls1.3": "TLSv1.3",
        }
        return [mapping.get(v.lower() if isinstance(v, str) else v, v) for v in value]

    @field_validator("min_tls_version", "max_tls_version", mode="before")
    @classmethod
    def _normalize_tls_version_field(cls, value: Any) -> str:
        """Normalize TLS version in min/max fields."""
        if isinstance(value, str):
            mapping = {
                "sslv3": "SSLv3", "ssl3": "SSLv3",
                "tlsv1.0": "TLSv1.0", "tls1.0": "TLSv1.0", "tlsv1": "TLSv1.0",
                "tlsv1.1": "TLSv1.1", "tls1.1": "TLSv1.1",
                "tlsv1.2": "TLSv1.2", "tls1.2": "TLSv1.2",
                "tlsv1.3": "TLSv1.3", "tls1.3": "TLSv1.3",
            }
            return mapping.get(value.lower(), value)
        return value

    # Features
    supports_perfect_forward_secrecy: bool = Field(default=False, description="PFS support")
    supports_session_resumption: bool = Field(default=False, description="Session resumption")
    supports_compression: bool = Field(default=False, description="Compression enabled (usually bad)")
    supports_heartbeat: bool = Field(default=False, description="Heartbeat enabled")

    # Certificate Details
    certificate_subject: str = Field(default="", max_length=512, description="Certificate subject")
    certificate_issuer: str = Field(default="", max_length=512, description="Certificate issuer")
    certificate_valid_from: datetime | None = Field(default=None, description="Certificate validity start")
    certificate_valid_until: datetime | None = Field(default=None, description="Certificate validity end")
    certificate_self_signed: bool = Field(default=False, description="Self-signed certificate")
    certificate_trusted: bool = Field(default=True, description="Certificate chain trusted")
    certificate_expired: bool = Field(default=False, description="Certificate has expired")
    certificate_days_until_expiry: int | None = Field(default=None, description="Days until expiration")

    # Vulnerabilities Found
    vuln_count: int = Field(ge=0, description="Total vulnerabilities found")
    critical_vulns: int = Field(ge=0, description="Critical severity count")
    high_vulns: int = Field(ge=0, description="High severity count")
    medium_vulns: int = Field(ge=0, description="Medium severity count")
    low_vulns: int = Field(ge=0, description="Low severity count")

    # Detection Context
    detected_by: str = Field(default="testssl_agent", description="Detection tool")
    detection_date: datetime = Field(description="Detection timestamp")
    last_verified: datetime | None = Field(default=None, description="Last verification")

    # OPSEC
    via_snl: bool = Field(default=True, description="Routed through Sovereign Network Layer")
    scan_stealth_level: str = Field(default="standard", description="Stealth mode used")
