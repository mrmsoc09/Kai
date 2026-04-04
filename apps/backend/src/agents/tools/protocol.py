from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class FindingType(str, Enum):
    SUBDOMAIN = "subdomain"
    IP = "ip"
    PORT = "port"
    URL = "url"
    VULNERABILITY = "vulnerability"
    TECHNOLOGY = "technology"
    METADATA = "metadata"
    CREDENTIAL = "credential"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class KaisonFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: FindingType
    value: str
    source_agent: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity = Severity.INFO
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KaisonResult(BaseModel):
    """The 'Standard Ammunition' for the Kaison Swarm."""
    mission_id: str
    source_agent: str
    target: str
    findings: List[KaisonFinding] = Field(default_factory=list)
    raw_output_path: Optional[str] = None
    next_recommended_agent: Optional[str] = None
    runtime_ms: int = 0
    status: str = "success"  # success, failure, partial


class MissionState(BaseModel):
    """The LangGraph state object."""
    mission_id: str
    root_domain: str
    active_targets: List[str] = Field(default_factory=list)
    discovered_subdomains: set[str] = Field(default_factory=set)
    vulnerabilities: List[KaisonFinding] = Field(default_factory=list)
    history: List[KaisonResult] = Field(default_factory=list)
    current_phase: str = "recon"
