from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root() -> Path:
    root = Path(os.getenv("K1_COMMS_ROOT", "artifacts/comms")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _thread_id(run_id: str, finding_id: Optional[str], report_id: Optional[str]) -> str:
    suffix = finding_id or report_id or "default"
    return f"{run_id}:{suffix}"


def _thread_path(thread_id: str) -> Path:
    safe = thread_id.replace("/", "_")
    return _root() / safe / "thread.json"


def _load_thread(thread_id: str) -> Dict[str, Any] | None:
    path = _thread_path(thread_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_thread(thread: Dict[str, Any]) -> Dict[str, Any]:
    path = _thread_path(thread["thread_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(thread, indent=2), encoding="utf-8")
    return thread


def upsert_thread(
    *,
    run_id: str,
    finding_id: Optional[str] = None,
    report_id: Optional[str] = None,
    stakeholder: Optional[str] = None,
) -> Dict[str, Any]:
    thread_id = _thread_id(run_id, finding_id, report_id)
    existing = _load_thread(thread_id)
    if existing:
        if stakeholder:
            existing["stakeholder"] = stakeholder
        existing["updated_at"] = _now()
        return _save_thread(existing)

    thread = {
        "thread_id": thread_id,
        "run_id": run_id,
        "finding_id": finding_id,
        "report_id": report_id,
        "stakeholder": stakeholder,
        "messages": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    return _save_thread(thread)


def append_message(
    *,
    run_id: str,
    channel: str,
    direction: str,
    subject: str,
    body: str,
    finding_id: Optional[str] = None,
    report_id: Optional[str] = None,
    stakeholder: Optional[str] = None,
    artifact_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    thread = upsert_thread(
        run_id=run_id,
        finding_id=finding_id,
        report_id=report_id,
        stakeholder=stakeholder,
    )
    message = {
        "message_id": str(uuid.uuid4()),
        "timestamp": _now(),
        "channel": channel,
        "direction": direction,
        "subject": subject,
        "body": body,
        "artifact_path": artifact_path,
        "metadata": metadata or {},
    }
    thread["messages"].append(message)
    thread["updated_at"] = _now()
    _save_thread(thread)
    return message


def get_thread(thread_id: str) -> Dict[str, Any] | None:
    return _load_thread(thread_id)


def list_threads(run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    threads: List[Dict[str, Any]] = []
    for path in sorted(_root().glob("*/thread.json")):
        thread = json.loads(path.read_text(encoding="utf-8"))
        if run_id and thread.get("run_id") != run_id:
            continue
        threads.append(thread)
    threads.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    return threads
