from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from .praison_execution_events import MissionEvent, get_event_bus

logger = logging.getLogger(__name__)


def _norm(value: str) -> str:
    return str(value or "").strip().lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text_for_fingerprint(fp: dict[str, Any]) -> str:
    return " | ".join(
        [
            f"os={fp.get('os', '')}",
            f"service={fp.get('service', '')}",
            f"waf={fp.get('waf', '')}",
            f"version={fp.get('version', '')}",
            f"ip_range={fp.get('ip_range', '')}",
        ]
    )


def _resolve_storage_path(storage_path: str | Path | None) -> Path:
    """
    Resolve a writable storage path.

    Preferred order:
    1) Explicit `storage_path`
    2) `K1_EXPERIENCE_MEMORY_PATH`
    3) Legacy NVMe default
    4) Local runtime fallback (always writable in repo sandbox)
    """
    configured = (
        storage_path
        or os.getenv("K1_EXPERIENCE_MEMORY_PATH")
        or "/mnt/nvme/k1-experience-memory/chromadb"
    )
    primary = Path(str(configured)).expanduser()
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError as exc:
        fallback = Path.cwd() / "runtime" / "k1-experience-memory" / "chromadb"
        fallback.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "ExperienceMemory path '%s' unavailable (%s); using fallback '%s'",
            primary,
            exc,
            fallback,
        )
        return fallback


