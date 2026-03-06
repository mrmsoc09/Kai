from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict


@dataclass(frozen=True)
class MethodPolicy:
    method: str
    max_requests_per_minute: int
    max_concurrent: int
    max_executions_per_hour: int


class OPSECPolicyError(Exception):
    pass


class OPSECPolicyEngine:
    """
    Centralized OPSEC control for worker dispatch:
    - Rate limiting per method
    - Concurrency caps per method
    - Hourly execution budget per method
    """

    def __init__(self, policies: Dict[str, MethodPolicy]):
        self._policies = dict(policies)
        self._minute_window: Dict[str, deque[float]] = defaultdict(deque)
        self._hour_window: Dict[str, deque[float]] = defaultdict(deque)
        self._active_counts: Dict[str, int] = defaultdict(int)
        self._lock = Lock()
        self._telemetry_path = (
            Path(os.getenv("K1_OPSEC_TELEMETRY_PATH", "artifacts/telemetry/opsec_policy.jsonl")).resolve()
        )
        self._telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    def _policy_for(self, method: str) -> MethodPolicy:
        if method in self._policies:
            return self._policies[method]
        # Unknown methods use strict defaults.
        return MethodPolicy(
            method=method,
            max_requests_per_minute=10,
            max_concurrent=1,
            max_executions_per_hour=100,
        )

    def _prune(self, now: float, method: str) -> None:
        minute_cutoff = now - 60.0
        hour_cutoff = now - 3600.0
        minute_q = self._minute_window[method]
        hour_q = self._hour_window[method]
        while minute_q and minute_q[0] < minute_cutoff:
            minute_q.popleft()
        while hour_q and hour_q[0] < hour_cutoff:
            hour_q.popleft()

    def _write_telemetry(self, record: Dict[str, Any]) -> None:
        with self._telemetry_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def acquire(self, method: str, tool_id: str) -> Dict[str, Any]:
        now = time.time()
        policy = self._policy_for(method)
        with self._lock:
            self._prune(now, method)
            minute_count = len(self._minute_window[method])
            hour_count = len(self._hour_window[method])
            active = self._active_counts[method]

            if minute_count >= policy.max_requests_per_minute:
                self._write_telemetry(
                    {
                        "event": "blocked",
                        "reason": "rate_limit_exceeded",
                        "method": method,
                        "tool_id": tool_id,
                        "timestamp": now,
                        "policy": asdict(policy),
                    }
                )
                raise OPSECPolicyError(f"rate limit exceeded for method={method}")

            if active >= policy.max_concurrent:
                self._write_telemetry(
                    {
                        "event": "blocked",
                        "reason": "concurrency_exceeded",
                        "method": method,
                        "tool_id": tool_id,
                        "timestamp": now,
                        "policy": asdict(policy),
                    }
                )
                raise OPSECPolicyError(f"concurrency limit exceeded for method={method}")

            if hour_count >= policy.max_executions_per_hour:
                self._write_telemetry(
                    {
                        "event": "blocked",
                        "reason": "hourly_budget_exceeded",
                        "method": method,
                        "tool_id": tool_id,
                        "timestamp": now,
                        "policy": asdict(policy),
                    }
                )
                raise OPSECPolicyError(f"execution budget exceeded for method={method}")

            self._minute_window[method].append(now)
            self._hour_window[method].append(now)
            self._active_counts[method] += 1

        ticket = {"method": method, "tool_id": tool_id, "acquired_at": now}
        self._write_telemetry(
            {
                "event": "acquired",
                "method": method,
                "tool_id": tool_id,
                "timestamp": now,
                "policy": asdict(policy),
            }
        )
        return ticket

    def release(self, ticket: Dict[str, Any], status: str) -> None:
        method = str(ticket.get("method"))
        now = time.time()
        with self._lock:
            self._active_counts[method] = max(0, self._active_counts[method] - 1)
        self._write_telemetry(
            {
                "event": "released",
                "method": method,
                "tool_id": ticket.get("tool_id"),
                "status": status,
                "timestamp": now,
            }
        )


def _build_default_policies() -> Dict[str, MethodPolicy]:
    return {
        "osint": MethodPolicy("osint", max_requests_per_minute=30, max_concurrent=4, max_executions_per_hour=400),
        "recon": MethodPolicy("recon", max_requests_per_minute=20, max_concurrent=3, max_executions_per_hour=240),
        "vulnerability_scanning": MethodPolicy(
            "vulnerability_scanning",
            max_requests_per_minute=8,
            max_concurrent=2,
            max_executions_per_hour=80,
        ),
        "web_testing": MethodPolicy("web_testing", max_requests_per_minute=10, max_concurrent=2, max_executions_per_hour=100),
    }


def _load_policies_from_env() -> Dict[str, MethodPolicy]:
    raw = os.getenv("K1_OPSEC_POLICIES_JSON", "").strip()
    if not raw:
        return _build_default_policies()
    try:
        data = json.loads(raw)
    except Exception:
        return _build_default_policies()

    loaded: Dict[str, MethodPolicy] = {}
    for method, policy in (data or {}).items():
        if not isinstance(policy, dict):
            continue
        loaded[method] = MethodPolicy(
            method=method,
            max_requests_per_minute=int(policy.get("max_requests_per_minute", 10)),
            max_concurrent=int(policy.get("max_concurrent", 1)),
            max_executions_per_hour=int(policy.get("max_executions_per_hour", 100)),
        )
    return loaded or _build_default_policies()


_GLOBAL_POLICY = OPSECPolicyEngine(_load_policies_from_env())


def get_opsec_policy_engine() -> OPSECPolicyEngine:
    return _GLOBAL_POLICY
