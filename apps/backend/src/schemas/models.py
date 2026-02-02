from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class LoopStep(BaseModel):
    name: str
    ts: Optional[str] = None

class LoopState(BaseModel):
    strategic: LoopStep = LoopStep(name='Plan')
    tactical: LoopStep = LoopStep(name='Orient')

class SystemState(BaseModel):
    loop: LoopState = LoopState()
    autonomy_tier: int = 0
    confidence: float = 0.0
    comms_status: str = 'CLOSED'  # OPEN | CLOSED | BLOCKED
    knowledge_delta: int = 0      # count since last review


class MissionState(BaseModel):
    id: str
    name: str
    status: str = 'idle'
    agents: List[str] = []

class AgentState(BaseModel):
    id: str
    name: str
    role: str
    status: str = 'inactive'

class Evidence(BaseModel):
    id: str
    name: str
    path: str
    hash: Optional[str] = None
    finalized: bool = False
    metadata: Dict[str, str] = {}
