from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class AuditRecord:
    event_id: str
    event_type: str
    finding_id: str
    analyst_id: str
    timestamp: str
    event_data: dict[str, Any]
    event_hash: str
    previous_record_hash: str
    digital_signature: str
    immutable: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "finding_id": self.finding_id,
            "analyst_id": self.analyst_id,
            "timestamp": self.timestamp,
            "event_data": self.event_data,
            "event_hash": self.event_hash,
            "previous_record_hash": self.previous_record_hash,
            "digital_signature": self.digital_signature,
            "immutable": self.immutable,
        }


class HiLAuditTrail:
    """
    Append-only immutable audit log with hash chaining and signatures.
    """

    def __init__(
        self,
        *,
        log_path: str | Path = "tools/hil/data/hil_audit_log.jsonl",
        signing_key: str = "k1-hil-dev-signing-key",
    ) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.signing_key = signing_key.encode("utf-8")

        if not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")

    @staticmethod
    def _stable_json(obj: dict[str, Any]) -> str:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _sign(self, message: str) -> str:
        return hmac.new(self.signing_key, message.encode("utf-8"), hashlib.sha256).hexdigest()

    def _read_all(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def get_previous_record_hash(self) -> str:
        rows = self._read_all()
        if not rows:
            return "GENESIS"
        return str(rows[-1].get("event_hash", "GENESIS"))

    def calculate_hash(self, event_payload: dict[str, Any]) -> str:
        return self._sha256(self._stable_json(event_payload))

    def sign_record(self, record_payload: dict[str, Any]) -> str:
        return self._sign(self._stable_json(record_payload))

    def append_to_immutable_log(self, audit_record: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(self._stable_json(audit_record) + "\n")

    def record_hil_event(
        self,
        *,
        event_type: str,
        finding_id: str,
        analyst_id: str,
        event_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "finding_id": finding_id,
            "analyst_id": analyst_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "event_data": event_data or {},
            "previous_record_hash": self.get_previous_record_hash(),
        }
        event_hash = self.calculate_hash(payload)
        payload["event_hash"] = event_hash
        payload["digital_signature"] = self.sign_record(payload)
        payload["immutable"] = True

        self.append_to_immutable_log(payload)
        return payload

    def verify_chain_integrity(self, events: list[dict[str, Any]] | None = None) -> bool:
        rows = events if events is not None else self._read_all()
        if not rows:
            return True

        prev = "GENESIS"
        for row in rows:
            provided_sig = str(row.get("digital_signature", ""))
            provided_hash = str(row.get("event_hash", ""))
            if str(row.get("previous_record_hash", "")) != prev:
                return False

            check_payload = {
                "event_id": row.get("event_id"),
                "event_type": row.get("event_type"),
                "finding_id": row.get("finding_id"),
                "analyst_id": row.get("analyst_id"),
                "timestamp": row.get("timestamp"),
                "event_data": row.get("event_data"),
                "previous_record_hash": row.get("previous_record_hash"),
            }
            expected_hash = self.calculate_hash(check_payload)
            if expected_hash != provided_hash:
                return False

            check_payload["event_hash"] = provided_hash
            expected_sig = self.sign_record(check_payload)
            if expected_sig != provided_sig:
                return False

            prev = provided_hash
        return True

    def create_timeline(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        timeline = sorted(events, key=lambda e: str(e.get("timestamp", "")))
        return [
            {
                "timestamp": e.get("timestamp"),
                "event_type": e.get("event_type"),
                "analyst_id": e.get("analyst_id"),
                "event_id": e.get("event_id"),
            }
            for e in timeline
        ]

    def get_audit_trail_for_finding(self, finding_id: str) -> dict[str, Any]:
        events = [e for e in self._read_all() if str(e.get("finding_id", "")) == finding_id]
        return {
            "finding_id": finding_id,
            "events": events,
            "timeline": self.create_timeline(events),
            "integrity_verified": self.verify_chain_integrity(events),
        }


__all__ = ["HiLAuditTrail", "AuditRecord"]
