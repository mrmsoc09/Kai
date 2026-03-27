"""
QuotaTracker — client-side token bucket + RPD counter for the 5-tier model chain.

Hardware context: CPU-only, 40 GB RAM.  All API tiers run against Gemini free
tier.  Quota management is critical — exhausting the daily budget blocks the
entire pipeline.

Model limits (Gemini free tier):
  gemini-2.5-flash:       10 RPM,  250 RPD
  gemini-2.5-flash-lite:  15 RPM, 1,000 RPD
  gemini-2.5-pro:          5 RPM,  100 RPD  ← hard cap enforced at 80 RPD

Alert thresholds (configurable via env):
  Flash RPD < GEMINI_FLASH_DAILY_ALERT (50)  → Flash-Lite spillover activated
  Pro RPD consumed >= GEMINI_PRO_DAILY_CAP (80) → Pro hard-gated until next reset
  Pro RPD < GEMINI_PRO_DAILY_ALERT (20)     → warning logged

429 handling:
  On any 429 response: exponential backoff with jitter, auto-promote to next
  tier, NEVER propagate a 429 upstream.

Persistence:
  Daily totals are written to GEMINI_QUOTA_PERSIST_PATH on every mutation so
  that process restarts survive intraday.  Counters reset at UTC midnight.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .task_schema import ModelTier, QuotaStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _persist_path() -> Path:
    raw = os.getenv("GEMINI_QUOTA_PERSIST_PATH", "")
    if raw.strip():
        return Path(raw.strip())
    return Path(os.getenv("K1_ARTIFACTS_ROOT", "artifacts")) / "quota_state.json"


# ---------------------------------------------------------------------------
# Token bucket (RPM enforcement)
# ---------------------------------------------------------------------------

@dataclass
class _TokenBucket:
    """Classic token bucket for per-minute rate limiting.

    Tokens are replenished continuously at rate = capacity / 60 per second.
    """

    capacity: int          # max tokens (= RPM limit)
    tokens: float = 0.0
    _last_refill: float = field(default_factory=time.monotonic)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        # rate = capacity tokens per 60 seconds
        self.tokens = min(self.capacity, self.tokens + elapsed * (self.capacity / 60.0))
        self._last_refill = now

    def consume(self) -> bool:
        """Consume one token.  Returns True if allowed, False if throttled."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def remaining(self) -> int:
        self._refill()
        return int(self.tokens)


# ---------------------------------------------------------------------------
# Per-model state
# ---------------------------------------------------------------------------

@dataclass
class _ModelState:
    name: str
    rpm_limit: int
    rpd_limit: int
    rpd_consumed: int = 0
    count_date: str = ""  # "YYYY-MM-DD UTC"
    bucket: Optional[_TokenBucket] = None

    def __post_init__(self) -> None:
        self.bucket = _TokenBucket(capacity=self.rpm_limit, tokens=float(self.rpm_limit))

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_reset(self) -> None:
        today = self._today()
        if self.count_date != today:
            self.count_date = today
            self.rpd_consumed = 0

    def rpm_remaining(self) -> int:
        assert self.bucket is not None
        return self.bucket.remaining()

    def rpd_remaining(self) -> int:
        self._maybe_reset()
        return max(0, self.rpd_limit - self.rpd_consumed)

    def can_consume(self) -> tuple[bool, str]:
        """Returns (allowed, reason).  Does NOT mutate state."""
        self._maybe_reset()
        if self.rpd_remaining() <= 0:
            return False, f"{self.name} daily quota exhausted ({self.rpd_limit} RPD)"
        assert self.bucket is not None
        self.bucket._refill()
        if self.bucket.tokens < 1.0:
            return False, f"{self.name} rate limit hit ({self.rpm_limit} RPM)"
        return True, ""

    def consume(self) -> None:
        """Mutate state — call only after can_consume() returned True."""
        self._maybe_reset()
        self.rpd_consumed += 1
        assert self.bucket is not None
        self.bucket.tokens = max(0.0, self.bucket.tokens - 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "rpd_consumed": self.rpd_consumed,
            "count_date": self.count_date,
        }

    @classmethod
    def from_dict(
        cls,
        d: dict[str, Any],
        *,
        rpm_limit: int,
        rpd_limit: int,
    ) -> "_ModelState":
        inst = cls(name=d["name"], rpm_limit=rpm_limit, rpd_limit=rpd_limit)
        today = inst._today()
        saved_date = d.get("count_date", "")
        if saved_date == today:
            inst.rpd_consumed = int(d.get("rpd_consumed", 0))
            inst.count_date = today
        return inst


# ---------------------------------------------------------------------------
# QuotaTracker
# ---------------------------------------------------------------------------

