"""
Task and result schema for GeminiOrchestrator.

These dataclasses flow through the entire orchestration pipeline:
  OrchestrationTask → model_router → provider chain → OrchestrationResult
  QuotaStatus       → quota_tracker → /api/v1/orchestration/quota
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ModelTier(str, Enum):
    """Five-tier model routing strategy.

    Hardware context: CPU-only, 40 GB RAM, no discrete GPU.
    Local inference runs at 5-15 t/s — acceptable for routing decisions only.
    Tiers 4 and 5 must NEVER be used for sustained agentic pipeline execution.

    Future: Tiers 4-5 will be replaced by a custom KAISON AI agent fine-tuned
    on accumulated platform hunt data, optimised for offensive security reasoning
    and BBP workflow orchestration. Swapping any tier requires only a config change.
    """

    FLASH = "flash"                      # Tier 1 PRIMARY:      gemini-2.5-flash
    FLASH_LITE = "flash_lite"            # Tier 2 HIGH_VOLUME:  gemini-2.5-flash-lite
    PRO = "pro"                          # Tier 3 COMPLEX:      gemini-2.5-pro
    LOCAL_ROUTING = "local_routing"      # Tier 4 ROUTING_ONLY: gemma3:8b via Ollama
    LOCAL_EMERGENCY = "local_emergency"  # Tier 5 EMERGENCY:    qwen2.5:7b via Ollama


class TaskComplexity(str, Enum):
    """Task complexity classification produced by model_router.

    Maps directly to the dispatch tier:
      LOW    → Flash-Lite (Tier 2) — volume tasks, classification, simple recon
      MEDIUM → Flash     (Tier 1) — standard agentic work, tool dispatch, BBP pipeline
      HIGH   → Pro       (Tier 3) — complex multi-hop chains, report generation,
                                    final vuln validation — EXPLICIT classification only
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    QUOTA_BLOCKED = "quota_blocked"


@dataclass
class OrchestrationTask:
    """Task submitted to GeminiOrchestrator for execution."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: str = ""
    # Examples: "recon", "analysis", "validation", "report"

    instruction: str = ""
    # Natural language task description fed to the selected model tier.

    context: dict[str, Any] = field(default_factory=dict)
    # Structured context injected alongside the instruction.

    tools_available: list[str] = field(default_factory=list)
    # Tool names from ToolRegistry that this task may invoke.
    # Ignored for routing-only tiers (Tier 4).

    complexity_hint: Optional[TaskComplexity] = None
    # Explicit override. When set to HIGH, forces dispatch to Tier 3 (Pro).
    # None → auto-classified by model_router.

    timeout_seconds: int = 120
    priority: int = 5  # 1 = highest, 10 = lowest

    session_id: Optional[str] = None


@dataclass
class OrchestrationResult:
    """Result returned from GeminiOrchestrator after task execution."""

    task_id: str
    status: TaskStatus
    output: Optional[str] = None
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    model_used: Optional[str] = None
    tier_used: Optional[ModelTier] = None
    duration_ms: float = 0.0
    quota_consumed: dict[str, int] = field(default_factory=dict)
    # {model_name: request_count} e.g. {"gemini-2.5-flash": 1}

    session_id: Optional[str] = None
    error: Optional[str] = None

    vision_observations: list[dict[str, Any]] = field(default_factory=list)
    # ScreenVisionAgent observations injected mid-task.
    # Each entry: {"screenshot_path": ..., "verdict": ..., "confidence": ...}


@dataclass
class QuotaStatus:
    """Per-model quota state. Surfaced via GET /api/v1/orchestration/quota.

    Limit reference (Gemini free tier):
      gemini-2.5-flash:       10 RPM,  250 RPD
      gemini-2.5-flash-lite:  15 RPM, 1000 RPD
      gemini-2.5-pro:          5 RPM,  100 RPD (hard cap at 80 RPD consumed)
    """

    # Tier 1 — Flash
    flash_rpm_remaining: int = 10
    flash_rpd_remaining: int = 250
    flash_rpm_limit: int = 10
    flash_rpd_limit: int = 250

    # Tier 2 — Flash-Lite
    flash_lite_rpm_remaining: int = 15
    flash_lite_rpd_remaining: int = 1000
    flash_lite_rpm_limit: int = 15
    flash_lite_rpd_limit: int = 1000

    # Tier 3 — Pro
    pro_rpm_remaining: int = 5
    pro_rpd_remaining: int = 100
    pro_rpm_limit: int = 5
    pro_rpd_limit: int = 100

    active_tier: ModelTier = ModelTier.FLASH
    emergency_fallback_active: bool = False
    # True when all API tiers exhausted or network unavailable.

    last_reset_time: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    flash_lite_spillover_active: bool = False
    # True when Flash RPD remaining < GEMINI_FLASH_DAILY_ALERT (default 50).
    # Signals that new medium-complexity tasks should route to Flash-Lite.

    pro_restricted: bool = False
    # True when Pro RPD remaining < GEMINI_PRO_DAILY_ALERT (default 20).
    # Hard gate: no new HIGH tasks dispatched to Pro until next reset.

    def to_dict(self) -> dict[str, Any]:
        return {
            "flash": {
                "rpm_remaining": self.flash_rpm_remaining,
                "rpd_remaining": self.flash_rpd_remaining,
                "rpm_limit": self.flash_rpm_limit,
                "rpd_limit": self.flash_rpd_limit,
            },
            "flash_lite": {
                "rpm_remaining": self.flash_lite_rpm_remaining,
                "rpd_remaining": self.flash_lite_rpd_remaining,
                "rpm_limit": self.flash_lite_rpm_limit,
                "rpd_limit": self.flash_lite_rpd_limit,
            },
            "pro": {
                "rpm_remaining": self.pro_rpm_remaining,
                "rpd_remaining": self.pro_rpd_remaining,
                "rpm_limit": self.pro_rpm_limit,
                "rpd_limit": self.pro_rpd_limit,
            },
            "active_tier": self.active_tier.value,
            "emergency_fallback_active": self.emergency_fallback_active,
            "flash_lite_spillover_active": self.flash_lite_spillover_active,
            "pro_restricted": self.pro_restricted,
            "last_reset_time": self.last_reset_time,
        }
