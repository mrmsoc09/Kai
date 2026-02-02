from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime

LogCategory = Literal['plan','execution','evidence','governance','audit','metrics','learning']
LogType = Literal['decision_trace','reasoning_summary','evidence_links','knowledge_delta']

class DecisionTraceEntry(BaseModel):
    id: str
    ts: datetime
    gpee_step: Literal['goal','plan','execute','evaluate']
    ooda_step: Literal['observe','orient','decide','act']
    action: str
    score: dict = Field(description='score breakdown, redacted')
    outcome: str = Field(description='short, redacted outcome summary (no raw CoT)')
    category: LogCategory = 'plan'
    tags: List[str] = []

class ReasoningSummary(BaseModel):
    run_id: str
    ts: datetime
    title: str
    bullets: List[str] = Field(description='structured, redacted summary bullets')
    categories: List[LogCategory] = []
    tags: List[str] = []

class EvidenceLink(BaseModel):
    id: str
    ts: datetime
    label: str
    path: str
    artifact_type: str
    category: LogCategory = 'evidence'
    tags: List[str] = []

class KnowledgeDeltaEntry(BaseModel):
    id: str
    ts: datetime
    summary: str
    impact_score: int = Field(ge=0, le=100)
    applies_to: List[str] = Field(description='e.g., persona, policy, graph, dorks')
    category: LogCategory = 'learning'
    tags: List[str] = []

class LogIndex(BaseModel):
    run_id: str
    available: List[LogType]
    counts: dict
