"""Lightweight IO contracts for hooks."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SessionContext:
    request_id: str
    user_id: Optional[str] = None
    program_id: Optional[str] = None
    target: Optional[str] = None
    method: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    tool_id: str
    adapter_id: str
    args: Dict[str, Any]
    scope_allowed: bool = False
    authorized: bool = False


@dataclass
class HookResult:
    ok: bool
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
