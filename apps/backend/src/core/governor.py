from __future__ import annotations

import asyncio
import json
import os
import random
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# Targeted tools for rate-limit flag injection
_TARGET_TOOLS = {"nuclei", "ffuf", "subfinder", "msfconsole"}
_WAF_STATUS_CODES = {403, 429}
_STATUS_RE = re.compile(r"\b(403|429)\b")


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_binary(command: list[str]) -> str:
    if not command:
        return ""
    return os.path.basename(str(command[0]).strip()).lower()


@dataclass(slots=True)
class QueueDecision:
    queued: bool
    reason: str
    delay_seconds: float
    heat_level: float
    paused: bool


@dataclass(slots=True)
class StealthExecutionContext:
    command: list[str]
    binary: str
    delay_seconds: float
    queue_decision: QueueDecision
    overrides: dict[str, Any]
    acquired: bool


class StealthGovernor:
    """
    K1 Stealth Governor (Stage 20).
    Manages global concurrency, dynamic jitter, and WAF evasion.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StealthGovernor, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._config = self._load_config()
        self._global_limit = max(
            1,
            _to_int(
                os.getenv("K1_GOVERNOR_GLOBAL_CONCURRENCY"),
                _to_int(self._config.get("global_concurrency_limit"), 4),
            ),
        )
        self._heat_queue_threshold = _clamp(
            _to_float(
                os.getenv("K1_GOVERNOR_QUEUE_HEAT_THRESHOLD"),
                _to_float(self._config.get("queue_heat_threshold"), 0.75),
            )
        )
        self._pause_seconds = max(
            1,
            _to_int(
                os.getenv("K1_GOVERNOR_AUTOPAUSE_SECONDS"),
                _to_int(self._config.get("autopause_seconds"), 600), # 10 minutes default
            ),
        )
        
        # Gaussian Jitter Configuration
        self._jitter_mean = max(
            0.0,
            _to_float(os.getenv("K1_GOVERNOR_JITTER_MEAN"), _to_float(self._config.get("jitter_mean"), 0.20)),
        )
        self._jitter_std = max(
            0.0,
            _to_float(os.getenv("K1_GOVERNOR_JITTER_STD"), _to_float(self._config.get("jitter_std"), 0.08)),
        )
        self._jitter_min = max(
            0.0,
            _to_float(os.getenv("K1_GOVERNOR_JITTER_MIN"), _to_float(self._config.get("jitter_min"), 0.01)),
        )
        self._jitter_max = max(
            self._jitter_min,
            _to_float(os.getenv("K1_GOVERNOR_JITTER_MAX"), _to_float(self._config.get("jitter_max"), 3.0)),
        )

        self._rng = random.Random()
        self._semaphore = threading.BoundedSemaphore(self._global_limit)
        self._state_lock = threading.Lock()
        self._active_count = 0
        self._consecutive_waf_hits = 0
        self._pause_until_monotonic = 0.0
        self._target_profiles: dict[str, dict[str, Any]] = {}
        self._initialized = True

    @staticmethod
    def _load_config() -> dict[str, Any]:
        path = os.getenv("K1_GOVERNOR_CONFIG_PATH", "config/tools/stealth_defaults.json")
        cfg_path = Path(path).expanduser().resolve()
        if not cfg_path.exists():
            return {}
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _is_cloudflare_target(self, target: str | None, metadata: Mapping[str, Any] | None) -> bool:
        """Heuristic to detect Cloudflare targets for 5x jitter increase."""
        target_str = str(target or "").lower()
        md = metadata or {}
        if "cloudflare" in target_str:
            return True
        if "cloudflare" in str(md.get("waf_vendor", "")).lower():
            return True
        return False

    def get_stealth_delay(self, *, target: str | None = None, metadata: Mapping[str, Any] | None = None) -> float:
        """Returns randomized Gaussian jitter delay."""
        delay = max(self._jitter_min, self._rng.gauss(self._jitter_mean, self._jitter_std))
        delay = min(self._jitter_max, delay)
        
        if self._is_cloudflare_target(target, metadata):
            delay *= 5.0 # 5x increase for Cloudflare
            
        return round(delay, 4)

    def get_queue_decision(self, *, target: str | None = None, metadata: Mapping[str, Any] | None = None) -> QueueDecision:
        """Determines if a task should be executed or queued based on 'Heat Level'."""
        with self._state_lock:
            now = time.monotonic()
            paused = now < self._pause_until_monotonic
            active_ratio = self._active_count / self._global_limit
            heat = max(active_ratio, 1.0 if paused else 0.0)

        if paused:
            return QueueDecision(True, "autopause_active", self._pause_until_monotonic - now, heat, True)
        
        if heat >= self._heat_queue_threshold:
            return QueueDecision(True, "heat_level_threshold", self.get_stealth_delay(target=target), heat, False)
            
        return QueueDecision(False, "healthy", 0.0, heat, False)

    def acquire_slot(self) -> bool:
        if self._semaphore.acquire(blocking=True):
            with self._state_lock:
                self._active_count += 1
            return True
        return False

    def release_slot(self) -> None:
        with self._state_lock:
            self._active_count = max(0, self._active_count - 1)
        self._semaphore.release()

    def register_http_status(self, status_code: int, target: str | None = None) -> None:
        """WAF Detection Sensor: Auto-Pause if 5+ consecutive 403/429 hits."""
        with self._state_lock:
            if status_code in _WAF_STATUS_CODES:
                self._consecutive_waf_hits += 1
            else:
                self._consecutive_waf_hits = 0
            
            if self._consecutive_waf_hits >= 5:
                self._pause_until_monotonic = time.monotonic() + self._pause_seconds
                self._log_stealth_critical(target)

    def _log_stealth_critical(self, target: str | None):
        alert = {
            "event": "STEALTH_CRITICAL",
            "target": target,
            "reason": "consecutive_waf_blocks",
            "pause_duration": self._pause_seconds,
            "timestamp": time.time()
        }
        path = Path("artifacts/stealth/alerts.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(alert) + "\n")

    def apply_tool_overrides(self, command: list[str], band: str = "medium") -> list[str]:
        """Injects tool-specific rate-limiting flags."""
        cmd = list(command)
        binary = _normalize_binary(cmd)
        if binary not in _TARGET_TOOLS:
            return cmd

        tools_cfg = self._config.get("tools", {})
        tool_cfg = tools_cfg.get(binary, {})

        if binary == "nuclei":
            rate = tool_cfg.get("rate_limit", {}).get(band, 6)
            cmd.extend(["-rate-limit", str(rate)])
        elif binary == "ffuf":
            threads = tool_cfg.get("threads", {}).get(band, 5)
            cmd.extend(["-t", str(threads)])
        elif binary == "subfinder":
            threads = tool_cfg.get("threads", {}).get(band, 10)
            cmd.extend(["-t", str(threads)])
        elif binary == "msfconsole":
            cmd.append("-q")

        return cmd


def get_governor() -> StealthGovernor:
    return StealthGovernor()


class StealthWrapper:
    """Interceptors for system calls to enforce stealth governance."""

    @staticmethod
    def prepare_sync_command(command: list[str], target: str, metadata: dict = None) -> StealthExecutionContext:
        gov = get_governor()
        decision = gov.get_queue_decision(target=target, metadata=metadata)
        
        if decision.queued:
            time.sleep(decision.delay_seconds)
            
        gov.acquire_slot()
        delay = gov.get_stealth_delay(target=target, metadata=metadata)
        time.sleep(delay)
        
        # Apply overrides
        heat = gov.get_queue_decision().heat_level
        band = "high" if heat > 0.8 else ("medium" if heat > 0.4 else "low")
        adjusted_cmd = gov.apply_tool_overrides(command, band=band)
        
        return StealthExecutionContext(
            command=adjusted_cmd,
            binary=_normalize_binary(adjusted_cmd),
            delay_seconds=delay,
            queue_decision=decision,
            overrides={},
            acquired=True
        )

    @staticmethod
    def finalize_context(context: StealthExecutionContext, stdout: str = "", stderr: str = ""):
        gov = get_governor()
        # Scan output for WAF hits
        for code in [403, 429]:
            if str(code) in stdout or str(code) in stderr:
                gov.register_http_status(code)
        
        if context.acquired:
            gov.release_slot()