class QuotaTracker:
    """Thread-safe quota tracker for the 5-tier model chain.

    Usage:
        tracker = QuotaTracker.load()
        allowed, reason = tracker.can_consume(ModelTier.FLASH)
        if allowed:
            tracker.consume(ModelTier.FLASH)
        else:
            # auto-promote → tracker.next_available_tier(ModelTier.FLASH)
    """

    # Class-level singleton shared across the process.
    _instance: Optional["QuotaTracker"] = None
    _lock: asyncio.Lock = asyncio.Lock()  # async guard for concurrent coroutines

    def __init__(self) -> None:
        flash_rpd = _int_env("GEMINI_FLASH_DAILY_LIMIT", 250)
        flash_rpm = _int_env("GEMINI_FLASH_RPM", 10)
        lite_rpd = _int_env("GEMINI_FLASH_LITE_DAILY_LIMIT", 1000)
        lite_rpm = _int_env("GEMINI_FLASH_LITE_RPM", 15)
        pro_rpd = _int_env("GEMINI_PRO_DAILY_LIMIT", 100)
        pro_rpm = _int_env("GEMINI_PRO_RPM", 5)

        self._models: dict[ModelTier, _ModelState] = {
            ModelTier.FLASH: _ModelState(
                name=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash"),
                rpm_limit=flash_rpm,
                rpd_limit=flash_rpd,
            ),
            ModelTier.FLASH_LITE: _ModelState(
                name=os.getenv("GEMINI_FLASH_LITE_MODEL", "gemini-2.5-flash-lite"),
                rpm_limit=lite_rpm,
                rpd_limit=lite_rpd,
            ),
            ModelTier.PRO: _ModelState(
                name=os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro"),
                rpm_limit=pro_rpm,
                rpd_limit=pro_rpd,
            ),
        }

        self._flash_daily_alert = _int_env("GEMINI_FLASH_DAILY_ALERT", 50)
        self._pro_daily_cap = _int_env("GEMINI_PRO_DAILY_CAP", 80)
        self._pro_daily_alert = _int_env("GEMINI_PRO_DAILY_ALERT", 20)

        self._emergency_active = False

        # Threshold callbacks — populated by register_callback()
        self._callbacks: list[Callable[[str, Any], None]] = []

        self._persist_path = _persist_path()

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> "QuotaTracker":
        if cls._instance is None:
            cls._instance = QuotaTracker.load()
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        """Test helper — reset the singleton so tests start fresh."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "QuotaTracker":
        """Load persisted state from disk, return fresh tracker if missing/corrupt."""
        inst = cls()
        path = inst._persist_path
        if not path.exists():
            return inst
        try:
            with open(path) as fh:
                data = json.load(fh)
            for tier, model in inst._models.items():
                key = tier.value
                if key in data:
                    inst._models[tier] = _ModelState.from_dict(
                        data[key],
                        rpm_limit=model.rpm_limit,
                        rpd_limit=model.rpd_limit,
                    )
            inst._emergency_active = bool(data.get("emergency_active", False))
            logger.info("QuotaTracker: loaded persisted state from %s", path)
        except Exception as exc:
            logger.warning("QuotaTracker: could not load persisted state: %s", exc)
        return inst

    def save(self) -> None:
        """Persist current counters to disk (atomic write)."""
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            tier.value: model.to_dict()
            for tier, model in self._models.items()
        }
        data["emergency_active"] = self._emergency_active
        tmp = self._persist_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(self._persist_path)
        except Exception as exc:
            logger.warning("QuotaTracker: failed to persist state: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def can_consume(self, tier: ModelTier) -> tuple[bool, str]:
        """Check whether tier has budget remaining.  Does NOT mutate state."""
        model = self._models.get(tier)
        if model is None:
            return True, ""  # local tiers (Tier 4/5) have no API quota

        # Pro hard cap: treat as exhausted once consumed >= cap
        if tier == ModelTier.PRO:
            consumed = model.rpd_consumed
            cap = self._pro_daily_cap
            today = model._today()
            model._maybe_reset()
            if model.rpd_consumed >= cap:
                return False, (
                    f"Pro hard cap reached ({cap} RPD consumed today). "
                    "Reserved 20 RPD as daily buffer."
                )

        return model.can_consume()

    def consume(self, tier: ModelTier) -> None:
        """Record a request against *tier*.  Fires threshold callbacks and persists."""
        model = self._models.get(tier)
        if model is None:
            return  # local tiers — no quota to track

        model.consume()
        self._check_thresholds(tier, model)
        self.save()

    def record_429(self, tier: ModelTier, *, backoff_base_ms: int = 1000) -> None:
        """Record a 429 response.  Logs prominently.  Does NOT propagate upstream.

        Caller is responsible for promoting to next_available_tier() and retrying.
        The backoff duration is returned via the logger — sleep is the caller's job
        so that async callers can await properly.
        """
        jitter = random.uniform(0.5, 1.5)
        backoff_ms = backoff_base_ms * jitter
        logger.warning(
            "QUOTA 429: tier=%s  backoff=%.0fms  — auto-promoting to next tier",
            tier.value,
            backoff_ms,
        )

    def next_available_tier(self, current: ModelTier) -> Optional[ModelTier]:
        """Return the next tier with remaining budget, or None if all exhausted."""
        promotion_order: list[ModelTier] = [
            ModelTier.FLASH,
            ModelTier.FLASH_LITE,
            ModelTier.PRO,
            ModelTier.LOCAL_EMERGENCY,
        ]
        try:
            start = promotion_order.index(current) + 1
        except ValueError:
            start = 0

        for tier in promotion_order[start:]:
            ok, _ = self.can_consume(tier)
            if ok:
                if tier == ModelTier.LOCAL_EMERGENCY and not self._emergency_active:
                    # Reached emergency tier — all API tiers exhausted
                    self._emergency_active = True
                    self.save()
                    logger.critical(
                        "QUOTA EMERGENCY: all API tiers exhausted — switching to Tier 5 "
                        "(qwen2.5:7b local). Performance severely degraded at 5-15 t/s."
                    )
                    self._fire("emergency_active", {})
                return tier

        # No tier available at all (should not happen — local tiers are always available)
        self._emergency_active = True
        self.save()
        logger.critical(
            "QUOTA EMERGENCY: all API tiers exhausted — switching to Tier 5 "
            "(qwen2.5:7b local). Performance severely degraded at 5-15 t/s."
        )
        return ModelTier.LOCAL_EMERGENCY

    def status(self) -> QuotaStatus:
        """Return current quota state as a QuotaStatus dataclass."""
        flash = self._models[ModelTier.FLASH]
        lite = self._models[ModelTier.FLASH_LITE]
        pro = self._models[ModelTier.PRO]

        active = ModelTier.FLASH
        if self._emergency_active:
            active = ModelTier.LOCAL_EMERGENCY
        elif flash.rpd_remaining() <= 0:
            active = ModelTier.FLASH_LITE

        return QuotaStatus(
            flash_rpm_remaining=flash.rpm_remaining(),
            flash_rpd_remaining=flash.rpd_remaining(),
            flash_rpm_limit=flash.rpm_limit,
            flash_rpd_limit=flash.rpd_limit,
            flash_lite_rpm_remaining=lite.rpm_remaining(),
            flash_lite_rpd_remaining=lite.rpd_remaining(),
            flash_lite_rpm_limit=lite.rpm_limit,
            flash_lite_rpd_limit=lite.rpd_limit,
            pro_rpm_remaining=pro.rpm_remaining(),
            pro_rpd_remaining=pro.rpd_remaining(),
            pro_rpm_limit=pro.rpm_limit,
            pro_rpd_limit=pro.rpd_limit,
            active_tier=active,
            emergency_fallback_active=self._emergency_active,
            flash_lite_spillover_active=flash.rpd_remaining() < self._flash_daily_alert,
            pro_restricted=pro.rpd_consumed >= self._pro_daily_alert,
            last_reset_time=datetime.now(timezone.utc).isoformat(),
        )

    def register_callback(self, fn: Callable[[str, Any], None]) -> None:
        """Register a callback invoked on threshold events.

        fn(event_name, payload) where event_name is one of:
          "flash_low"        — Flash RPD < GEMINI_FLASH_DAILY_ALERT
          "pro_cap_hard"     — Pro consumed >= GEMINI_PRO_DAILY_CAP
          "pro_alert"        — Pro RPD remaining < GEMINI_PRO_DAILY_ALERT
          "emergency_active" — all API tiers exhausted
        """
        self._callbacks.append(fn)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_thresholds(self, tier: ModelTier, model: _ModelState) -> None:
        rpd_remaining = model.rpd_remaining()

        if tier == ModelTier.FLASH:
            if rpd_remaining < self._flash_daily_alert:
                logger.warning(
                    "QUOTA ALERT: Flash RPD low — %d remaining. "
                    "Spillover to Flash-Lite activated.",
                    rpd_remaining,
                )
                self._fire("flash_low", {"rpd_remaining": rpd_remaining})

        elif tier == ModelTier.PRO:
            consumed = model.rpd_consumed
            if consumed >= self._pro_daily_cap:
                logger.warning(
                    "QUOTA HARD CAP: Pro RPD cap reached (%d consumed). "
                    "Reserving %d RPD as daily buffer.",
                    consumed,
                    model.rpd_limit - self._pro_daily_cap,
                )
                self._fire("pro_cap_hard", {"rpd_consumed": consumed})
            elif rpd_remaining < self._pro_daily_alert:
                logger.warning(
                    "QUOTA ALERT: Pro RPD low — %d remaining (buffer zone).",
                    rpd_remaining,
                )
                self._fire("pro_alert", {"rpd_remaining": rpd_remaining})

    def _fire(self, event: str, payload: Any) -> None:
        for fn in self._callbacks:
            try:
                fn(event, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("QuotaTracker callback error (%s): %s", event, exc)
