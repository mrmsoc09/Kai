from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypedDict
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_FINDING_VALUE_BYTES = 64 * 1024  # 64 KiB safety cap to prevent tool dump blowups.


class FindingType(str, Enum):
    SUBDOMAIN = "subdomain"
    PORT = "port"
    VULN = "vuln"
    SECRET = "secret"
    CONFIG = "config"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class KaisonFinding(BaseModel):
    """Canonical finding payload used by all specialist agents."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    finding_id: UUID = Field(default_factory=uuid4)
    finding_type: FindingType
    value: str
    source_agent: str = Field(min_length=1, max_length=255)
    confidence: float = 1.0
    severity: Severity = Severity.INFO
    raw_evidence: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("value", "source_agent")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized

    @field_validator("value")
    @classmethod
    def _value_sanity_guard(cls, value: str) -> str:
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) > MAX_FINDING_VALUE_BYTES:
            raise ValueError(
                f"value exceeds safety cap ({len(encoded)} bytes > {MAX_FINDING_VALUE_BYTES} bytes)"
            )
        return value

    @field_validator("finding_type", mode="before")
    @classmethod
    def _normalize_finding_type(cls, value: Any) -> FindingType:
        if isinstance(value, FindingType):
            return value
        if isinstance(value, str):
            token = value.strip().lower()
            try:
                return FindingType(token)
            except ValueError as exc:
                raise ValueError(f"invalid finding_type: {value!r}") from exc
        raise ValueError("finding_type must be a FindingType enum or string")

    @field_validator("finding_id", mode="before")
    @classmethod
    def _normalize_finding_id(cls, value: Any) -> UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value.strip())
            except ValueError as exc:
                raise ValueError(f"invalid finding_id: {value!r}") from exc
        raise ValueError("finding_id must be a UUID or UUID string")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        if isinstance(value, bool):
            raise ValueError("confidence must be numeric")
        if not isinstance(value, (int, float)):
            raise ValueError("confidence must be numeric")
        numeric = float(value)
        if numeric < 0.0:
            return 0.0
        if numeric > 1.0:
            return 1.0
        return numeric

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, value: Any) -> Severity:
        if isinstance(value, Severity):
            return value
        if isinstance(value, str):
            token = value.strip().lower()
            try:
                return Severity(token)
            except ValueError as exc:
                raise ValueError(f"invalid severity: {value!r}") from exc
        raise ValueError("severity must be a Severity enum or string")

    @field_validator("observed_at", mode="before")
    @classmethod
    def _force_finding_utc(cls, value: Any) -> datetime:
        return _force_utc_datetime(value)


class KaisonResultMetadata(BaseModel):
    """Execution metadata for a single agent run."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    started_at: datetime
    ended_at: datetime
    runtime_ms: int = Field(ge=0)

    @field_validator("started_at", "ended_at", mode="before")
    @classmethod
    def _force_metadata_utc(cls, value: Any) -> datetime:
        return _force_utc_datetime(value)

    @model_validator(mode="after")
    def _validate_times(self) -> "KaisonResultMetadata":
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must be greater than or equal to started_at")
        return self


class KaisonResult(BaseModel):
    """Standardized container for all tool-agent output in Kaison."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    result_id: UUID = Field(default_factory=uuid4)
    mission_id: str = Field(min_length=1, max_length=255)
    source_agent: str = Field(min_length=1, max_length=255)
    status: str = Field(min_length=1, max_length=32)
    target_context: dict[str, Any] = Field(default_factory=dict)
    metadata: KaisonResultMetadata
    findings: list[KaisonFinding] = Field(default_factory=list)

    @field_validator("mission_id", "source_agent", "status")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized

    @field_validator("result_id", mode="before")
    @classmethod
    def _normalize_result_id(cls, value: Any) -> UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value.strip())
            except ValueError as exc:
                raise ValueError(f"invalid result_id: {value!r}") from exc
        raise ValueError("result_id must be a UUID or UUID string")


class MissionState(TypedDict, total=False):
    """LangGraph-compatible global mission state contract."""

    mission_id: str
    current_phase: str
    target_queue: list[str]
    pending_targets: list[str]
    active_target: str
    active_targets: list[str]
    completed_targets: list[str]
    re_entry_targets: list[str]
    discovered_assets: dict[str, list[str]]
    execution_profile: dict[str, Any]
    waf_flagged: bool
    cycle_count: int
    max_cycles: int
    state_hash: str
    previous_state_hash: str
    unchanged_cycles: int
    terminate: bool
    terminate_reason: str
    findings: list[KaisonFinding]
    results_history: list[KaisonResult]
    global_state: dict[str, Any]


def _force_utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)

    if isinstance(value, str) and value.strip():
        token = value.strip()
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(token)
        except ValueError as exc:
            raise ValueError(f"invalid datetime: {value!r}") from exc
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    raise ValueError("datetime value must be datetime or ISO8601 string")
