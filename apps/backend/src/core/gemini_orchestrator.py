"""
GeminiOrchestrator — singleton orchestration hub for the 5-tier LLM routing stack.

FIVE-TIER MODEL ARCHITECTURE
─────────────────────────────────────────────────────────────────────────────
  TIER 1  PRIMARY         gemini-2.5-flash         10 RPM / 250 RPD
           All agentic execution, tool dispatch, BBP pipeline
  TIER 2  HIGH_VOLUME     gemini-2.5-flash-lite    15 RPM / 1,000 RPD
           High-volume recon tasks, classification, quota spillover from Tier 1
           Auto-promotes when Flash daily quota drops below GEMINI_FLASH_DAILY_ALERT
  TIER 3  COMPLEX         gemini-2.5-pro           5 RPM / 100 RPD (hard cap 80)
           Report generation, CVE triage, complex multi-hop chains, final validation
           Dispatched ONLY for explicit COMPLEXITY_HIGH classification
  TIER 4  LOCAL_ROUTING   gemma3:8b via Ollama     ~5-15 t/s on CPU
           Routing and task classification decisions ONLY.
           NEVER dispatches tool calls.  NEVER executes agentic tasks.
           Uses Gemini CLI native local model routing.
  TIER 5  LOCAL_EMERGENCY qwen2.5:7b Q4_K_M        ~5-15 t/s on CPU
           Full offline fallback only — all API tiers exhausted or network down.
           Tool-call capable via Ollama.  NOT suitable for sustained pipeline use.
           Activation logged prominently.

HARDWARE CONTEXT
─────────────────────────────────────────────────────────────────────────────
  Lenovo V15 G2 IJL — CPU-only, 40 GB RAM, 1 TB NVMe, no discrete GPU.
  Local inference runs at 5-15 t/s.  Acceptable for routing/classification.
  NOT acceptable for sustained agentic pipeline execution.

FUTURE ARCHITECTURE NOTE
─────────────────────────────────────────────────────────────────────────────
  Tiers 4-5 will be replaced by a custom KAISON AI agent fine-tuned on
  accumulated platform hunt data, optimised for offensive security reasoning
  and BBP workflow orchestration.  GeminiOrchestrator is model-agnostic by
  design — swapping any tier requires only a config change.

Public interface:
  get_gemini_orchestrator()    → singleton
  initialize_gemini_orchestrator() → called once from main.py lifespan startup
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from typing import Any, Optional

from .governance_evidence_integration import (
    get_governance_evidence_integration,
    ActionType,
    ActionCriticality,
    FindingDetectionEvent,
)
from .finding_status_tracker import get_finding_status_tracker, FindingStatusEnum
from .background_evidence_dispatcher import get_background_evidence_dispatcher

logger = logging.getLogger(__name__)

_orchestrator: "GeminiOrchestrator | None" = None

# Exponential backoff constants for 429 handling
_BACKOFF_BASE_MS = 1000
_BACKOFF_MAX_MS = 32000
_BACKOFF_JITTER = 0.3


class GeminiOrchestrator:
    """5-tier LLM routing hub.

    Wraps LLMProviderFactory, integrates QuotaTracker, ModelRouter, optional
    ScreenVisionAgent, and a ToolRegistry dispatch stub.
    """

    def __init__(self) -> None:
        from .llm_providers import LLMProviderFactory
        from .quota_tracker import QuotaTracker
        from .model_router import ModelRouter

        self.factory = LLMProviderFactory()
        self.factory.initialize_from_env()

        self.quota = QuotaTracker.get()
        self.router = ModelRouter()

        self._primary = os.getenv("K1_PRIMARY_LLM_PROVIDER", "gemini")
        self._routing = os.getenv("K1_ROUTING_LLM_PROVIDER", "gemma")
        self._fallbacks = [
            f.strip()
            for f in os.getenv(
                "K1_FALLBACK_LLM_PROVIDERS", "gemini-flash-lite,gemini-pro,ollama"
            ).split(",")
            if f.strip()
        ]

        # Session counter (informational)
        self._session_count: int = 0
        self._lock = asyncio.Lock()

        # Vision agent (optional — wired when K1_VISION_ANALYSIS_ENABLED=true)
        self._vision_agent: Optional[Any] = None
        self._init_vision_agent()

        # Initialize governance & evidence integration
        self._governance_integration: Optional[Any] = None

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _init_vision_agent(self) -> None:
        if os.getenv("K1_VISION_ANALYSIS_ENABLED", "false").strip().lower() not in {
            "1", "true", "yes", "on"
        }:
            return
        try:
            from .vision_validation_service import VisionValidationService
            self._vision_agent = VisionValidationService()
            logger.info("GeminiOrchestrator: ScreenVisionAgent wired")
        except Exception as exc:
            logger.warning("GeminiOrchestrator: ScreenVisionAgent init failed: %s", exc)

    async def _init_governance_integration(self) -> None:
        """Initialize governance and evidence integration."""
        try:
            self._governance_integration = await get_governance_evidence_integration()
            logger.info("GeminiOrchestrator: Governance & Evidence integration ready")
        except Exception as exc:
            logger.warning(
                "GeminiOrchestrator: Governance & Evidence integration failed: %s",
                exc
            )

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        instruction: str,
        *,
        context: dict[str, Any] | None = None,
        tools: list[str] | None = None,
        complexity_hint: str | None = None,
        timeout_seconds: int = 120,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute an instruction through the 5-tier routing stack.

        Returns a dict compatible with OrchestrationResult.to_dict() semantics.
        """
        from .task_schema import ModelTier, OrchestrationResult, OrchestrationTask, TaskComplexity, TaskStatus

        hint: Optional[TaskComplexity] = None
        if complexity_hint:
            try:
                hint = TaskComplexity(complexity_hint.lower())
            except ValueError:
                pass

        start = time.monotonic()
        self._session_count += 1

        # 1. Classify and determine target tier
        quota_status = self.quota.status()
        tier = await self.router.route(
            instruction, hint=hint, quota_status=quota_status
        )

        # 2. Attempt execution with backoff + tier promotion on failure
        result_text: Optional[str] = None
        model_used: Optional[str] = None
        tier_used: Optional[ModelTier] = None
        error: Optional[str] = None
        tool_calls_made: list[dict[str, Any]] = []
        vision_obs: list[dict[str, Any]] = []

        backoff_ms = _BACKOFF_BASE_MS

        for attempt in range(5):
            ok, reason = self.quota.can_consume(tier)
            if not ok:
                logger.warning(
                    "GeminiOrchestrator: quota blocked tier=%s reason=%s — promoting",
                    tier.value, reason,
                )
                next_tier = self.quota.next_available_tier(tier)
                if next_tier is None or next_tier == tier:
                    error = f"All tiers quota-blocked: {reason}"
                    break
                tier = next_tier
                continue

            try:
                provider = self.factory.get_provider()
                messages = [{"role": "user", "content": instruction}]
                if context:
                    messages[0]["content"] += f"\n\nContext: {context}"

                # Check for governance gates on HIGH/CRITICAL actions
                if tools:
                    # Lazy-initialize governance integration on first use
                    if self._governance_integration is None:
                        try:
                            await self._init_governance_integration()
                        except Exception as exc:
                            logger.warning("Failed to initialize governance integration: %s", exc)

                    if self._governance_integration:
                        # Determine criticality from context
                        criticality = ActionCriticality.MEDIUM  # default
                        if context and "criticality" in context:
                            criticality_str = context["criticality"].lower()
                            if criticality_str in ("high", "critical"):
                                criticality = ActionCriticality[criticality_str.upper()]

                        # Request approval for HIGH/CRITICAL
                        if criticality in (ActionCriticality.HIGH, ActionCriticality.CRITICAL):
                            action_id = f"{session_id}_tool_execution"
                            approved = await self._governance_integration.request_action_approval(
                                action_id=action_id,
                                action_type=ActionType.TOOL_EXECUTION,
                                criticality=criticality,
                                description=f"Execute tools: {', '.join(tools)}",
                                context=context,
                            )

                            if not approved:
                                logger.error(f"Tool execution BLOCKED: {action_id}")
                                return {
                                    "task_id": session_id,
                                    "status": "BLOCKED_PENDING_APPROVAL",
                                    "output": f"Execution blocked pending HiL approval",
                                    "tool_calls_made": [],
                                }

                # Tool dispatch: invoke stub for each requested tool
                dispatched_tools: list[dict[str, Any]] = []
                if tools:
                    for tool_name in tools:
                        tool_result = await self._dispatch_tool(tool_name, {"instruction": instruction})
                        dispatched_tools.append({"tool": tool_name, "result": tool_result})

                response = await provider.complete(messages)
                self.quota.consume(tier)

                result_text = response.text
                model_used = response.model
                tier_used = tier
                tool_calls_made = dispatched_tools

                # Vision injection: if vision agent available, observe post-execution
                if self._vision_agent is not None:
                    try:
                        obs = await self._observe_vision(instruction, session_id)
                        vision_obs = obs
                    except Exception as vexc:
                        logger.debug("Vision observation failed (non-fatal): %s", vexc)

                break  # success

            except RuntimeError as exc:
                msg = str(exc)
                if "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
                    self.quota.record_429(tier, backoff_base_ms=backoff_ms)
                    jitter = 1.0 + random.uniform(-_BACKOFF_JITTER, _BACKOFF_JITTER)
                    sleep_s = min(backoff_ms * jitter, _BACKOFF_MAX_MS) / 1000.0
                    await asyncio.sleep(sleep_s)
                    backoff_ms = min(backoff_ms * 2, _BACKOFF_MAX_MS)
                    next_tier = self.quota.next_available_tier(tier)
                    if next_tier is None or next_tier == tier:
                        error = f"All tiers 429: {msg}"
                        break
                    tier = next_tier
                else:
                    error = msg
                    break
            except Exception as exc:
                error = str(exc)
                break

        duration_ms = (time.monotonic() - start) * 1000
        status = TaskStatus.COMPLETED if result_text is not None else TaskStatus.FAILED

        if tier_used == ModelTier.LOCAL_EMERGENCY:
            logger.critical(
                "⚠️  EMERGENCY FALLBACK ACTIVE ⚠️  — executing via qwen2.5:7b local "
                "(Tier 5).  Performance severely degraded at 5-15 t/s on CPU-only hardware."
            )

        if os.getenv("GEMINI_LOG_SESSIONS", "true").strip().lower() in {"1", "true", "yes", "on"}:
            logger.info(
                "GeminiOrchestrator: session=%s tier=%s model=%s duration=%.0fms status=%s",
                session_id,
                tier_used.value if tier_used else "none",
                model_used,
                duration_ms,
                status.value,
            )

        return {
            "task_id": session_id,
            "status": status.value,
            "output": result_text,
            "model_used": model_used,
            "tier_used": tier_used.value if tier_used else None,
            "duration_ms": duration_ms,
            "tool_calls_made": tool_calls_made,
            "vision_observations": vision_obs,
            "error": error,
        }

    # ------------------------------------------------------------------
    # Vision integration
    # ------------------------------------------------------------------

    async def _observe_vision(
        self, instruction: str, session_id: str | None
    ) -> list[dict[str, Any]]:
        """Invoke ScreenVisionAgent.observe() mid-task and return observations."""
        if self._vision_agent is None:
            return []
        # VisionValidationService has an async validate_triggered_findings method.
        # We inject the current instruction as a pseudo-finding for observation.
        pseudo_findings = [
            {
                "finding_id": session_id or "orch-obs",
                "title": instruction[:100],
                "url": "",
                "payload": "",
            }
        ]
        try:
            results = await self._vision_agent.validate_triggered_findings(pseudo_findings)
            return [
                {
                    "finding_id": r.finding_id,
                    "validated": r.validated,
                    "suppressed": r.suppressed,
                    "requires_human_review": r.requires_human_review,
                    "analysis": r.analysis,
                }
                for r in results
            ]
        except Exception as exc:
            logger.debug("_observe_vision: %s", exc)
            return []

    async def capture_evidence_on_finding(
        self,
        task_id: str,
        target_url: str,
        vulnerability_type: str,
        severity: str,
        tool_name: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Trigger evidence capture as NON-BLOCKING background task.

        CRITICAL: This method returns IMMEDIATELY and does NOT wait for
        evidence collection to complete. The scanner loop continues while
        evidence is being collected in the background.

        Returns:
            Dict with background_task_id and finding_id for tracking
        """
        if not self._governance_integration:
            return {}

        # Get status tracker (lazy init if needed)
        status_tracker = await get_finding_status_tracker()

        # Create finding record in DETECTED state
        finding_status = await status_tracker.create_finding(
            task_id=task_id,
            target_url=target_url,
            vulnerability_type=vulnerability_type,
            severity=severity,
            tool_name=tool_name,
            metadata=evidence,
        )

        logger.info(f"📍 Finding created: {finding_status.finding_id}")

        # Get background dispatcher
        dispatcher = get_background_evidence_dispatcher()

        # Define evidence collection function
        async def _collect_evidence():
            """Async function to collect evidence in background."""
            event = FindingDetectionEvent(
                task_id=task_id,
                finding_id=finding_status.finding_id,
                target_url=target_url,
                vulnerability_type=vulnerability_type,
                severity=severity,
                tool_name=tool_name,
                evidence=evidence,
            )

            result = await self._governance_integration.on_vulnerability_detected(event)
            logger.info(f"Evidence collection result for {finding_status.finding_id}: {result}")
            return result

        # Dispatch to background (NON-BLOCKING)
        background_task_id = await dispatcher.dispatch_evidence_collection(
            finding_id=finding_status.finding_id,
            task_id=task_id,
            target_url=target_url,
            vulnerability_type=vulnerability_type,
            severity=severity,
            tool_name=tool_name,
            evidence=evidence,
            evidence_fn=_collect_evidence,
            status_tracker=status_tracker,
        )

        # Return immediately (scanner loop can continue)
        return {
            "finding_id": finding_status.finding_id,
            "background_task_id": background_task_id,
            "status": "dispatched",
            "message": "Evidence collection started in background (non-blocking)",
        }

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def _dispatch_tool(
        self,
        tool_name: str,
        inputs: dict[str, Any],
        *,
        program_id: str | None = None,
        user_id: str | None = None,
        workflow_id: str | None = None,
        certificate_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch tool_name through ToolRegistry → Celery worker.

        Execution contract:
          1. Look up tool_name in the global ToolRegistry (tools.py).
          2. Validate inputs against the tool's declared parameter schema.
          3. Check autonomy tier — Band 2/3 tools require human approval;
             returned as {"status": "pending_approval"} without enqueuing.
          4. Enqueue Band 0/1 tools via tool_runner (Celery) in a thread
             executor so the event loop is never blocked.
          5. All errors are caught and returned as {"status": "error"} —
             a failed tool call MUST NOT kill the active orchestration session.
          6. Every dispatch (queued or error) is written to the audit log.
        """
        import time as _time
        from fastapi import HTTPException as _HTTPException
        from .tools import get_registry, initialize_default_tools, ToolAutonomyTier

        start_ms = _time.monotonic() * 1000

        def _audit(status: str, detail: str = "") -> None:
            logger.info(
                "TOOL_DISPATCH audit: tool=%r program_id=%r user_id=%r status=%s%s",
                tool_name,
                program_id,
                user_id,
                status,
                f" {detail}" if detail else "",
            )

        # 1. Ensure default tools are loaded (idempotent).
        try:
            initialize_default_tools()
        except Exception as exc:
            logger.warning("_dispatch_tool: initialize_default_tools error: %s", exc)

        # 2. Look up tool in registry.
        registry = get_registry()
        tool = registry.get(tool_name)
        if tool is None:
            _audit("not_found")
            logger.warning("_dispatch_tool: tool %r not found in registry", tool_name)
            return {
                "tool": tool_name,
                "status": "error",
                "error": f"Tool not found in registry: {tool_name}",
                "inputs_received": inputs,
            }

        # 3. Validate inputs against parameter schema.
        valid, validation_error = tool.validate_parameters(**inputs)
        if not valid:
            _audit("validation_failed", validation_error or "")
            logger.warning(
                "_dispatch_tool: input validation failed for %r: %s",
                tool_name,
                validation_error,
            )
            return {
                "tool": tool_name,
                "status": "error",
                "error": f"Input validation failed: {validation_error}",
                "inputs_received": inputs,
            }

        # 4. Enforce autonomy tier — Band 2/3 require human approval.
        if tool.autonomy_tier in {ToolAutonomyTier.TIER_2_APPROVE, ToolAutonomyTier.TIER_3_HARD_STOP}:
            _audit("pending_approval", f"tier={tool.autonomy_tier.name}")
            logger.info(
                "_dispatch_tool: tool %r requires approval (tier=%s) — not auto-dispatching",
                tool_name,
                tool.autonomy_tier.name,
            )
            return {
                "tool": tool_name,
                "status": "pending_approval",
                "autonomy_tier": tool.autonomy_tier.name,
                "message": "Tool requires human approval before execution (Band 2/3)",
                "inputs_received": inputs,
            }

        # 5. Enqueue via tool_runner (Celery).
        # tool_runner.enqueue() is synchronous (calls Redis apply_async).
        # Run in executor to avoid blocking the event loop.
        from .tool_runner import tool_runner as _tool_runner

        def _enqueue() -> str:
            return _tool_runner.enqueue(
                tool_id=tool_name,
                params=inputs,
                program_id=program_id,
                certificate_id=certificate_id,
                user_id=user_id,
                workflow_id=workflow_id,
                require_approval=False,  # Band 0/1 already verified above
                approved=True,
            )

        try:
            loop = asyncio.get_running_loop()
            task_id: str = await loop.run_in_executor(None, _enqueue)
        except _HTTPException as exc:
            # tool_runner raises HTTPException for 403/404/503 conditions.
            _audit("blocked", f"http_{exc.status_code}: {exc.detail}")
            logger.warning(
                "_dispatch_tool: tool %r blocked by enqueue (HTTP %d): %s",
                tool_name,
                exc.status_code,
                exc.detail,
            )
            return {
                "tool": tool_name,
                "status": "error",
                "error": f"Dispatch blocked (HTTP {exc.status_code}): {exc.detail}",
                "inputs_received": inputs,
            }
        except Exception as exc:
            _audit("enqueue_error", str(exc))
            logger.error("_dispatch_tool: enqueue failed for %r: %s", tool_name, exc)
            return {
                "tool": tool_name,
                "status": "error",
                "error": str(exc),
                "inputs_received": inputs,
            }

        elapsed_ms = _time.monotonic() * 1000 - start_ms
        _audit("queued", f"task_id={task_id} elapsed_ms={elapsed_ms:.0f}")
        logger.info(
            "_dispatch_tool: queued tool=%r task_id=%s elapsed=%.0fms",
            tool_name,
            task_id,
            elapsed_ms,
        )
        return {
            "tool": tool_name,
            "status": "queued",
            "task_id": task_id,
            "inputs_received": inputs,
            "elapsed_ms": elapsed_ms,
        }

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        registered = list(self.factory.providers.keys())
        quota_status = self.quota.status()
        return {
            "status": "ok" if registered else "degraded",
            "primary": self._primary,
            "routing": self._routing,
            "fallbacks": self._fallbacks,
            "providers_registered": [p.value for p in registered],
            "active_tier": quota_status.active_tier.value,
            "emergency_fallback_active": quota_status.emergency_fallback_active,
            "flash_lite_spillover_active": quota_status.flash_lite_spillover_active,
            "pro_restricted": quota_status.pro_restricted,
            "session_count": self._session_count,
        }

    def agent_list(self) -> list[dict[str, Any]]:
        """Return the provider chain as an agent list for the frontend."""
        from .llm_providers import ProviderRole

        agents = []
        for provider, instance in self.factory.providers.items():
            role: ProviderRole = getattr(instance.config, "role", ProviderRole.FALLBACK)
            agents.append(
                {
                    "id": provider.value,
                    "name": f"{provider.value} ({getattr(instance, 'model', 'unknown')})",
                    "objective": role.value,
                    "status": "ready",
                    "autonomy_level": 4 if role == ProviderRole.PRIMARY else 2,
                    "performance": {"success_rate": 1.0, "success_count": 0, "failure_count": 0},
                }
            )
        return agents

    def quota_status_dict(self) -> dict[str, Any]:
        return self.quota.status().to_dict()


# ---------------------------------------------------------------------------
# Singleton lifecycle
# ---------------------------------------------------------------------------


def initialize_gemini_orchestrator() -> GeminiOrchestrator:
    """Initialise the singleton.  Called once from main.py lifespan startup."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = GeminiOrchestrator()
        status = _orchestrator.quota.status()
        logger.info(
            "GeminiOrchestrator initialised — active_tier=%s  flash_rpd=%d  "
            "flash_lite_rpd=%d  pro_rpd=%d  emergency=%s",
            status.active_tier.value,
            status.flash_rpd_remaining,
            status.flash_lite_rpd_remaining,
            status.pro_rpd_remaining,
            status.emergency_fallback_active,
        )
    return _orchestrator


def get_gemini_orchestrator() -> GeminiOrchestrator:
    """Return the singleton, initialising lazily if not yet created."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = GeminiOrchestrator()
    return _orchestrator
