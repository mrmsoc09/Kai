
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    finding_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    id: str
    title: Optional[str] = None
    severity: Optional[str] = None
    type: Optional[str] = None
    target_asset: Optional[str] = None
    chain_value: Optional[int] = None
    chain_potential: Optional[str] = None
    stage: Optional[str] = None
    status: Optional[str] = None
    evidence_completeness: Optional[int] = None
    description: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)


class SystemState(BaseModel):
    comms_status: str = 'OPEN'
    knowledge_delta: int = 0
    version: Optional[str] = None
    services: Dict[str, Any] = Field(default_factory=dict)


class MissionState(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    objective: Optional[str] = None
    progress: float = 0.0
    run_id: Optional[str] = None
    status: str = 'idle'


class AgentState(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    ok: bool = True
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class Persona(BaseModel):
    id: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    knowledge_count: Optional[int] = None
    last_training_update: Optional[datetime] = None
    confidence_trend: List[int] = Field(default_factory=list)
    maturity: Optional[str] = None
    rentable: Optional[bool] = None
    plan: Optional[str] = None


class MCPServer(BaseModel):
    id: Optional[str] = None
    name: str
    status: Optional[str] = None
    uptime_seconds: Optional[int] = None
    purpose: Optional[str] = None