class _HashEmbeddingFunction:
    """
    Deterministic local embedding function.

    Avoids external model downloads so Chroma remains fully local/offline.
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = max(16, int(dim))

    def __call__(self, input: list[str]) -> list[list[float]]:  # chroma embedding signature
        return [self.embed(text) for text in input]

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _norm(text).split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = digest[0] % self.dim
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


@dataclass
class Lesson:
    lesson_id: str
    target_fingerprint: dict[str, Any]
    attempted_cve: str
    outcome: str
    mutation_used: str
    created_at: str
    metadata: dict[str, Any]

    def as_metadata(self) -> dict[str, Any]:
        return {
            "attempted_cve": self.attempted_cve,
            "outcome": self.outcome,
            "mutation_used": self.mutation_used,
            "os": str(self.target_fingerprint.get("os") or ""),
            "service": str(self.target_fingerprint.get("service") or ""),
            "waf": str(self.target_fingerprint.get("waf") or ""),
            "version": str(self.target_fingerprint.get("version") or ""),
            "ip_range": str(self.target_fingerprint.get("ip_range") or ""),
            "created_at": self.created_at,
            "success": self.outcome == "Success",
        }

    def as_document(self) -> str:
        return json.dumps(
            {
                "fingerprint": self.target_fingerprint,
                "attempted_cve": self.attempted_cve,
                "outcome": self.outcome,
                "mutation_used": self.mutation_used,
                "metadata": self.metadata,
            },
            sort_keys=True,
        )


class ExperienceMemory:
    """
    Local vector memory for K1 execution lessons.

    Default backend:
      - ChromaDB PersistentClient at NVMe path
    Fallback backend:
      - in-process memory with deterministic vector similarity
    """

    _instance: ExperienceMemory | None = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        *,
        storage_path: str | Path | None = None,
        disable_chroma: bool | None = None,
    ) -> None:
        self.storage_path = _resolve_storage_path(storage_path)
        self._embedding = _HashEmbeddingFunction(dim=64)
        self._disable_chroma = (
            disable_chroma
            if disable_chroma is not None
            else os.getenv("K1_EXPERIENCE_MEMORY_DISABLE_CHROMA", "false").lower() == "true"
        )
        self._collection = None
        self._fallback_rows: list[dict[str, Any]] = []
        self._waf_policies: dict[str, dict[str, Any]] = {}
        self._attempts = 0
        self._successes = 0
        self._lock = threading.RLock()
        self._init_backend()

    @classmethod
    def get_instance(
        cls,
        *,
        storage_path: str | Path | None = None,
        disable_chroma: bool | None = None,
    ) -> ExperienceMemory:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(storage_path=storage_path, disable_chroma=disable_chroma)
            return cls._instance

    def _init_backend(self) -> None:
        if self._disable_chroma:
            return
        try:
            import chromadb  # type: ignore

            client = chromadb.PersistentClient(path=str(self.storage_path))
            self._collection = client.get_or_create_collection(
                name="k1_execution_lessons",
                embedding_function=self._embedding,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.warning("ChromaDB unavailable; falling back to in-process lesson memory: %s", exc)
            self._collection = None

    def _emit_event(self, event_type: str, detail: dict[str, Any]) -> None:
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type=event_type,
                    phase="experience_memory",
                    detail=detail,
                )
            )
        except Exception:
            logger.debug("ExperienceMemory event emit failed", exc_info=True)

    def _emit_efficiency_metric(self) -> None:
        ratio = self.exploit_efficiency_ratio()
        self._emit_event(
            "vrad_metric",
            {"metric": "EXPLOIT_EFFICIENCY_RATIO", "value": ratio},
        )

    def record_lesson(
        self,
        *,
        target_fingerprint: dict[str, Any],
        attempted_cve: str,
        outcome: str,
        mutation_used: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        lesson = Lesson(
            lesson_id=str(uuid4()),
            target_fingerprint=dict(target_fingerprint or {}),
            attempted_cve=str(attempted_cve or "").strip(),
            outcome=str(outcome or "Silence").strip(),
            mutation_used=str(mutation_used or "default").strip(),
            created_at=_now_iso(),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            if self._collection is not None:
                self._collection.add(
                    ids=[lesson.lesson_id],
                    documents=[lesson.as_document()],
                    metadatas=[lesson.as_metadata()],
                )
            else:
                self._fallback_rows.append(
                    {
                        "id": lesson.lesson_id,
                        "document": lesson.as_document(),
                        "metadata": lesson.as_metadata(),
                        "vector": self._embedding.embed(lesson.as_document()),
                    }
                )

            self._attempts += 1
            if lesson.outcome == "Success":
                self._successes += 1

            waf_name = _norm(str(lesson.target_fingerprint.get("waf") or ""))
            ip_range = str(lesson.target_fingerprint.get("ip_range") or "").strip()
            if lesson.outcome == "WAF_Trigger" and ip_range:
                self.enforce_waf_bypass_for_ip_range(
                    ip_range=ip_range,
                    waf_vendor=waf_name or "unknown",
                )

        self._emit_efficiency_metric()
        return lesson.lesson_id

    def _query_fallback(
        self,
        *,
        query_doc: str,
        attempted_cve: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        qv = self._embedding.embed(query_doc)
        rows: list[tuple[float, dict[str, Any]]] = []
        for row in self._fallback_rows:
            md = row.get("metadata", {})
            if attempted_cve and _norm(md.get("attempted_cve")) != _norm(attempted_cve):
                continue
            rv = row.get("vector", [])
            score = sum(float(a) * float(b) for a, b in zip(qv, rv))
            rows.append((score, row))
        rows.sort(key=lambda item: item[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, row in rows[: max(1, limit)]:
            out.append(
                {
                    "id": row.get("id"),
                    "score": float(score),
                    "metadata": row.get("metadata", {}),
                }
            )
        return out

    def query_lessons(
        self,
        *,
        target_fingerprint: dict[str, Any],
        attempted_cve: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query_doc = json.dumps(
            {
                "target_fingerprint": target_fingerprint,
                "attempted_cve": attempted_cve or "",
            },
            sort_keys=True,
        )
        with self._lock:
            if self._collection is None:
                return self._query_fallback(
                    query_doc=query_doc,
                    attempted_cve=attempted_cve,
                    limit=limit,
                )

            where: dict[str, Any] | None = None
            if attempted_cve:
                where = {"attempted_cve": str(attempted_cve)}
            result = self._collection.query(
                query_texts=[query_doc],
                n_results=max(1, int(limit)),
                where=where,
            )
            ids = (result.get("ids") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            out: list[dict[str, Any]] = []
            for idx, lesson_id in enumerate(ids):
                md = metadatas[idx] if idx < len(metadatas) else {}
                distance = float(distances[idx]) if idx < len(distances) else 1.0
                out.append(
                    {
                        "id": lesson_id,
                        "score": 1.0 - distance,
                        "metadata": md if isinstance(md, dict) else {},
                    }
                )
            return out

    def recommend_strategy(
        self,
        *,
        target_fingerprint: dict[str, Any],
        attempted_cve: str,
        fallback_list: list[str] | None = None,
    ) -> dict[str, Any]:
        lessons = self.query_lessons(
            target_fingerprint=target_fingerprint,
            attempted_cve=attempted_cve,
            limit=25,
        )
        if not lessons:
            return {
                "recall_hit": False,
                "failure_rate": 0.0,
                "selected_mutation": None,
                "low_slow": False,
                "reason": "no_prior_lessons",
            }

        outcomes = Counter(_norm(row.get("metadata", {}).get("outcome", "")) for row in lessons)
        attempts = sum(outcomes.values())
        failures = (
            outcomes.get("waf_trigger", 0)
            + outcomes.get("rate_limit", 0)
            + outcomes.get("silence", 0)
        )
        failure_rate = float(failures / attempts) if attempts else 0.0
        low_slow = outcomes.get("waf_trigger", 0) > 0 or outcomes.get("rate_limit", 0) > 0

        successful_mutations = [
            str(row.get("metadata", {}).get("mutation_used") or "")
            for row in lessons
            if _norm(row.get("metadata", {}).get("outcome")) == "success"
            and str(row.get("metadata", {}).get("mutation_used") or "").strip()
        ]
        mutation_choice = None
        if successful_mutations:
            mutation_choice = Counter(successful_mutations).most_common(1)[0][0]
        elif fallback_list:
            mutation_choice = fallback_list[0]

        strategy = {
            "recall_hit": True,
            "failure_rate": round(failure_rate, 4),
            "selected_mutation": mutation_choice,
            "low_slow": low_slow or (failure_rate >= 0.6 and attempts >= 3),
            "reason": "historical_failure_pattern" if failure_rate >= 0.6 else "historical_signal",
            "lesson_count": attempts,
        }
        self._emit_event(
            "MEMORY_RECALL_SUCCESS",
            {
                "signal": "MEMORY_RECALL_SUCCESS",
                "attempted_cve": attempted_cve,
                "failure_rate": strategy["failure_rate"],
                "selected_mutation": mutation_choice,
                "low_slow": strategy["low_slow"],
                "target_fingerprint": _text_for_fingerprint(target_fingerprint),
            },
        )
        return strategy

    def enforce_waf_bypass_for_ip_range(self, *, ip_range: str, waf_vendor: str) -> None:
        with self._lock:
            self._waf_policies[ip_range] = {
                "policy": "WAF-Bypass",
                "waf_vendor": str(waf_vendor or "unknown"),
                "updated_at": _now_iso(),
            }

    def waf_policy_for_ip_range(self, ip_range: str) -> dict[str, Any] | None:
        with self._lock:
            policy = self._waf_policies.get(str(ip_range))
            return dict(policy) if policy else None

    def exploit_efficiency_ratio(self) -> float:
        with self._lock:
            if self._attempts <= 0:
                return 0.0
            return round(float(self._successes / self._attempts), 6)
