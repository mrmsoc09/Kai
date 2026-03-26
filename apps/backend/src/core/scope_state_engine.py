from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaginationCheckpoint(BaseModel):
    source: str
    page_number: int = Field(default=1, ge=1)
    cursor: str | None = None
    next_cursor: str | None = None
    item_count: int = Field(default=0, ge=0)
    updated_at: str = Field(default_factory=_utcnow_iso)


class SessionCheckpoint(BaseModel):
    provider: str
    resume_cursor: str | None = None
    token_expires_at: str | None = None
    updated_at: str = Field(default_factory=_utcnow_iso)


class ScopeStateSnapshot(BaseModel):
    known_asset_hashes: list[str] = Field(default_factory=list)
    page_checkpoints: dict[str, PaginationCheckpoint] = Field(default_factory=dict)
    session_checkpoints: dict[str, SessionCheckpoint] = Field(default_factory=dict)
    last_scan_metadata: dict[str, Any] = Field(default_factory=dict)


class ScopeStateEngine:
    """
    Stateful scope/delta tracker for long-running opportunity scans.

    Tracks:
    - known asset fingerprints (dedupe + delta detection)
    - per-source pagination checkpoints (resume-safe crawling)
    - per-provider session checkpoints (token/cursor continuity)
    """

    def __init__(self, state_path: Path | str):
        self.state_path = Path(state_path).expanduser().resolve()
        self._lock = Lock()
        self._snapshot = ScopeStateSnapshot()

    def load(self) -> None:
        with self._lock:
            if not self.state_path.exists():
                self._snapshot = ScopeStateSnapshot()
                return
            try:
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    self._snapshot = ScopeStateSnapshot()
                    return
                self._snapshot = ScopeStateSnapshot.model_validate(payload)
            except Exception:
                self._snapshot = ScopeStateSnapshot()

    def save(self) -> None:
        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(self._snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def get_asset_fingerprint(self, asset_data: dict[str, Any]) -> str:
        raw_str = f"{asset_data.get('id')}|{asset_data.get('url')}|{asset_data.get('type')}"
        return hashlib.sha256(raw_str.encode()).hexdigest()

    def identify_new_opportunities(self, current_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            known = set(self._snapshot.known_asset_hashes)
            new_items: list[dict[str, Any]] = []
            for asset in current_assets:
                fp = self.get_asset_fingerprint(asset)
                if fp in known:
                    continue
                new_items.append(asset)
                known.add(fp)
            self._snapshot.known_asset_hashes = sorted(known)
            return new_items

    def begin_scan(self, *, scan_id: str, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            merged = dict(self._snapshot.last_scan_metadata)
            merged.update(metadata or {})
            merged.update(
                {
                    "scan_id": scan_id,
                    "started_at": _utcnow_iso(),
                }
            )
            self._snapshot.last_scan_metadata = merged

    def mark_page(
        self,
        *,
        source: str,
        page_number: int,
        cursor: str | None = None,
        next_cursor: str | None = None,
        item_count: int = 0,
    ) -> None:
        with self._lock:
            self._snapshot.page_checkpoints[source] = PaginationCheckpoint(
                source=source,
                page_number=max(1, int(page_number)),
                cursor=cursor,
                next_cursor=next_cursor,
                item_count=max(0, int(item_count)),
                updated_at=_utcnow_iso(),
            )

    def should_fetch_page(self, *, source: str, page_number: int, cursor: str | None = None) -> bool:
        with self._lock:
            checkpoint = self._snapshot.page_checkpoints.get(source)
            if checkpoint is None:
                return True
            if cursor and checkpoint.cursor and cursor != checkpoint.cursor:
                return True
            return int(page_number) >= int(checkpoint.page_number)

    def update_session_checkpoint(
        self,
        *,
        provider: str,
        resume_cursor: str | None = None,
        token_expires_at: str | None = None,
    ) -> None:
        with self._lock:
            self._snapshot.session_checkpoints[provider] = SessionCheckpoint(
                provider=provider,
                resume_cursor=resume_cursor,
                token_expires_at=token_expires_at,
                updated_at=_utcnow_iso(),
            )

    def known_count(self) -> int:
        with self._lock:
            return len(self._snapshot.known_asset_hashes)
