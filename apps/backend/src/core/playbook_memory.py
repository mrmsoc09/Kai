from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any

from .praison_execution_events import MissionEvent, get_event_bus

logger = logging.getLogger(__name__)


def _norm(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


@dataclass
class PlaybookLookupResult:
    playbook_id: str
    score: float
    reasons: list[str]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "score": round(self.score, 4),
            "reasons": self.reasons,
            "metadata": self.metadata,
        }


class PlaybookMemory:
    """
    Singleton in-memory cache for chain-orchestration JSON indices.

    Primary lookup directory:
      tools/playbooks/chain_orchestration/

    Fallback:
      tools/playbooks/*.json
    """

    _instance: PlaybookMemory | None = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        *,
        chain_orchestration_dir: str | Path | None = None,
        playbook_root: str | Path | None = None,
    ) -> None:
        self.playbook_root = Path(playbook_root or "tools/playbooks").resolve()
        self.chain_dir = Path(
            chain_orchestration_dir or self.playbook_root / "chain_orchestration"
        ).resolve()

        self._data: dict[str, Any] = {}
        self._cve_to_playbooks: dict[str, set[str]] = defaultdict(set)
        self._tech_to_playbooks: dict[str, set[str]] = defaultdict(set)
        self._playbook_meta: dict[str, dict[str, Any]] = {}
        self._contract_pairs: set[tuple[str, str]] = set()
        self._metrics: dict[str, float] = {
            "LOOKUP_LATENCY_MS": 0.0,
            "CHAIN_VALIDATION_TIME": 0.0,
        }

        self._watcher_thread: threading.Thread | None = None
        self._watcher_stop = threading.Event()
        self._watched_mtimes: dict[str, float] = {}
        self._lock = threading.RLock()

        self._redis_client = None
        self._initialize_redis_optional()
        self.reload_indices(reason="boot")

    @classmethod
    def get_instance(
        cls,
        *,
        chain_orchestration_dir: str | Path | None = None,
        playbook_root: str | Path | None = None,
    ) -> PlaybookMemory:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(
                    chain_orchestration_dir=chain_orchestration_dir,
                    playbook_root=playbook_root,
                )
            return cls._instance

    def _initialize_redis_optional(self) -> None:
        redis_url = os.getenv("K1_PLAYBOOK_MEMORY_REDIS_URL", "").strip()
        use_redis = os.getenv("K1_PLAYBOOK_MEMORY_USE_REDIS", "false").lower() == "true"
        if not use_redis or not redis_url:
            return
        try:
            import redis  # type: ignore

            self._redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            self._redis_client.ping()
            logger.info("PlaybookMemory redis cache enabled")
        except Exception as exc:
            logger.warning("PlaybookMemory redis unavailable: %s", exc)
            self._redis_client = None

    def _index_files(self) -> list[Path]:
        files: list[Path] = []
        if self.chain_dir.exists():
            files.extend(sorted(self.chain_dir.glob("*.json")))
        if not files and self.playbook_root.exists():
            files.extend(sorted(self.playbook_root.glob("*.json")))
        return files

    def _yaml_files(self) -> list[Path]:
        if not self.playbook_root.exists():
            return []
        return sorted(self.playbook_root.rglob("*.yaml"))

    def _emit_compilation_event(self, reason: str) -> None:
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="LOGIC_COMPILATION_COMPLETE",
                    phase="playbook_memory",
                    detail={
                        "signal": "LOGIC_COMPILATION_COMPLETE",
                        "reason": reason,
                        "index_files_loaded": sorted(self._data.keys()),
                        "at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            )
        except Exception:
            logger.debug("event emission failed", exc_info=True)

    def _emit_metric(self, metric: str, value: float) -> None:
        self._metrics[metric] = float(value)
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="vrad_metric",
                    phase="playbook_memory",
                    detail={"metric": metric, "value": float(value)},
                )
            )
        except Exception:
            logger.debug("metric emission failed", exc_info=True)

    def _persist_to_redis(self) -> None:
        if self._redis_client is None:
            return
        try:
            payload = {
                "data": self._data,
                "cve_to_playbooks": {k: sorted(v) for k, v in self._cve_to_playbooks.items()},
                "tech_to_playbooks": {k: sorted(v) for k, v in self._tech_to_playbooks.items()},
                "playbook_meta": self._playbook_meta,
                "contract_pairs": [list(pair) for pair in sorted(self._contract_pairs)],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._redis_client.set("k1:playbook_memory", json.dumps(payload))
        except Exception:
            logger.debug("redis persist failed", exc_info=True)

    def _extract_playbook_index_rows(self) -> list[dict[str, Any]]:
        payload = self._data.get("playbook_index")
        if not isinstance(payload, dict):
            return []
        rows = payload.get("playbooks_by_success_weight")
        return rows if isinstance(rows, list) else []

    def _build_fast_indices(self) -> None:
        self._cve_to_playbooks.clear()
        self._tech_to_playbooks.clear()
        self._playbook_meta.clear()
        self._contract_pairs.clear()

        alias_to_id: dict[str, str] = {}

        for row in self._extract_playbook_index_rows():
            if not isinstance(row, dict):
                continue
            pb_id = str(row.get("id") or "").strip()
            if not pb_id:
                continue
            self._playbook_meta[pb_id] = row
            alias_to_id[_norm(pb_id)] = pb_id
            name = str(row.get("name") or "").strip()
            if name:
                alias_to_id[_norm(name)] = pb_id
            for token in row.get("tags", []):
                self._tech_to_playbooks[_norm(str(token))].add(pb_id)
            for token in row.get("tools", []):
                self._tech_to_playbooks[_norm(str(token))].add(pb_id)
            for token in row.get("prerequisites", []):
                self._tech_to_playbooks[_norm(str(token))].add(pb_id)

        def resolve_playbook_ref(value: str) -> str:
            token = _norm(value)
            mapped = alias_to_id.get(token)
            if mapped:
                return mapped
            for alias, pb_id in alias_to_id.items():
                if token in alias or alias in token:
                    return pb_id
            return value

        cve_payload = self._data.get("cve_index")
        if isinstance(cve_payload, dict):
            for cve_id, entries in cve_payload.items():
                cve_key = str(cve_id).strip().upper()
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, str):
                            self._cve_to_playbooks[cve_key].add(resolve_playbook_ref(entry))
                        elif isinstance(entry, dict):
                            pb = str(entry.get("playbook_id") or entry.get("id") or "").strip()
                            if pb:
                                self._cve_to_playbooks[cve_key].add(resolve_playbook_ref(pb))
                elif isinstance(entries, dict):
                    pb_list = entries.get("playbooks")
                    if isinstance(pb_list, list):
                        for pb in pb_list:
                            if isinstance(pb, str):
                                self._cve_to_playbooks[cve_key].add(resolve_playbook_ref(pb))

        prereq_payload = self._data.get("prerequisite_index")
        if isinstance(prereq_payload, dict):
            for key, value in prereq_payload.items():
                tech_key = _norm(key)
                if isinstance(value, list):
                    for row in value:
                        if isinstance(row, str):
                            self._tech_to_playbooks[tech_key].add(resolve_playbook_ref(row))
                        elif isinstance(row, dict):
                            pb = str(row.get("playbook_id") or row.get("id") or "").strip()
                            if pb:
                                self._tech_to_playbooks[tech_key].add(resolve_playbook_ref(pb))
                elif isinstance(value, dict):
                    for pb in value.get("playbooks", []):
                        if isinstance(pb, str):
                            self._tech_to_playbooks[tech_key].add(resolve_playbook_ref(pb))

        contracts_payload = self._data.get("data_contract_registry")
        if isinstance(contracts_payload, dict):
            if isinstance(contracts_payload.get("contracts"), list):
                for row in contracts_payload["contracts"]:
                    if not isinstance(row, dict):
                        continue
                    out_s = _norm(str(row.get("output_schema") or ""))
                    in_s = _norm(str(row.get("input_schema") or ""))
                    if out_s and in_s:
                        self._contract_pairs.add((out_s, in_s))
            matrix = contracts_payload.get("compatibility_matrix")
            if isinstance(matrix, dict):
                for out_schema, inputs in matrix.items():
                    if isinstance(inputs, dict):
                        for in_schema, ok in inputs.items():
                            if ok:
                                self._contract_pairs.add((_norm(out_schema), _norm(in_schema)))
                    elif isinstance(inputs, list):
                        for in_schema in inputs:
                            self._contract_pairs.add((_norm(out_schema), _norm(str(in_schema))))
            flat_pairs = contracts_payload.get("pairs")
            if isinstance(flat_pairs, list):
                for pair in flat_pairs:
                    if (
                        isinstance(pair, list)
                        and len(pair) == 2
                        and isinstance(pair[0], str)
                        and isinstance(pair[1], str)
                    ):
                        self._contract_pairs.add((_norm(pair[0]), _norm(pair[1])))

    def reload_indices(self, *, reason: str = "manual") -> None:
        started = time.perf_counter()
        with self._lock:
            loaded: dict[str, Any] = {}
            for path in self._index_files():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning("Failed to load index file %s: %s", path, exc)
                    continue
                loaded[path.stem] = payload
            self._data = loaded
            self._build_fast_indices()
            self._persist_to_redis()

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._emit_metric("LOOKUP_LATENCY_MS", elapsed_ms)
        self._emit_compilation_event(reason=reason)

    def metrics(self) -> dict[str, float]:
        with self._lock:
            return dict(self._metrics)

    def get_index(self, name: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(name, default)

    def match_target_to_playbook(
        self,
        cve_id: str,
        tech_stack: list[str] | tuple[str, ...] | None = None,
        *,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        tech_stack = list(tech_stack or [])
        started = time.perf_counter()

        score: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)

        cve_key = str(cve_id or "").strip().upper()
        cve_candidates = self._cve_to_playbooks.get(cve_key, set())
        for pb in cve_candidates:
            score[pb] += 10.0
            reasons[pb].append(f"cve_match:{cve_key}")

        for tech in tech_stack:
            tech_key = _norm(tech)
            for pb in self._tech_to_playbooks.get(tech_key, set()):
                score[pb] += 2.0
                reasons[pb].append(f"tech_match:{tech_key}")

        ranked: list[PlaybookLookupResult] = []
        for pb, sc in score.items():
            meta = self._playbook_meta.get(pb, {})
            success_weight = float(meta.get("success_weight") or 0.0)
            final_score = sc + success_weight
            ranked.append(
                PlaybookLookupResult(
                    playbook_id=pb,
                    score=final_score,
                    reasons=reasons.get(pb, []),
                    metadata={
                        "name": meta.get("name"),
                        "category": meta.get("category"),
                        "success_weight": success_weight,
                        "tools": meta.get("tools", []),
                    },
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._emit_metric("LOOKUP_LATENCY_MS", elapsed_ms)
        return [item.as_dict() for item in ranked[: max(1, int(top_k))]]

    def validate_handoff(self, output_schema: str, input_schema: str) -> bool:
        started = time.perf_counter()
        with self._lock:
            ok = (_norm(output_schema), _norm(input_schema)) in self._contract_pairs
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._emit_metric("CHAIN_VALIDATION_TIME", elapsed_ms)
        return ok

    def start_watcher(self, *, interval_seconds: float = 2.0) -> None:
        if self._watcher_thread and self._watcher_thread.is_alive():
            return
        self._watcher_stop.clear()
        self._watched_mtimes = {
            str(path): path.stat().st_mtime for path in self._yaml_files() if path.exists()
        }

        def _run() -> None:
            while not self._watcher_stop.is_set():
                changed = False
                current: dict[str, float] = {}
                for path in self._yaml_files():
                    if not path.exists():
                        continue
                    mtime = path.stat().st_mtime
                    key = str(path)
                    current[key] = mtime
                    if key not in self._watched_mtimes or self._watched_mtimes[key] != mtime:
                        changed = True
                if changed:
                    self._watched_mtimes = current
                    self.reload_indices(reason="yaml_change_detected")
                time.sleep(max(0.2, interval_seconds))

        self._watcher_thread = threading.Thread(
            target=_run,
            daemon=True,
            name="k1-playbook-memory-watcher",
        )
        self._watcher_thread.start()

    def stop_watcher(self) -> None:
        self._watcher_stop.set()
        if self._watcher_thread and self._watcher_thread.is_alive():
            self._watcher_thread.join(timeout=2.0)
