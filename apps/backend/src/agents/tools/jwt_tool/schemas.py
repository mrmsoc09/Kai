"""
JWT Authentication Security Schemas for K1 Platform

Models for tracking JWT vulnerabilities, cryptographic weaknesses,
and authentication bypass risks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JwtAlgorithm(str, Enum):
    """JWT algorithms."""
    HS256 = "HS256"  # HMAC with SHA-256
    HS384 = "HS384"  # HMAC with SHA-384
    HS512 = "HS512"  # HMAC with SHA-512
    RS256 = "RS256"  # RSA with SHA-256
    RS384 = "RS384"  # RSA with SHA-384
    RS512 = "RS512"  # RSA with SHA-512
    ES256 = "ES256"  # ECDSA with SHA-256
    ES384 = "ES384"  # ECDSA with SHA-384
    ES512 = "ES512"  # ECDSA with SHA-512
    PS256 = "PS256"  # RSA PSS with SHA-256
    PS384 = "PS384"  # RSA PSS with SHA-384
    PS512 = "PS512"  # RSA PSS with SHA-512
    NONE = "none"    # No signature (vulnerable)
    UNKNOWN = "unknown"


class VulnerabilityVector(str, Enum):
    """JWT vulnerability vectors."""
    ALG_NONE = "alg_none"                      # algorithm: none
    WEAK_SECRET = "weak_secret"                # Weak/crackable secret
    KEY_CONFUSION = "key_confusion"            # RS256 downgrade to HS256
    EXPIRED_TOKEN = "expired_token"            # Expired but accepted
    SIGNATURE_BYPASS = "signature_bypass"      # Signature verification disabled
    JWT_INJECTION = "jwt_injection"            # JWT injection in headers
    KID_INJECTION = "kid_injection"            # Key ID manipulation
    SENSITIVE_DATA = "sensitive_data"          # Secrets in claims
    ALGORITHM_DOWNGRADE = "algorithm_downgrade"  # Algo downgrade attack
    REPLAY_ATTACK = "replay_attack"            # Token reusability
    UNKNOWN = "unknown"


class ClaimType(str, Enum):
    """JWT claim types."""
    STANDARD = "standard"      # Standard claims (iss, sub, aud, exp)
    SENSITIVE = "sensitive"    # Sensitive data (email, password, api_key)
    ROLE = "role"             # Role/permission claims
    ADMIN = "admin"           # Admin flag
    USER_ID = "user_id"       # User identifier
    SCOPE = "scope"           # OAuth scope
    UNKNOWN = "unknown"


class ForgeCapability(str, Enum):
    """Ability to forge tokens."""
    ADMIN_ESCALATION = "admin_escalation"      # Can forge admin tokens
    ROLE_CHANGE = "role_change"                # Can change user roles
    PERMISSION_GRANT = "permission_grant"      # Can add permissions
    USER_IMPERSONATION = "user_impersonation"  # Can impersonate any user
    UNKNOWN = "unknown"


class AuthSecurityRegistry(BaseModel):
    """Registry of JWT vulnerabilities and authentication weaknesses."""

    model_config = ConfigDict(extra="forbid", strict=True)

    # Identification
    token_id: UUID = Field(default_factory=uuid4, description="Unique token ID")
    token_location: str = Field(description="Where token was found (header, cookie, body)")
    target_url: str = Field(min_length=10, max_length=2048, description="Target URL")

    # JWT structure
    jwt_alg: JwtAlgorithm = Field(description="JWT algorithm used")
    algorithm_strength: str = Field(default="unknown", description="Algorithm strength rating")
    token_payload: dict[str, Any] = Field(default_factory=dict, description="Decoded token claims")
    token_header: dict[str, Any] = Field(default_factory=dict, description="JWT header")
    token_signature: str = Field(default="", description="Signature value (first 50 chars)")

    # Vulnerability assessment
    vuln_vector: VulnerabilityVector = Field(description="Primary vulnerability")
    secondary_vectors: list[VulnerabilityVector] = Field(
        default_factory=list, description="Additional vulnerabilities"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")

    # Cryptographic analysis
    signature_verified: bool = Field(default=False, description="Signature verified successfully")
    signature_valid: bool = Field(default=False, description="Signature is cryptographically valid")
    secret_cracked: bool = Field(default=False, description="Secret key cracked/discovered")
    cracked_secret: str = Field(default="", max_length=256, description="Discovered secret (masked)")
    crack_attempts: int = Field(ge=0, default=0, description="Brute-force attempts used")
    crack_time_seconds: float = Field(ge=0, default=0, description="Time to crack secret")

    # Forgery capability
    forgeable: bool = Field(default=False, description="Token can be forged")
    forge_capability: ForgeCapability = Field(
        default=ForgeCapability.UNKNOWN, description="What type of token can be forged"
    )
    forged_admin_token: str = Field(default="", max_length=5000, description="Generated admin token")
    forged_token_verified: bool = Field(default=False, description="Forged token tested successfully")

    # Claims analysis
    claims_sensitive: list[ClaimType] = Field(
        default_factory=list, description="Sensitive claim types found"
    )
    sensitive_values_exposed: list[str] = Field(
        default_factory=list, description="Sensitive values (masked)"
    )
    expiration_time: datetime | None = Field(default=None, description="Token expiration")
    is_expired: bool = Field(default=False, description="Token is expired")
    expiration_enforced: bool = Field(default=False, description="Expiration checked by server")

    # Risk assessment
    is_critical: bool = Field(default=False, description="Critical security issue")
    risk_level: str = Field(default="unknown", description="CRITICAL/HIGH/MEDIUM/LOW")
    authentication_bypass: bool = Field(default=False, description="Can bypass authentication")
    privilege_escalation: bool = Field(default=False, description="Can escalate privileges")
    data_exposure: bool = Field(default=False, description="Sensitive data exposed")

    # Detection context
    detected_by: str = Field(default="jwt_tool", description="Detection tool")
    detection_date: datetime = Field(description="Discovery timestamp")
    last_verified: datetime | None = Field(default=None, description="Last verification")

    # Metadata
    request_method: str = Field(default="GET", description="HTTP method used")
    request_headers: dict[str, str] = Field(default_factory=dict, description="Request headers")
    response_status: int = Field(ge=100, le=599, default=200, description="HTTP response status")
    notes: str = Field(default="", description="Additional findings")

    # OPSEC
    rate_limited: bool = Field(default=True, description="Brute-force was rate-limited")
    via_snl: bool = Field(default=True, description="Routed through Sovereign Network Layer")

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Validate URL format."""
        normalized = value.strip()
        if not (normalized.startswith("http://") or normalized.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return normalized

    @property
    def is_critical_finding(self) -> bool:
        """Check if finding is critical."""
        return (
            self.confidence > 0.85
            and (
                self.forgeable
                or self.authentication_bypass
                or self.vuln_vector == VulnerabilityVector.ALG_NONE
            )
        )

    @property
    def exploitation_difficulty(self) -> str:
        """Estimate exploitation difficulty."""
        if self.vuln_vector == VulnerabilityVector.ALG_NONE:
            return "low"
        elif self.secret_cracked:
            return "low"
        elif self.vuln_vector == VulnerabilityVector.WEAK_SECRET:
            return "medium"
        elif self.vuln_vector == VulnerabilityVector.KEY_CONFUSION:
            return "medium"
        elif self.vuln_vector == VulnerabilityVector.EXPIRED_TOKEN:
            return "high"
        return "unknown"


class AuthStatistics(BaseModel):
    """Statistics from JWT analysis run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tokens_analyzed: int = 0
    tokens_vulnerable: int = 0
    signatures_valid: int = 0
    signatures_invalid: int = 0
    signatures_cracked: int = 0

    alg_none_count: int = 0
    weak_secret_count: int = 0
    key_confusion_count: int = 0
    expired_count: int = 0
    injectable_count: int = 0

    tokens_forgeable: int = 0
    admin_tokens_forged: int = 0

    critical_severity: int = 0
    high_severity: int = 0
    medium_severity: int = 0
    low_severity: int = 0

    @property
    def vulnerability_ratio(self) -> float:
        """Percentage of vulnerable tokens."""
        if self.tokens_analyzed == 0:
            return 0.0
        return self.tokens_vulnerable / self.tokens_analyzed * 100

    @property
    def critical_exposure_count(self) -> int:
        """Count of critical/high severity exposures."""
        return self.critical_severity + self.high_severity
