from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InstallCheck(BaseModel):
    """Result of running install_verification_cmd."""

    status: Literal["ok", "missing", "skipped", "error"]
    detail: str = ""
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CredentialCheck(BaseModel):
    """Whether declared api_keys_required are present in the environment."""

    status: Literal["ready", "missing", "not_required", "unchecked"]
    required_keys: list[str] = Field(default_factory=list)
    present_keys: list[str] = Field(default_factory=list)
    missing_keys: list[str] = Field(default_factory=list)
    detail: str = ""

    model_config = ConfigDict(from_attributes=True)


class WrapperCheck(BaseModel):
    """Whether the tool adapter is registered and its schema is valid."""

    status: Literal["ok", "failed", "not_registered", "skipped"]
    registry_tool_id: str | None = None
    detail: str = ""

    model_config = ConfigDict(from_attributes=True)


class RuntimePresenceCheck(BaseModel):
    status: Literal["present", "missing", "not_required"]
    binary_present: bool = False
    binary_path: str | None = None
    container_image_configured: bool = False
    docker_available: bool = False
    detail: str = ""

    model_config = ConfigDict(from_attributes=True)


class SmokeTestCheck(BaseModel):
    status: Literal["ok", "failed", "not_registered", "skipped"]
    detail: str = ""

    model_config = ConfigDict(from_attributes=True)


class SafeModeCompatibility(BaseModel):
    compatible: bool
    requires_override: bool
    detail: str = ""

    model_config = ConfigDict(from_attributes=True)


class RecentExecutionSummary(BaseModel):
    """Recent execution history sourced from telemetry JSONL."""

    window_size: int = Field(description="Number of recent runs considered")
    total: int = 0
    completed: int = 0
    failed: int = 0
    failure_rate: float = 0.0
    last_status: str | None = None
    last_executed_at: str | None = None
    failure_reasons: list[str] = Field(
        default_factory=list,
        description="Deduplicated recent failure messages, newest first",
    )

    model_config = ConfigDict(from_attributes=True)


OverallHealth = Literal["healthy", "degraded", "unavailable", "unchecked"]


class ToolHealthReport(BaseModel):
    """Complete health record for a single tool."""

    tool_name: str
    name: str
    category: str
    enabled_status: Literal["enabled", "disabled_by_policy", "disabled_by_default"]
    enabled: bool
    execution_mode: str
    safety_classification: str
    enabled_by_default: bool
    policy_enabled: bool
    tags: list[str] = Field(default_factory=list)
    api_keys_required: list[str] = Field(default_factory=list)
    timeout_seconds: int = 180
    binary_or_image_presence: RuntimePresenceCheck
    install_verification_status: Literal["ok", "missing", "skipped", "error"]
    required_environment_variables_present: bool = True
    credential_status: Literal["ready", "missing", "not_required", "unchecked"]
    wrapper_smoke_test_status: Literal["ok", "failed", "not_registered", "skipped"]
    safe_mode_compatibility: SafeModeCompatibility
    last_execution_status: str | None = None
    last_failure_reason: str | None = None
    last_execution_at: str | None = None
    install: InstallCheck
    credentials: CredentialCheck
    wrapper: WrapperCheck
    smoke_test: SmokeTestCheck
    recent_executions: RecentExecutionSummary
    overall_health: OverallHealth
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    total: int = 0
    healthy: int = 0
    degraded: int = 0
    unavailable: int = 0
    unchecked: int = 0
    total_tools: int = 0
    healthy_tools: int = 0
    tools_missing_binary: int = 0
    tools_missing_credentials: int = 0
    tools_with_failed_verification: int = 0

    model_config = ConfigDict(from_attributes=True)


class ToolHealthDashboard(BaseModel):
    """Full tool health dashboard response."""

    generated_at: datetime
    install_timeout_seconds: int = Field(
        description="Timeout used for each install_verification_cmd"
    )
    summary: DashboardSummary
    by_category: dict[str, DashboardSummary] = Field(default_factory=dict)
    tools: list[ToolHealthReport] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
