from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Target(BaseModel):
    target_id: str
    value: str
    target_type: str = "domain"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScopeRule(BaseModel):
    rule_id: str
    rule_type: str  # allow | deny | cidr_allow
    pattern: str
    source: str = "policy"


class WorkflowRun(BaseModel):
    run_id: str
    workflow_name: str
    target: str
    status: str
    safe_mode: bool = True
    dry_run: bool = False
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StageRun(BaseModel):
    stage_run_id: str
    run_id: str
    stage_name: str
    status: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    tool_count: int = 0
    success_count: int = 0
    failed_count: int = 0


class ToolExecution(BaseModel):
    execution_id: str
    run_id: str
    stage_name: str
    tool_name: str
    status: str
    target: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    duration_ms: float | None = None
    exit_code: int | None = None
    error: str | None = None
    raw_artifact_path: str | None = None
    normalized_artifact_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveredAsset(BaseModel):
    run_id: str
    host: str
    source_tool: str
    confidence: float = 0.5
    tags: list[str] = Field(default_factory=list)


class DNSRecord(BaseModel):
    run_id: str
    host: str
    record_type: str
    value: str
    source_tool: str


class LiveService(BaseModel):
    run_id: str
    host: str
    port: int
    protocol: str = "tcp"
    service: str | None = None
    source_tool: str = ""


class WebApplication(BaseModel):
    run_id: str
    host: str
    base_url: str
    title: str | None = None
    technologies: list[str] = Field(default_factory=list)
    source_tool: str = ""


class URLRecord(BaseModel):
    run_id: str
    url: str
    host: str | None = None
    source_tool: str = ""


class EndpointRecord(BaseModel):
    run_id: str
    endpoint: str
    host: str | None = None
    method: str | None = None
    source_tool: str = ""


class ParameterRecord(BaseModel):
    run_id: str
    parameter_name: str
    endpoint: str | None = None
    host: str | None = None
    source_tool: str = ""


class TechnologyFingerprint(BaseModel):
    run_id: str
    host: str
    technology: str
    source_tool: str
    confidence: float = 0.5


class SecretFinding(BaseModel):
    run_id: str
    secret_type: str
    location: str
    source_tool: str
    confidence: float = 0.5
    severity_hint: str = "medium"


class VulnCandidate(BaseModel):
    run_id: str
    title: str
    target: str
    source_tool: str
    severity_hint: str = "low"
    confidence: float = 0.4
    evidence_ref: str | None = None


class CorrelationRecord(BaseModel):
    run_id: str
    host: str
    urls: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    open_ports: list[int] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    confidence: float = 0.5


class AnalystExport(BaseModel):
    run_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: dict[str, Any] = Field(default_factory=dict)
    prioritized_findings: list[dict[str, Any]] = Field(default_factory=list)
    raw_report_path: str | None = None
