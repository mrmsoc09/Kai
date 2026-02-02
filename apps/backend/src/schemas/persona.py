from __future__ import annotations

from typing import List, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone

MemorySource = Literal['obsidian']
IngestionPolicy = Literal['distilled']
Maturity = Literal['seed','growing','mature']
Plan = Literal['internal','rental','subscription']

class Persona(BaseModel):
    id: str
    role: str
    knowledge_count: int = Field(ge=0)
    last_training_update: datetime
    confidence_trend: List[float] = Field(description='0..100 over recent epochs')
    memory_source: MemorySource = 'obsidian'
    ingestion_policy: IngestionPolicy = 'distilled'
    maturity: Maturity = 'growing'
    rentable: bool = False
    plan: Plan = 'internal'
