from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

Severity = Literal['low','medium','high','critical']
Stage = Literal['discovered','validated','exploited','mitigated']
Status = Literal['open','in_progress','closed']
ChainPotential = Literal['low','medium','high']

class Finding(BaseModel):
    id: str
    title: str
    severity: Severity
    type: str
    target_asset: str
    chain_value: int = Field(ge=0, le=100, description='0..100 potential value to enable exploit chains')
    chain_potential: ChainPotential = 'medium'
    stage: Stage = 'discovered'
    status: Status = 'open'
    evidence_completeness: int = Field(ge=0, le=100)
