"""
Basic Praison adapter contract with deterministic reconciliation semantics.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


class PraisonAdapterBackend(Protocol):
    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def status(self, job_id: str) -> dict[str, Any]:
        ...

    def result(self, job_id: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class PraisonAdapterTicket:
    adapter_job_id: str
    idempotency_key: str
    request_hash: str
    submitted_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "adapter_job_id": self.adapter_job_id,
            "idempotency_key": self.idempotency_key,
            "request_hash": self.request_hash,
            "submitted_at": self.submitted_at,
        }


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_status(raw_status: Any) -> str:
    normalized = str(raw_status or "").strip().lower()
    if normalized in {"submitted", "queued", "running", "completed", "failed", "cancelled"}:
        return normalized
    return "unknown"


class BasicPraisonAdapterContract:
    """
    Submit/status/result contract with deterministic reconciliation output.
    """

    def __init__(self, backend: PraisonAdapterBackend) -> None:
        self._backend = backend

    def submit(
        self,
        *,
        mission_id: str,
        workflow_id: str,
        program_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> PraisonAdapterTicket:
        request_payload = {
            "mission_id": mission_id,
            "workflow_id": workflow_id,
            "program_id": program_id,
            "idempotency_key": idempotency_key,
            "payload": payload,
        }
        response = self._backend.submit(request_payload)
        adapter_job_id = str(response.get("job_id") or response.get("adapter_job_id") or "").strip()
        if not adapter_job_id:
            raise RuntimeError("Praison submit response missing job_id")
        return PraisonAdapterTicket(
            adapter_job_id=adapter_job_id,
            idempotency_key=idempotency_key,
            request_hash=_stable_hash(request_payload),
            submitted_at=datetime.now(timezone.utc).isoformat(),
        )

    def status(self, adapter_job_id: str) -> dict[str, Any]:
        raw = self._backend.status(adapter_job_id)
        return {
            "adapter_job_id": adapter_job_id,
            "status": _normalize_status(raw.get("status")),
            "progress": raw.get("progress"),
            "updated_at": str(raw.get("updated_at") or datetime.now(timezone.utc).isoformat()),
            "raw": raw,
        }

    def result(self, adapter_job_id: str) -> dict[str, Any]:
        raw = self._backend.result(adapter_job_id)
        status = _normalize_status(raw.get("status") or raw.get("state"))
        return {
            "adapter_job_id": adapter_job_id,
            "status": status if status != "unknown" else "completed",
            "result": raw.get("result", {}),
            "error": raw.get("error"),
            "completed_at": str(raw.get("completed_at") or datetime.now(timezone.utc).isoformat()),
            "raw": raw,
        }

    def reconcile(self, ticket: PraisonAdapterTicket) -> dict[str, Any]:
        """
        Deterministically reconcile adapter status/result into a single payload.
        """
        status_view = self.status(ticket.adapter_job_id)
        status = status_view.get("status")
        if status in {"completed", "failed", "cancelled"}:
            terminal = self.result(ticket.adapter_job_id)
            return {
                "adapter_job_id": ticket.adapter_job_id,
                "idempotency_key": ticket.idempotency_key,
                "request_hash": ticket.request_hash,
                "status": terminal.get("status"),
                "result": terminal.get("result", {}),
                "error": terminal.get("error"),
                "terminal": True,
                "reconciled_at": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "adapter_job_id": ticket.adapter_job_id,
            "idempotency_key": ticket.idempotency_key,
            "request_hash": ticket.request_hash,
            "status": status,
            "result": {},
            "error": None,
            "terminal": False,
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
        }
