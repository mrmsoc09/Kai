from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    finding_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
