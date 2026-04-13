"""
Vulnerability Registry Schemas for Dalfox XSS Agent
Normalizes dalfox JSON output into canonical VulnerabilityRegistry models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VulnerabilityType(str, Enum):
    """XSS vulnerability classification."""
    REFLECTED_XSS = "reflected_xss"         # Parameter reflects input
    STORED_XSS = "stored_xss"               # Input stored and rendered
    DOM_XSS = "dom_xss"                     # DOM manipulation vulnerability
    JAVASCRIPT_URL = "javascript_url"       # javascript: protocol injection
    DATA_ATTRIBUTE = "data_attribute"       # SVG/XML attribute injection
    EVENT_HANDLER = "event_handler"         # Event handler injection (onclick, etc.)
    ATTRIBUTE_INJECTION = "attribute_injection"  # HTML attribute breaking
    CONTEXT_CONFUSION = "context_confusion" # Context-aware injection (script vs attribute)
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """Vulnerability severity/risk assessment."""
    CRITICAL = "critical"   # Immediate exploitation risk
    HIGH = "high"           # High exploitation probability
    MEDIUM = "medium"       # Moderate risk, may require user interaction
    LOW = "low"             # Low risk or requires specific conditions
    INFO = "info"           # Informational finding


class ParamType(str, Enum):
    """Parameter classification."""
    QUERY_STRING = "query"
    POST_BODY = "post"
    HEADER = "header"
    COOKIE = "cookie"
    PATH_PARAMETER = "path"
    JSON_BODY = "json"
    XML_BODY = "xml"
    UNKNOWN = "unknown"


class ReflectionType(str, Enum):
    """How parameter is reflected in response."""
    DIRECT = "direct"           # Unescaped reflection
    HTML_ESCAPED = "html_escaped"  # HTML entity encoded
    JAVASCRIPT_ESCAPED = "javascript_escaped"  # JavaScript string escaped
    URL_ENCODED = "url_encoded"    # URL encoded
    DOUBLE_ENCODED = "double_encoded"  # Double-encoded reflection
    PARTIAL = "partial"         # Partial reflection (filtered)
    UNKNOWN = "unknown"


class PoC(BaseModel):
    """Proof of Concept for vulnerability."""

    model_config = ConfigDict(extra="forbid", strict=True)

    payload: str = Field(min_length=1, max_length=5000, description="XSS payload")
    reflection_type: ReflectionType = Field(description="How payload is reflected")
    verified: bool = Field(default=False, description="Payload verified in target response")
    success_indicator: str = Field(default="", description="Text/pattern confirming successful injection")
    encoded_form: str = Field(default="", description="Encoding/mutation of payload")
    bypass_technique: str = Field(default="", description="Bypass technique used (if any)")


class VulnerabilityRegistry(BaseModel):
    """Canonical vulnerability record from Dalfox XSS scanning."""

    model_config = ConfigDict(extra="forbid", strict=True)

    vuln_id: UUID = Field(default_factory=uuid4, description="Unique vulnerability identifier")
    target_url: str = Field(min_length=10, max_length=2048, description="Target URL")
    vulnerable_parameter: str = Field(min_length=1, max_length=256, description="Parameter name")
    param_type: ParamType = Field(description="Parameter location (query, post, header, etc.)")

    # Vulnerability classification
    vuln_type: VulnerabilityType = Field(description="XSS type classification")
    risk_level: RiskLevel = Field(description="Severity/risk assessment")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence (0.0-1.0)")

    # PoC and evidence
    poc_payloads: list[PoC] = Field(default_factory=list, description="Verified PoCs")
    primary_payload: str = Field(description="Primary payload used in detection")
    reflection_type: ReflectionType = Field(description="Reflection classification")

    # Target analysis
    target_domain: str = Field(description="Domain from target URL")
    endpoint_path: str = Field(description="Path component of target")
    full_request: str = Field(default="", description="Full HTTP request (for audit)")
    response_preview: str = Field(default="", max_length=1000, description="Response excerpt (first 1000 chars)")

    # Detection context
    detected_by: str = Field(default="dalfox", description="Detection tool/agent")
    detection_date: datetime = Field(description="When vulnerability was detected")
    last_verified: datetime | None = Field(default=None, description="Last successful verification")

    # Metadata
    bypassable_filters: list[str] = Field(default_factory=list, description="Detected WAF/filter bypasses")
    requires_user_interaction: bool = Field(default=False, description="User interaction required (clicking, etc.)")
    requires_authentication: bool = Field(default=False, description="Authentication needed to exploit")
    is_stored: bool = Field(default=False, description="Vulnerability is stored (not just reflected)")
    is_authenticated_context: bool = Field(default=False, description="Detected in authenticated context")

    # Raw evidence
    raw_dalfox_output: str = Field(default="", description="Raw dalfox JSON output")
    request_headers: dict[str, str] = Field(default_factory=dict, description="Request headers used")
    response_headers: dict[str, str] = Field(default_factory=dict, description="Response headers")
    notes: str = Field(default="", description="Additional findings/notes")

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Validate URL format."""
        normalized = value.strip()
        if not (normalized.startswith("http://") or normalized.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return normalized

    @field_validator("vulnerable_parameter")
    @classmethod
    def validate_parameter(cls, value: str) -> str:
        """Normalize parameter name."""
        return value.strip().lower()

    @property
    def is_critical(self) -> bool:
        """Check if vulnerability is critical risk."""
        return self.risk_level == RiskLevel.CRITICAL and self.confidence > 0.85

    @property
    def is_high_confidence(self) -> bool:
        """Check if detection has high confidence."""
        return self.confidence >= 0.8

    @property
    def has_verified_poc(self) -> bool:
        """Check if at least one PoC is verified."""
        return any(poc.verified for poc in self.poc_payloads)

    @property
    def exploitation_difficulty(self) -> str:
        """Estimate exploitation difficulty."""
        if self.requires_user_interaction and self.requires_authentication:
            return "high"
        elif self.requires_user_interaction or self.requires_authentication:
            return "medium"
        else:
            return "low"

    def add_poc(self, payload: str, reflection: ReflectionType, verified: bool = False) -> None:
        """Add a proof-of-concept payload."""
        poc = PoC(
            payload=payload,
            reflection_type=reflection,
            verified=verified,
        )
        self.poc_payloads.append(poc)

    def mark_verified(self, success_indicator: str) -> None:
        """Mark vulnerability as verified with success indicator."""
        self.last_verified = datetime.now(UTC)
        if self.poc_payloads:
            self.poc_payloads[0].verified = True
            self.poc_payloads[0].success_indicator = success_indicator


class DalfoxFinding(BaseModel):
    """Dalfox JSON output finding."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: str = Field(description="Finding type (xss, reflected, etc.)")
    inurlparam: str = Field(description="Parameter name in URL")
    method: str = Field(description="HTTP method (GET, POST, etc.)")
    data: str = Field(default="", description="Request body data")
    headers: dict[str, str] = Field(default_factory=dict, description="Request headers")
    payload: str = Field(description="XSS payload used")
    evidence: str = Field(description="Evidence from response")
    code: int = Field(ge=0, le=999, description="HTTP status code")
    url: str = Field(description="Target URL")


class XSSStatistics(BaseModel):
    """Statistics from XSS scanning run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    total_urls_scanned: int = 0
    total_parameters_tested: int = 0
    vulnerabilities_found: int = 0

    reflected_xss_count: int = 0
    stored_xss_count: int = 0
    dom_xss_count: int = 0
    other_xss_count: int = 0

    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    verified_count: int = 0
    unverified_count: int = 0

    payloads_tested: int = 0
    total_attempts: int = 0

    @property
    def critical_ratio(self) -> float:
        """Percentage of critical findings."""
        if self.vulnerabilities_found == 0:
            return 0.0
        return self.critical_count / self.vulnerabilities_found * 100

    @property
    def verification_ratio(self) -> float:
        """Percentage of verified findings."""
        if self.vulnerabilities_found == 0:
            return 0.0
        return self.verified_count / self.vulnerabilities_found * 100

    @property
    def success_rate(self) -> float:
        """Success rate of payloads tested."""
        if self.total_attempts == 0:
            return 0.0
        return self.vulnerabilities_found / self.total_attempts * 100

    @property
    def xss_breakdown(self) -> dict[str, int]:
        """XSS type breakdown."""
        return {
            "reflected": self.reflected_xss_count,
            "stored": self.stored_xss_count,
            "dom": self.dom_xss_count,
            "other": self.other_xss_count,
        }
