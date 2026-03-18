"""
K1 Profile Performance Tracker (Phase 4.5)
=============================================
Tracks execution performance metrics for all tool profiles and prompt profiles
across missions, enabling data-driven profile selection.

Tracked metrics per profile:
  - executions:       Total times this profile was used
  - successes:        Times execution completed without failure
  - total_score:      Sum of composite strategy scores
  - total_signal:     Sum of signal_value scores
  - total_time:       Sum of actual execution seconds
  - total_fp:         Sum of false positive counts
  - total_findings:   Sum of total findings produced

Derived metrics (computed on read):
  - success_rate:     successes / executions
  - avg_score:        total_score / executions
  - avg_signal:       total_signal / executions
  - avg_time:         total_time / executions
  - fp_rate:          total_fp / max(total_findings, 1)

Governance:
  - All metric updates are auditable (event emitted)
  - Metrics are append-only (no overwrites of raw counters)
  - Thread-safe read/write
  - No LLM calls — pure arithmetic
  - Profile tracker cannot modify profiles, governance, or graph topology

Persistence:
  - JSONL file at {K1_ARTIFACTS_ROOT}/knowledge/profile_metrics.jsonl
  - In-memory aggregation for fast lookup
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.backend.src.core.praison_execution_events import (
    emit,
    profile_score_updated_event,
)
from apps.backend.src.core.praison_strategy_scoring import StrategyScore

logger = logging.getLogger(__name__)


# -- Profile metrics -----------------------------------------------------------


@dataclass
class ProfileMetrics:
    """
    Mutable aggregate metrics for a single profile.

    Not frozen — counters are updated incrementally.
    Thread-safety is handled by the parent ProfileTracker lock.
    """
    profile_id: str = ""
    profile_type: str = ""  # "tool" or "prompt"
    profile_name: str = ""

    # Raw counters (append-only accumulation)
    executions: int = 0
    successes: int = 0
    total_score: float = 0.0
    total_signal: float = 0.0
    total_time: float = 0.0
    total_fp: int = 0
    total_findings: int = 0

    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # -- Derived metrics -------------------------------------------------------

    @property
    def success_rate(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.successes / self.executions

    @property
    def avg_score(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.total_score / self.executions

    @property
    def avg_signal(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.total_signal / self.executions

    @property
    def avg_time(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.total_time / self.executions

    @property
    def fp_rate(self) -> float:
        if self.total_findings == 0:
            return 0.0
        return self.total_fp / self.total_findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type,
            "profile_name": self.profile_name,
            "executions": self.executions,
            "successes": self.successes,
            "total_score": round(self.total_score, 4),
            "total_signal": round(self.total_signal, 4),
            "total_time": round(self.total_time, 2),
            "total_fp": self.total_fp,
            "total_findings": self.total_findings,
            "success_rate": round(self.success_rate, 4),
            "avg_score": round(self.avg_score, 4),
            "avg_signal": round(self.avg_signal, 4),
            "avg_time": round(self.avg_time, 2),
            "fp_rate": round(self.fp_rate, 4),
            "last_updated": self.last_updated,
        }


# -- Profile update record (persisted to JSONL) --------------------------------


@dataclass(frozen=True)
class ProfileUpdateRecord:
    """
    Immutable record of a single profile metric update.
    Persisted to JSONL for full audit trail.
    """
    profile_id: str = ""
    profile_type: str = ""
    mission_id: str = ""
    phase: str = ""
    strategy_id: str = ""
    success: bool = True
    composite_score: float = 0.0
    signal_score: float = 0.0
    actual_seconds: float = 0.0
    false_positives: int = 0
    total_findings: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type,
            "mission_id": self.mission_id,
            "phase": self.phase,
            "strategy_id": self.strategy_id,
            "success": self.success,
            "composite_score": round(self.composite_score, 4),
            "signal_score": round(self.signal_score, 4),
            "actual_seconds": round(self.actual_seconds, 2),
            "false_positives": self.false_positives,
            "total_findings": self.total_findings,
            "timestamp": self.timestamp,
        }


# -- ProfileTracker ------------------------------------------------------------


class ProfileTracker:
    """
    Tracks performance metrics for tool and prompt profiles.

    Thread-safe. All updates produce audit events. Metrics are
    append-only — counters accumulate, never overwrite.
    """

    def __init__(self, storage_root: str | None = None) -> None:
        root = Path(storage_root or os.getenv("K1_ARTIFACTS_ROOT", "artifacts"))
        self._metrics_path = root / "knowledge" / "profile_metrics.jsonl"
        self._metrics: dict[str, ProfileMetrics] = {}
        self._lock = threading.Lock()
        self._file_lock = threading.Lock()

    def record_execution(
        self,
        profile_id: str,
        profile_type: str,
        profile_name: str,
        score: StrategyScore,
        success: bool = True,
        actual_seconds: float = 0.0,
        false_positives: int = 0,
        total_findings: int = 0,
        mission_id: str = "",
        workflow_id: str = "",
        program_id: str = "",
    ) -> ProfileMetrics:
        """
        Record execution outcome for a profile.

        Updates in-memory metrics, persists update record, emits event.
        Returns the updated metrics for the profile.
        """
        with self._lock:
            metrics = self._metrics.get(profile_id)
            if metrics is None:
                metrics = ProfileMetrics(
                    profile_id=profile_id,
                    profile_type=profile_type,
                    profile_name=profile_name,
                )
                self._metrics[profile_id] = metrics

            metrics.executions += 1
            if success:
                metrics.successes += 1
            metrics.total_score += score.composite_score
            metrics.total_signal += score.signal_value_score
            metrics.total_time += actual_seconds
            metrics.total_fp += false_positives
            metrics.total_findings += total_findings
            metrics.last_updated = datetime.now(timezone.utc).isoformat()

            snapshot = metrics.to_dict()

        # Persist update record
        record = ProfileUpdateRecord(
            profile_id=profile_id,
            profile_type=profile_type,
            mission_id=mission_id,
            phase=score.phase,
            strategy_id=score.strategy_id,
            success=success,
            composite_score=score.composite_score,
            signal_score=score.signal_value_score,
            actual_seconds=actual_seconds,
            false_positives=false_positives,
            total_findings=total_findings,
        )
        self._persist(record)

        # Emit telemetry
        emit(profile_score_updated_event(
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            profile_id=profile_id,
            profile_type=profile_type,
            new_score=snapshot["avg_score"],
        ))

        logger.info(
            "Profile %s (%s) updated: executions=%d avg_score=%.3f success_rate=%.2f",
            profile_id, profile_type,
            snapshot["executions"], snapshot["avg_score"], snapshot["success_rate"],
        )
        return self._metrics[profile_id]

    def get_metrics(self, profile_id: str) -> ProfileMetrics | None:
        """Get current metrics for a profile. Returns None if no data."""
        with self._lock:
            return self._metrics.get(profile_id)

    def get_all_metrics(self, profile_type: str | None = None) -> list[ProfileMetrics]:
        """Get metrics for all tracked profiles, optionally filtered by type."""
        with self._lock:
            results = list(self._metrics.values())
        if profile_type:
            results = [m for m in results if m.profile_type == profile_type]
        return results

    def rank_profiles(
        self,
        profile_type: str,
        metric: str = "avg_score",
        min_executions: int = 3,
    ) -> list[ProfileMetrics]:
        """
        Rank profiles by a derived metric. Only includes profiles with
        sufficient executions to avoid noisy rankings.

        Valid metrics: avg_score, success_rate, avg_signal, fp_rate, avg_time
        """
        valid_metrics = {"avg_score", "success_rate", "avg_signal", "fp_rate", "avg_time"}
        if metric not in valid_metrics:
            raise ValueError(f"Invalid ranking metric '{metric}'. Must be one of: {sorted(valid_metrics)}")

        candidates = self.get_all_metrics(profile_type=profile_type)
        candidates = [m for m in candidates if m.executions >= min_executions]

        # For fp_rate and avg_time, lower is better
        reverse = metric not in ("fp_rate", "avg_time")
        candidates.sort(key=lambda m: getattr(m, metric), reverse=reverse)
        return candidates

    def best_profile(
        self,
        profile_ids: list[str],
        metric: str = "avg_score",
        min_executions: int = 3,
    ) -> str | None:
        """
        Select the best profile from a set of candidates based on metric.

        Returns None if no profile has enough executions.
        Used by the learning system to recommend profiles.
        """
        valid_metrics = {"avg_score", "success_rate", "avg_signal", "fp_rate", "avg_time"}
        if metric not in valid_metrics:
            raise ValueError(f"Invalid ranking metric '{metric}'.")

        best_id = None
        best_val = None

        lower_is_better = metric in ("fp_rate", "avg_time")

        with self._lock:
            for pid in profile_ids:
                m = self._metrics.get(pid)
                if m is None or m.executions < min_executions:
                    continue
                val = getattr(m, metric)
                if best_val is None:
                    best_id, best_val = pid, val
                elif lower_is_better and val < best_val:
                    best_id, best_val = pid, val
                elif not lower_is_better and val > best_val:
                    best_id, best_val = pid, val

        return best_id

    def profile_count(self) -> int:
        with self._lock:
            return len(self._metrics)

    def _persist(self, record: ProfileUpdateRecord) -> None:
        try:
            self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
            with self._file_lock:
                with self._metrics_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record.to_dict()) + "\n")
        except Exception as exc:
            logger.warning("Failed to persist profile record %s: %s", record.profile_id, exc)


# -- Module singleton ----------------------------------------------------------

_TRACKER: ProfileTracker | None = None


def get_profile_tracker() -> ProfileTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = ProfileTracker()
    return _TRACKER


def initialize_profile_tracker(storage_root: str | None = None) -> ProfileTracker:
    global _TRACKER
    _TRACKER = ProfileTracker(storage_root)
    return _TRACKER
