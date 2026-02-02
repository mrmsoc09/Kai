from __future__ import annotations

from typing import Literal
from pydantic import BaseModel

MCPStatus = Literal['online','degraded','offline','blocked']

class MCPServer(BaseModel):
    id: str
    name: str
    status: MCPStatus
    uptime_seconds: int
    purpose: str  # e.g., feeds graph, validates findings
