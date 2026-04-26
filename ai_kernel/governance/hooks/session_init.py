"""Session initialization hook."""

from pathlib import Path
from typing import Dict, Any
from .lib.io_contracts import SessionContext, HookResult
from .lib.state_store import StateStore
from .lib.common import logger

POLICY_ROOT = Path(__file__).resolve().parents[1] / "policies"


def run(context: Dict[str, Any]) -> HookResult:
    """Initialize session context; attach request metadata."""
    state = StateStore()
    req_id = context.get("request_id") or context.get("trace_id") or "unknown"
    session = SessionContext(
        request_id=req_id,
        user_id=context.get("user_id"),
        program_id=context.get("program_id"),
        target=context.get("target"),
        method=context.get("method"),
        metadata=context.get("metadata") or {},
    )
    state.set("session", session)
    logger.debug("session_init ok request_id=%s target=%s", session.request_id, session.target)
    return HookResult(ok=True, data={"session": session, "state": state})
