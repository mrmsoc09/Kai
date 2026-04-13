"""
CRLF Injection Detection Schemas for K1 Platform

Models for tracking CRLF (Carriage Return Line Feed) injection vulnerabilities,
response splitting attacks, header injection, and session hijacking risks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExploitVector(str, Enum):
    """CRLF injection exploit vectors."""
    HEADER_INJECTION = "header_injection"      # Direct header injection
    RESPONSE_SPLITTING = "response_splitting"  # HTTP response splitting
    CACHE_POISONING = "cache_poisoning"        # Cache poisoning via CRLF
    SESSION_HIJACKING = "session_hijacking"    # Session/auth token injection
    COOKIE_INJECTION = "cookie_injection"      # Set-Cookie header injection
    XSS_VIA_HEADER = "xss_via_header"          # XSS via header injection
    OPEN_REDIRECT = "open_redirect"            # Redirect header injection
    UNKNOWN = "unknown"


class InjectionPoint(str, Enum):
    """Location where CRLF is injectable."""
    URL_PARAMETER = "url_parameter"            # Query string parameter
    POST_PARAMETER = "post_parameter"          # POST body parameter
    HEADER_VALUE = "header_value"              # HTTP header value
    COOKIE_VALUE = "cookie_value"              # Cookie value
    PATH_PARAMETER = "path_parameter"          # URL path segment
    JSON_FIELD = "json_field"                  # JSON body field
    XML_FIELD = "xml_field"                    # XML body field
    UNKNOWN = "unknown"


class ConfirmationMethod(str, Enum):
    """How the CRLF injection was confirmed."""
    RESPONSE_HEADER_MODIFIED = "response_header_modified"  # Response headers changed
    RESPONSE_BODY_SPLIT = "response_body_split"            # Response body separated
    STATUS_CODE_CHANGED = "status_code_changed"            # HTTP status changed
    NEW_HEADERS_INJECTED = "new_headers_injected"          # Custom headers added
    PATTERN_DETECTION = "pattern_detection"                # Pattern match in response
    TIMING_ANALYSIS = "timing_analysis"                    # Timing-based detection
    BLIND = "blind"                                         # Blind injection (unconfirmed)
    UNKNOWN = "unknown"


class CrlfVulnerabilityRegistry(BaseModel):
    """Registry of CRLF injection vulnerabilities and HTTP response splitting attacks."""

    model_config = ConfigDict(extra="forbid", strict=True)

    # Identification
    vuln_id: UUID = Field(default_factory=uuid4, description="Unique vulnerability ID")
    target_url: str = Field(
        min_length=10, max_length=2048, description="Target URL being tested"
    )
    vulnerable_parameter: str = Field(description="Parameter/header accepting CRLF")
    injection_point: InjectionPoint = Field(description="Where CRLF is injected")
    exploit_vector: ExploitVector = Field(description="Type of exploit enabled")

    # Exploitation details
    injected_payload: str = Field(description="CRLF payload used for exploitation")
    confirmation_method: ConfirmationMethod = Field(description="How injection confirmed")
    response_status_original: int = Field(ge=100, le=599, default=200, description="Original HTTP status")
    response_status_modified: int = Field(ge=100, le=599, default=200, description="Modified HTTP status")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")

    # Risk assessment
    can_inject_headers: bool = Field(default=False, description="Can inject arbitrary headers")
    can_inject_body: bool = Field(default=False, description="Can inject response body")
    can_split_response: bool = Field(default=False, description="Can split HTTP response")
    session_hijacking_risk: bool = Field(default=False, description="Risk of session hijacking")
    cache_poisoning_risk: bool = Field(default=False, description="Risk of cache poisoning")
    xss_risk: bool = Field(default=False, description="XSS via header injection possible")
    open_redirect_risk: bool = Field(default=False, description="Open redirect via Location header")

    # Response analysis
    raw_response: str = Field(default="", max_length=5000, description="Response preview")
    response_headers: dict[str, str] = Field(default_factory=dict, description="Modified headers")
    header_injection_evidence: list[str] = Field(default_factory=list, description="Evidence of header injection")
    body_split_evidence: str = Field(default="", description="Evidence of response body split")

    # Detection context
    detected_by: str = Field(default="crlfuzz", description="Detection tool")
    detection_date: datetime = Field(description="Discovery timestamp")
    last_verified: datetime | None = Field(default=None, description="Last verification")
    payload_used: str = Field(default="\\r\\n", description="CRLF sequence used")

    # Metadata
    request_method: str = Field(default="GET", description="HTTP method used")
    request_headers: dict[str, str] = Field(default_factory=dict, description="Request headers")
    target_domain: str = Field(default="", description="Domain being tested")
    endpoint_path: str = Field(default="", description="API endpoint path")
    is_authenticated_context: bool = Field(default=False, description="Auth required for exploitation")
    notes: str = Field(default="", description="Additional findings")

    # OPSEC
    stealthy: bool = Field(default=True, description="OPSEC measures applied")
    bypass_technique: str = Field(default="", description="WAF bypass used")

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
            self.confidence > 0.85
            and (
                self.session_hijacking_risk
                or self.cache_poisoning_risk
                or self.can_split_response
            )
        )

    @property
    def exploitation_difficulty(self) -> str:
        """Estimate exploitation difficulty."""
        if self.can_split_response and self.can_inject_headers:
            return "low"
        elif self.can_inject_headers:
            return "medium"
        elif (
            self.confirmation_method
            == ConfirmationMethod.RESPONSE_HEADER_MODIFIED
        ):
            return "medium"
        elif (
            self.confirmation_method == ConfirmationMethod.BLIND
        ):
            return "high"
        return "unknown"

    @property
    def risk_level(self) -> str:
        """Determine risk level based on exploitation potential."""
        if self.session_hijacking_risk or self.can_split_response:
            return "CRITICAL"
        elif (
            self.cache_poisoning_risk
            or self.xss_risk
            or self.can_inject_headers
        ):
            return "HIGH"
        elif self.confirmation_method != ConfirmationMethod.BLIND:
            return "MEDIUM"
        return "LOW"


class CrlfStatistics(BaseModel):
    """Statistics from CRLF fuzzing run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    total_urls_tested: int = 0
    total_parameters_tested: int = 0
    crlf_vulns_confirmed: int = 0
    crlf_vulns_probable: int = 0
    crlf_vulns_blind: int = 0

    header_injection_count: int = 0
    response_splitting_count: int = 0
    cache_poisoning_count: int = 0
    session_hijacking_risk_count: int = 0

    critical_severity: int = 0
    high_severity: int = 0
    medium_severity: int = 0
    low_severity: int = 0

    @property
    def confirmation_ratio(self) -> float:
        """Percentage of confirmed vs blind CRLF findings."""
        if self.crlf_vulns_confirmed + self.crlf_vulns_probable == 0:
            return 0.0
        return (
            self.crlf_vulns_confirmed
            / (self.crlf_vulns_confirmed + self.crlf_vulns_probable)
            * 100
        )

    @property
    def critical_exposure_count(self) -> int:
        """Count of critical/high severity exposures."""
        return self.critical_severity + self.high_severity
