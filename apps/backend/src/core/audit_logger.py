"""
Kai Platform Audit Logger
=========================
Persists governance decisions and security-relevant events to an append-only
JSONL audit log. Safe for concurrent writes. Each record is tamper-evident
(no in-place mutation) and indexed by timestamp + tenant + mission.

Audit log path: artifacts/audit/audit.jsonl  (overridable via K1_AUDIT_LOG_PATH)

Record schema:
  {
    "audit_id":   "<uuid>",
    "timestamp":  "<ISO 8601 UTC>",
    "event_type": "<audit event type string>",
    "tenant_id":  "<uuid or empty>",
    "user_id":    "<uuid or empty>",
    "mission_id": "<uuid or empty>",
    "decision":   "<approved|blocked|allowed|denied|created|revoked|...>",
    "reason":     "<human-readable reason>",
    "detail":     { ...arbitrary context }
  }
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_AUDIT_LOCK = threading.Lock()


def _audit_log_path() -> Path:
    raw = os.getenv("K1_AUDIT_LOG_PATH", "artifacts/audit/audit.jsonl")
    return Path(raw).resolve()


def _ensure_dir(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("audit_logger: cannot create audit dir %s: %s", path.parent, exc)


def write_audit_record(
    event_type: str,
    *,
    tenant_id: str = "",
    user_id: str = "",
    mission_id: str = "",
    decision: str = "",
    reason: str = "",
    detail: dict[str, Any] | None = None,
) -> str:
    """
    Append a single audit record to the JSONL audit log.

    Thread-safe. Returns the generated audit_id for correlation.
    On write failure, logs the error and returns "" rather than raising —
    audit log failures must never break the request path.
    """
    audit_id = str(uuid.uuid4())
    record = {
        "audit_id": audit_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "tenant_id": tenant_id or "",
        "user_id": user_id or "",
        "mission_id": mission_id or "",
        "decision": decision or "",
        "reason": reason or "",
        "detail": detail or {},
    }
    path = _audit_log_path()
    _ensure_dir(path)
    try:
        line = json.dumps(record, separators=(",", ":"), default=str)
        with _AUDIT_LOCK:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as exc:  # pragma: no cover
        logger.error("audit_logger: failed to write record %s: %s", audit_id, exc)
        return ""
    return audit_id


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


def audit_auth_login(
    user_id: str,
    tenant_id: str,
    username: str,
    success: bool,
    reason: str = "",
    ip_address: str = "",
) -> str:
    return write_audit_record(
        "auth.login",
        tenant_id=tenant_id,
        user_id=user_id,
        decision="success" if success else "failure",
        reason=reason or ("login succeeded" if success else "login failed"),
        detail={"username": username, "ip_address": ip_address},
    )


def audit_auth_token_issued(
    user_id: str,
    tenant_id: str,
    token_name: str = "",
) -> str:
    return write_audit_record(
        "auth.api_token_issued",
        tenant_id=tenant_id,
        user_id=user_id,
        decision="issued",
        reason="API token created",
        detail={"token_name": token_name},
    )


def audit_auth_token_revoked(
    user_id: str,
    tenant_id: str,
    token_id: str,
) -> str:
    return write_audit_record(
        "auth.api_token_revoked",
        tenant_id=tenant_id,
        user_id=user_id,
        decision="revoked",
        reason="API token revoked",
        detail={"token_id": token_id},
    )


def audit_governance_decision(
    mission_id: str,
    tenant_id: str,
    user_id: str,
    decision: str,
    reason: str,
    tool_id: str = "",
    target: str = "",
    risk_band: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    return write_audit_record(
        "governance.decision",
        tenant_id=tenant_id,
        user_id=user_id,
        mission_id=mission_id,
        decision=decision,
        reason=reason,
        detail={
            "tool_id": tool_id,
            "target": target,
            "risk_band": risk_band,
            **(extra or {}),
        },
    )


def audit_approval_action(
    mission_id: str,
    tenant_id: str,
    user_id: str,
    approval_id: str,
    action: str,  # approved | rejected
    reason: str = "",
) -> str:
    return write_audit_record(
        "approval.action",
        tenant_id=tenant_id,
        user_id=user_id,
        mission_id=mission_id,
        decision=action,
        reason=reason or f"approval {action}",
        detail={"approval_id": approval_id},
    )


def audit_mission_created(
    mission_id: str,
    tenant_id: str,
    user_id: str,
    workflow_id: str = "",
    program_id: str = "",
    execution_mode: str = "",
) -> str:
    return write_audit_record(
        "mission.created",
        tenant_id=tenant_id,
        user_id=user_id,
        mission_id=mission_id,
        decision="created",
        reason="mission started",
        detail={
            "workflow_id": workflow_id,
            "program_id": program_id,
            "execution_mode": execution_mode,
        },
    )


def audit_scope_violation(
    mission_id: str,
    tenant_id: str,
    user_id: str,
    target: str,
    reason: str,
) -> str:
    return write_audit_record(
        "scope.violation",
        tenant_id=tenant_id,
        user_id=user_id,
        mission_id=mission_id,
        decision="blocked",
        reason=reason,
        detail={"target": target},
    )
