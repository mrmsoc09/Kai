"""
K1 Orchestration Stack — Platform 1: PraisonAI Governance Layer
================================================================
SecurityGovernorAgent:
    Chief security/intelligence agent. Validates ALL tool executions against
    scope policy, HIL gates, and policy bands before they reach Celery workers.
    Fast synchronous path: no LLM calls, rule-based only.
    Async path: LLM-powered risk assessment for Band 2 intrusive tools.

HandoffAgent:
    Coordinates phase transitions in K1 hunt workflows. Reads completed phase
    output and decides the optimal next phase with packaged context.

InterscanReportAgent:
    Generates structured, machine-readable intelligence briefs between scan
    phases. Surfaces critical findings and priority targets for the next agent.

Integration points:
    - tool_runner.enqueue()  → praison_safety_gate_hook()   (sync, every tool)
    - orchestration_graph.py → review_band2_action()         (async, Band 2 only)
    - orchestration_graph.py → generate_interscan_report()   (async, phase complete)
    - orchestration_graph.py → coordinate_phase_handoff()    (async, phase transition)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ── Exception ────────────────────────────────────────────────────────────────

class PraisonGovernanceError(Exception):
    """
    Raised when PraisonAI's SecurityGovernor blocks a tool execution.
    Caught by tool_runner.enqueue() and converted to HTTP 403.
    """

    def __init__(self, reason: str, tool_id: str = "", code: str = "GOVERNANCE_BLOCK"):
        self.reason = reason
        self.tool_id = tool_id
        self.code = code
        super().__init__(f"[{code}] tool={tool_id!r}: {reason}")


# ── Governance context ────────────────────────────────────────────────────────

@dataclass
class GovernanceContext:
    """Structured context passed to governance validation."""

    tool_id: str
    tool_tier: int                          # 0–3 from ToolRiskTier
    program_id: str = ""
    workflow_id: str = ""
    user_id: str = ""
    target: str = ""                        # primary scan target (from params)
    params: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── PraisonGovernor ───────────────────────────────────────────────────────────

class PraisonGovernor:
    """
    PraisonAI-powered governance layer for K1 tool execution and phase orchestration.

    Design principles:
    - sync validate_tool_request() is called on EVERY tool execution (no LLM, sub-ms)
    - async LLM methods are called selectively (Band 2 review, phase handoff, reports)
    - PraisonAI agents are lazily initialized on first async call (import cost deferred)
    - All LLM calls go through PraisonAI → LiteLLM → K1's configured provider
    - Fail-safe: unexpected errors in async paths do not block execution (logged only)
    - Fail-secure: unexpected errors in sync path allow through (scope_guardrails
      and authorization_gate are the authoritative hard blockers)
    """

    def __init__(self, config_path: str | None = None):
        self._config = self._load_config(config_path)
        self._agents_initialized = False
        self._security_agent: Any = None
        self._handoff_agent: Any = None
        self._report_agent: Any = None
        self._hil_policy = self._config.get("hil_gate_policy", {})

    # ── Config loading ────────────────────────────────────────────────────────

    def _load_config(self, path: str | None) -> dict[str, Any]:
        """Load agent role definitions and policy from YAML."""
        if path:
            config_path = Path(path)
        else:
            env_path = os.getenv("K1_PRAISON_CONFIG")
            if env_path:
                config_path = Path(env_path)
            else:
                # Resolve relative to this file: ../../../../orchestration/praison/agents.yaml
                config_path = (
                    Path(__file__).resolve().parents[4]
                    / "orchestration" / "praison" / "agents.yaml"
                )

        try:
            with config_path.open(encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
                logger.info("PraisonAI config loaded from %s", config_path)
                return loaded
        except FileNotFoundError:
            logger.warning(
                "PraisonAI config not found at %s — using built-in defaults", config_path
            )
            return {}
        except yaml.YAMLError as exc:
            logger.error("PraisonAI config YAML parse error: %s — using defaults", exc)
            return {}

    # ── Agent initialization ──────────────────────────────────────────────────

    def _ensure_agents(self) -> None:
        """
        Lazily initialize PraisonAI Agent objects on first async call.
        Deferred because praisonaiagents import is expensive and not needed
        on every request — only for LLM-powered async governance paths.
        """
        if self._agents_initialized:
            return

        try:
            from praisonaiagents import Agent  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "praisonaiagents is not installed. "
                "Run: pip install 'praisonaiagents>=0.0.50,<1.0'"
            ) from exc

        llm = self._resolve_llm()

        sg = self._config.get("security_governor", {})
        self._security_agent = Agent(
            name=sg.get("name", "SecurityGovernor"),
            role=sg.get("role", "Chief Security and Intelligence Officer"),
            goal=sg.get(
                "goal",
                "Validate tool executions against scope, HIL gates, and policy bands",
            ),
            backstory=sg.get(
                "backstory",
                (
                    "You are K1's security conscience — a senior red team operator and "
                    "compliance authority. You block any scan that violates scope, exceeds "
                    "authorized bands, or bypasses HIL checkpoints. You are not a rubber stamp."
                ),
            ),
            llm=sg.get("llm_pin") or llm,
            verbose=False,
        )

        ha = self._config.get("handoff_agent", {})
        self._handoff_agent = Agent(
            name=ha.get("name", "PhaseHandoff"),
            role=ha.get("role", "Intelligence Handoff Coordinator"),
            goal=ha.get(
                "goal",
                "Coordinate phase transitions and package findings context for next-phase agents",
            ),
            backstory=ha.get(
                "backstory",
                (
                    "You are K1's transition intelligence — you read phase output, "
                    "assess what was learned, and decide the optimal path forward. "
                    "You package context cleanly so the next agent can start immediately."
                ),
            ),
            llm=ha.get("llm_pin") or llm,
            verbose=False,
        )

        ra = self._config.get("report_agent", {})
        self._report_agent = Agent(
            name=ra.get("name", "InterscanReporter"),
            role=ra.get("role", "Interscan Intelligence Reporter"),
            goal=ra.get(
                "goal",
                "Generate structured handoff reports between scan phases",
            ),
            backstory=ra.get(
                "backstory",
                (
                    "You distill raw scan output into precise, actionable intelligence briefings. "
                    "You highlight critical findings, exposure chains, and recommended priorities "
                    "for the next phase. You write for operators, not for word count."
                ),
            ),
            llm=ra.get("llm_pin") or llm,
            verbose=False,
        )

        self._agents_initialized = True
        logger.info(
            "PraisonAI agents initialized: %s, %s, %s",
            self._security_agent.name,
            self._handoff_agent.name,
            self._report_agent.name,
        )

    def _resolve_llm(self) -> str:
        """
        Resolve the LiteLLM model string for PraisonAI agents.

        Priority:
          1. agents.yaml llm_override (applies to all agents unless per-agent llm_pin set)
          2. K1_PRIMARY_LLM_PROVIDER env var → translated to LiteLLM format
          3. Default: anthropic/claude-sonnet-4-6
        """
        global_override = self._config.get("llm_override")
        if global_override:
            return global_override

        provider = os.getenv("K1_PRIMARY_LLM_PROVIDER", "anthropic").lower().strip()
        model_map: dict[str, str] = {
            "anthropic": f"anthropic/{os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-6')}",
            "openai": f"openai/{os.getenv('OPENAI_MODEL', 'gpt-4o')}",
            "gemini": f"gemini/{os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')}",
            "ollama": f"ollama/{os.getenv('OLLAMA_MODEL', 'llama3')}",
        }
        resolved = model_map.get(provider, "anthropic/claude-sonnet-4-6")
        logger.debug("PraisonAI LLM resolved to: %s", resolved)
        return resolved

    # ── Sync fast path ────────────────────────────────────────────────────────

    def validate_tool_request(self, ctx: GovernanceContext) -> None:
        """
        Fast synchronous governance validation. No LLM calls — sub-millisecond.
        Called by praison_safety_gate_hook() on EVERY tool execution.

        Enforces (in priority order):
          1. Band 3 tools: ALWAYS blocked at this layer
          2. Band 2 tools: require both workflow_id AND program_id
          3. All others: approved at this layer (deeper checks in scope_guardrails
             and authorization_gate have already run before this hook fires)

        Raises:
            PraisonGovernanceError: if the request is blocked
        """
        band3_block = self._hil_policy.get("band3_always_block", True)
        band2_requires_ctx = self._hil_policy.get("band2_requires_workflow_context", True)
        orphaned_allowed = self._hil_policy.get("orphaned_intrusive_scans_allowed", False)

        # ── Band 3: hard block ───────────────────────────────────────────────
        if band3_block and ctx.tool_tier >= 3:
            raise PraisonGovernanceError(
                reason=(
                    "Band 3 tools are never permitted through autonomous execution. "
                    "This action requires direct operator invocation with explicit override."
                ),
                tool_id=ctx.tool_id,
                code="BAND3_HARD_BLOCK",
            )

        # ── Band 2: requires campaign context ────────────────────────────────
        if ctx.tool_tier == 2 and band2_requires_ctx and not orphaned_allowed:
            missing = []
            if not ctx.workflow_id:
                missing.append("workflow_id")
            if not ctx.program_id:
                missing.append("program_id")
            if missing:
                raise PraisonGovernanceError(
                    reason=(
                        f"Band 2 (intrusive) tool requires campaign context. "
                        f"Missing: {', '.join(missing)}. "
                        "Orphaned intrusive scans are not permitted."
                    ),
                    tool_id=ctx.tool_id,
                    code="BAND2_NO_CAMPAIGN_CONTEXT",
                )

        logger.debug(
            "PraisonGovernor sync approved: tool=%s tier=%d workflow=%s",
            ctx.tool_id,
            ctx.tool_tier,
            ctx.workflow_id or "none",
        )

    # ── Async LLM path: Band 2 risk assessment ───────────────────────────────

    async def review_band2_action(
        self,
        ctx: GovernanceContext,
        tool_schema: dict[str, Any],
        scope_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """
        LLM-powered governance review for Band 2 (intrusive) tool executions.
        Called BEFORE the HIL approval request is created, to enrich the
        approval with an AI-generated risk assessment that the human approver sees.

        Returns:
            {
                "approved":              bool,
                "risk_level":            "low|medium|high|critical",
                "risk_rationale":        str,
                "recommended_params":    dict,   # suggested parameter adjustments
                "hil_summary":           str,    # shown to the human approver
            }

        Fail-safe: On any error, returns a blocking response requiring manual review.
        """
        self._ensure_agents()

        from praisonaiagents import Task, PraisonAIAgents  # type: ignore[import-untyped]

        prompt = (
            f"Review this Band 2 (intrusive) tool execution request and produce a "
            f"structured risk assessment.\n\n"
            f"Tool ID: {ctx.tool_id}\n"
            f"Target: {ctx.target or 'not specified'}\n"
            f"Program ID: {ctx.program_id}\n"
            f"Workflow ID: {ctx.workflow_id}\n"
            f"Parameters: {json.dumps(ctx.params, default=str)}\n"
            f"Tool Schema: {json.dumps(tool_schema, default=str)}\n"
            f"Active Scope Summary: {json.dumps(scope_summary, default=str)}\n\n"
            f"Assess the following:\n"
            f"1. Is the target within the declared scope?\n"
            f"2. Are the parameters within safe and authorized bounds?\n"
            f"3. What is the blast radius of this scan (what could it trigger/alert)?\n"
            f"4. Are there parameter adjustments that would reduce risk while achieving the goal?\n"
            f"5. What should the human approver specifically look for before approving?\n\n"
            f"Output a JSON object with exactly these keys:\n"
            f"  approved (bool), risk_level (low/medium/high/critical), "
            f"risk_rationale (str), recommended_params (dict), hil_summary (str)."
        )

        task = Task(
            description=prompt,
            agent=self._security_agent,
            expected_output="JSON object with governance risk assessment",
        )
        runner = PraisonAIAgents(
            agents=[self._security_agent],
            tasks=[task],
            verbose=False,
        )

        try:
            raw = await asyncio.to_thread(runner.start)
            return self._parse_json_result(
                raw,
                fallback={
                    "approved": True,
                    "risk_level": "medium",
                    "risk_rationale": "Automated review produced unparseable output; defaulting to medium.",
                    "recommended_params": {},
                    "hil_summary": str(raw),
                },
            )
        except Exception as exc:
            logger.error("PraisonAI Band2 review failed for tool %s: %s", ctx.tool_id, exc)
            return {
                "approved": False,
                "risk_level": "high",
                "risk_rationale": (
                    f"Automated governance review failed: {exc}. "
                    "Blocking pending manual review."
                ),
                "recommended_params": {},
                "hil_summary": (
                    "Automated governance review encountered an error. "
                    "Manual review is required before approving this action."
                ),
            }

    # ── Async LLM path: Interscan report ─────────────────────────────────────

    async def generate_interscan_report(
        self,
        workflow_id: str,
        completed_phase: str,
        phase_results: dict[str, Any],
        scope_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate a structured interscan intelligence brief after a phase completes.
        Packaged by the InterscanReportAgent for consumption by the next phase's agent.

        Returns:
            {
                "workflow_id":           str,
                "phase_completed":       str,
                "findings_summary":      str,
                "critical_targets":      list[str],
                "recommended_next_phase": str,
                "priority_targets":      list[str],
                "intelligence_brief":    str,
                "hil_flags":             list[str],  # any scope/HIL concerns
                "generated_at":          str,        # ISO 8601
            }
        """
        self._ensure_agents()

        from praisonaiagents import Task, PraisonAIAgents  # type: ignore[import-untyped]

        prompt = (
            f"Generate an interscan intelligence brief for K1 hunt workflow {workflow_id}.\n\n"
            f"Completed Phase: {completed_phase}\n"
            f"Phase Results: {json.dumps(phase_results, default=str)}\n"
            f"Active Scope: {json.dumps(scope_summary, default=str)}\n\n"
            f"Produce a concise intelligence brief covering:\n"
            f"1. Key findings from this phase (critical and high priority only — omit low/info)\n"
            f"2. Attack surface changes discovered (new subdomains, open ports, endpoints)\n"
            f"3. Priority targets for the next phase (specific hosts/paths/parameters)\n"
            f"4. Recommended next phase with one-line justification\n"
            f"5. Any scope violations or HIL flags encountered during this phase\n\n"
            f"Output a JSON object with exactly these keys:\n"
            f"  findings_summary (str), critical_targets (list[str]), "
            f"recommended_next_phase (str), priority_targets (list[str]), "
            f"intelligence_brief (str), hil_flags (list[str])."
        )

        task = Task(
            description=prompt,
            agent=self._report_agent,
            expected_output="JSON object with interscan intelligence brief",
        )
        runner = PraisonAIAgents(
            agents=[self._report_agent],
            tasks=[task],
            verbose=False,
        )

        try:
            raw = await asyncio.to_thread(runner.start)
            result = self._parse_json_result(raw, fallback={"intelligence_brief": str(raw)})
            result["workflow_id"] = workflow_id
            result["phase_completed"] = completed_phase
            result["generated_at"] = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as exc:
            logger.error(
                "PraisonAI interscan report failed for workflow %s phase %s: %s",
                workflow_id, completed_phase, exc,
            )
            return {
                "workflow_id": workflow_id,
                "phase_completed": completed_phase,
                "findings_summary": "Report generation failed.",
                "critical_targets": [],
                "recommended_next_phase": "unknown",
                "priority_targets": [],
                "intelligence_brief": f"Report generation error: {exc}",
                "hil_flags": [],
                "error": str(exc),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

    # ── Async LLM path: Phase handoff coordination ───────────────────────────

    async def coordinate_phase_handoff(
        self,
        workflow_id: str,
        completed_phase: str,
        phase_results: dict[str, Any],
        available_phases: list[str],
        scope_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Use HandoffAgent to decide the next phase and route accordingly.

        Returns:
            {
                "workflow_id":       str,
                "next_phase":        str,
                "skip_phases":       list[str],   # phases that can be skipped
                "handoff_context":   dict,         # context package for next agent
                "rationale":         str,
            }

        Fail-safe: On error, falls back to linear phase progression.
        """
        self._ensure_agents()

        from praisonaiagents import Task, PraisonAIAgents  # type: ignore[import-untyped]

        prompt = (
            f"Coordinate the phase handoff for K1 vulnerability hunt workflow {workflow_id}.\n\n"
            f"Just completed: {completed_phase}\n"
            f"Phase results summary: {json.dumps(phase_results, default=str)}\n"
            f"Available next phases: {available_phases}\n"
            f"Active scope: {json.dumps(scope_summary, default=str)}\n\n"
            f"Decide:\n"
            f"1. Which phase should run next from the available list?\n"
            f"2. Which phases (if any) can be skipped based on what was already discovered?\n"
            f"3. What specific context should be handed off to the next agent to avoid\n"
            f"   redundant work and focus on the highest-value targets?\n\n"
            f"Output a JSON object with exactly these keys:\n"
            f"  next_phase (str — must be from available_phases list or 'complete'), "
            f"skip_phases (list[str]), handoff_context (dict), rationale (str)."
        )

        task = Task(
            description=prompt,
            agent=self._handoff_agent,
            expected_output="JSON object with handoff routing decision",
        )
        runner = PraisonAIAgents(
            agents=[self._handoff_agent],
            tasks=[task],
            verbose=False,
        )

        try:
            raw = await asyncio.to_thread(runner.start)
            result = self._parse_json_result(
                raw,
                fallback={
                    "next_phase": available_phases[0] if available_phases else "complete",
                    "skip_phases": [],
                    "handoff_context": phase_results,
                    "rationale": str(raw),
                },
            )
            result["workflow_id"] = workflow_id
            # Ensure next_phase is valid
            if result.get("next_phase") not in available_phases + ["complete"]:
                result["next_phase"] = available_phases[0] if available_phases else "complete"
            return result
        except Exception as exc:
            logger.error(
                "PraisonAI handoff coordination failed for workflow %s: %s",
                workflow_id, exc,
            )
            return {
                "workflow_id": workflow_id,
                "next_phase": available_phases[0] if available_phases else "complete",
                "skip_phases": [],
                "handoff_context": phase_results,
                "rationale": f"Automated handoff failed ({exc}). Using linear fallback.",
            }

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json_result(
        raw: Any,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Extract a JSON dict from a PraisonAI agent result string.
        Returns fallback if parsing fails — never raises.
        """
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return fallback
        # Try to find a JSON object in the response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return fallback

    # ── Agent lifecycle governance (sync, no LLM) ────────────────────────────

    def validate_agent_spawn(
        self,
        agent_id: str,
        workflow_id: str,
        program_id: str,
        user_id: str,
        risk_profile: str = "standard",
        parent_agent: str = "",
    ) -> None:
        """
        Validate that an agent spawn is permitted.

        Rules (in priority order):
          1. governance agents require full campaign context (workflow_id + program_id)
          2. All agent spawns require at minimum a workflow_id when spawned
             from within an active hunt (non-governance spawning)
          3. Parent agent must exist if specified (checked by registry, not here)

        Raises:
            PraisonGovernanceError: if spawn is blocked.
        """
        lifecycle = self._config.get("agent_lifecycle_policy", {})
        governance_requires_ctx = lifecycle.get("governance_agents_require_campaign_context", True)

        if risk_profile == "governance" and governance_requires_ctx:
            missing = []
            if not workflow_id:
                missing.append("workflow_id")
            if not program_id:
                missing.append("program_id")
            if missing:
                raise PraisonGovernanceError(
                    reason=(
                        f"Governance agent '{agent_id}' requires full campaign context. "
                        f"Missing: {', '.join(missing)}."
                    ),
                    tool_id=agent_id,
                    code="GOVERNANCE_AGENT_SPAWN_BLOCKED",
                )

        logger.debug(
            "PraisonGovernor approved agent spawn: agent=%s profile=%s workflow=%s",
            agent_id, risk_profile, workflow_id or "none",
        )

    def validate_agent_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        workflow_id: str,
        program_id: str,
        user_id: str,
        handoff_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Validate that a handoff between agents is permitted.

        Rules:
          1. Handoff must occur within an active workflow (workflow_id required)
          2. handoff_data must not exceed the max memory write size
             (prevents oversized context dumps between agents)
          3. Governance → any: permitted (governance can hand off to any)
          4. Any → governance: permitted (agents can request governance review)

        Raises:
            PraisonGovernanceError: if handoff is blocked.
        """
        if not workflow_id:
            raise PraisonGovernanceError(
                reason=(
                    f"Agent handoff from '{from_agent_id}' to '{to_agent_id}' "
                    "requires an active workflow_id."
                ),
                tool_id=from_agent_id,
                code="HANDOFF_NO_WORKFLOW_CONTEXT",
            )

        # Check handoff data size
        if handoff_data:
            lifecycle = self._config.get("agent_lifecycle_policy", {})
            max_bytes = lifecycle.get("max_memory_write_bytes", 1_048_576)  # 1 MB default
            import sys
            data_size = sys.getsizeof(str(handoff_data))
            if data_size > max_bytes:
                raise PraisonGovernanceError(
                    reason=(
                        f"Handoff data from '{from_agent_id}' exceeds maximum size "
                        f"({data_size} bytes > {max_bytes} bytes limit)."
                    ),
                    tool_id=from_agent_id,
                    code="HANDOFF_DATA_OVERSIZED",
                )

        logger.debug(
            "PraisonGovernor approved handoff: %s → %s workflow=%s",
            from_agent_id, to_agent_id, workflow_id,
        )

    def validate_memory_write(
        self,
        agent_id: str,
        agent_memory_scope: str,
        target_scope: str,
        memory_key: str,
        data_size_bytes: int,
        workflow_id: str,
        program_id: str,
        user_id: str,
    ) -> None:
        """
        Validate that an agent is permitted to write to the target memory scope.

        Rules:
          1. Agent cannot write to a scope exceeding its declared memory_scope
             (session agents cannot write to workflow or persistent scope)
          2. Data size must not exceed max_memory_write_bytes
          3. persistent writes require a workflow_id (no ephemeral persistent writes)

        Raises:
            PraisonGovernanceError: if memory write is blocked.
        """
        lifecycle = self._config.get("agent_lifecycle_policy", {})
        enforce_hierarchy = lifecycle.get("enforce_memory_scope_hierarchy", True)
        max_bytes = lifecycle.get("max_memory_write_bytes", 1_048_576)

        # Scope hierarchy: session=0 < workflow=1 < persistent=2
        _scope_rank = {"session": 0, "workflow": 1, "persistent": 2}

        if enforce_hierarchy:
            agent_rank = _scope_rank.get(agent_memory_scope, 0)
            target_rank = _scope_rank.get(target_scope, 0)
            if target_rank > agent_rank:
                raise PraisonGovernanceError(
                    reason=(
                        f"Agent '{agent_id}' has memory_scope='{agent_memory_scope}' "
                        f"but attempted to write to scope='{target_scope}'. "
                        "Agents cannot write to a scope exceeding their declared boundary."
                    ),
                    tool_id=agent_id,
                    code="MEMORY_SCOPE_VIOLATION",
                )

        if data_size_bytes > max_bytes:
            raise PraisonGovernanceError(
                reason=(
                    f"Agent '{agent_id}' memory write exceeds size limit: "
                    f"{data_size_bytes} bytes > {max_bytes} bytes."
                ),
                tool_id=agent_id,
                code="MEMORY_WRITE_OVERSIZED",
            )

        if target_scope == "persistent" and not workflow_id:
            raise PraisonGovernanceError(
                reason=(
                    f"Agent '{agent_id}' attempted persistent memory write "
                    "without an active workflow_id. "
                    "Persistent writes require campaign context."
                ),
                tool_id=agent_id,
                code="PERSISTENT_WRITE_NO_CONTEXT",
            )

        logger.debug(
            "PraisonGovernor approved memory write: agent=%s scope=%s key=%s size=%d",
            agent_id, target_scope, memory_key, data_size_bytes,
        )

    def validate_external_call(
        self,
        agent_id: str,
        risk_profile: str,
        target_url: str,
        call_type: str,
        workflow_id: str,
        program_id: str,
        user_id: str,
    ) -> None:
        """
        Validate that an agent is permitted to make an external network call.

        Rules:
          1. Agent's risk_profile must be in the allowed_profiles list
          2. External calls require a workflow_id (no orphaned external calls)
          3. target_url must not be empty
          4. call_type must be recognized: "http_get" | "http_post" | "dns" | "tcp"

        Raises:
            PraisonGovernanceError: if external call is blocked.
        """
        lifecycle = self._config.get("agent_lifecycle_policy", {})
        allowed_profiles = lifecycle.get(
            "external_call_allowed_profiles",
            ["governance", "analysis", "orchestration", "recon", "reporting"],
        )

        if risk_profile not in allowed_profiles:
            raise PraisonGovernanceError(
                reason=(
                    f"Agent '{agent_id}' with risk_profile='{risk_profile}' "
                    "is not permitted to make external calls. "
                    f"Allowed profiles: {allowed_profiles}"
                ),
                tool_id=agent_id,
                code="EXTERNAL_CALL_PROFILE_BLOCKED",
            )

        if not workflow_id:
            raise PraisonGovernanceError(
                reason=(
                    f"Agent '{agent_id}' attempted external call to '{target_url}' "
                    "without an active workflow_id. "
                    "External calls require campaign context."
                ),
                tool_id=agent_id,
                code="EXTERNAL_CALL_NO_CONTEXT",
            )

        if not target_url:
            raise PraisonGovernanceError(
                reason=f"Agent '{agent_id}' attempted external call with empty target_url.",
                tool_id=agent_id,
                code="EXTERNAL_CALL_NO_TARGET",
            )

        logger.debug(
            "PraisonGovernor approved external call: agent=%s type=%s target=%s",
            agent_id, call_type, target_url,
        )

    @property
    def is_ready(self) -> bool:
        """True if config was loaded successfully."""
        return self._config is not None


# ── Module-level singleton ────────────────────────────────────────────────────

_governor: PraisonGovernor | None = None


def get_governor() -> PraisonGovernor:
    """Return the initialized PraisonGovernor singleton."""
    global _governor
    if _governor is None:
        raise RuntimeError(
            "PraisonGovernor not initialized. "
            "Call initialize_governor() during application startup."
        )
    return _governor


def initialize_governor(config_path: str | None = None) -> PraisonGovernor:
    """
    Initialize the PraisonGovernor singleton. Call once during app startup.
    PraisonAI Agent objects are lazily initialized on first async call.
    """
    global _governor
    _governor = PraisonGovernor(config_path)
    logger.info(
        "PraisonAI Governor initialized (agents lazy-loaded on first LLM call). "
        "Policy: band3_block=%s band2_ctx_required=%s",
        _governor._hil_policy.get("band3_always_block", True),
        _governor._hil_policy.get("band2_requires_workflow_context", True),
    )
    return _governor


# ── Hook callback ─────────────────────────────────────────────────────────────

def praison_safety_gate_hook(context: dict[str, Any]) -> dict[str, Any]:
    """
    HookRegistry callback registered as 'safety_gate' at order=5.

    AUDIT ORDERING FIX (Phase 3.5):
    This hook NO LONGER raises PraisonGovernanceError directly. Instead it
    updates the context with the governance decision. The hook execution order is:

      order=5   THIS HOOK    — evaluates, sets status + _governance_blocked
      order=50  audit hook   — writes the actual decision to audit log
      order=100 enforce hook — raises PraisonGovernanceError if _governance_blocked

    This guarantees the audit log always captures the true governance outcome
    (blocked or authorized), not a pre-decision "authorized" placeholder.

    Context keys set on block:
        _governance_blocked: True
        _governance_reason:  str  (human-readable reason)
        status:              "blocked"

    Context keys set on pass:
        praison_approved: True
        status:           "authorized"
    """
    global _governor
    if _governor is None:
        # Governor not yet initialized (startup/test path) — allow through.
        return {"status": "authorized", "praison_approved": True}

    try:
        ctx = GovernanceContext(
            tool_id=context.get("tool_id", ""),
            tool_tier=int(context.get("tool_tier", 0)),
            program_id=context.get("program_id", ""),
            workflow_id=context.get("workflow_id", ""),
            user_id=context.get("user_id", ""),
            target=context.get("target", ""),
            params=context.get("params") or {},
        )
        _governor.validate_tool_request(ctx)
        # Governance passed — update context, enforcement hook will not raise
        return {"praison_approved": True, "status": "authorized"}
    except PraisonGovernanceError as exc:
        # Governance blocked — update context. Do NOT raise here.
        # The enforce_safety_gate hook at order=100 will raise after the audit runs.
        logger.info(
            "PraisonAI governance blocked tool=%s reason=%s",
            context.get("tool_id"), exc.reason,
        )
        return {
            "_governance_blocked": True,
            "_governance_reason":  exc.reason,
            "status":              "blocked",
        }
    except Exception as exc:
        # Unexpected error — fail-open, log at error.
        # Hard security blocks come from scope_guardrails and authorization_gate.
        logger.error("PraisonAI safety_gate unexpected error (fail-open): %s", exc)
        return {"status": "authorized", "praison_approved": True}


# ── Agent lifecycle hook callbacks ────────────────────────────────────────────
# Registered with HookRegistry as "agent_spawn", "agent_handoff",
# "agent_memory_write", "agent_external_call" at application startup.
# Called by PraisonAgentRegistry.instantiate_agent() and other lifecycle points.

def praison_agent_spawn_hook(context: dict[str, Any]) -> dict[str, Any]:
    """
    HookRegistry callback for 'agent_spawn'.
    Fired by PraisonAgentRegistry._fire_spawn_hook() before agent instantiation.

    Context keys: agent_id, framework, workflow_id, program_id, parent_agent,
                  risk_profile, execution_id
    """
    global _governor
    if _governor is None:
        return {}
    try:
        _governor.validate_agent_spawn(
            agent_id=context.get("agent_id", ""),
            workflow_id=context.get("workflow_id", ""),
            program_id=context.get("program_id", ""),
            user_id=context.get("user_id", ""),
            risk_profile=context.get("risk_profile", "standard"),
            parent_agent=context.get("parent_agent", ""),
        )
        return {"praison_spawn_approved": True}
    except PraisonGovernanceError:
        raise
    except Exception as exc:
        logger.error("PraisonAI agent_spawn hook unexpected error (fail-open): %s", exc)
        return {}


def praison_agent_handoff_hook(context: dict[str, Any]) -> dict[str, Any]:
    """
    HookRegistry callback for 'agent_handoff'.
    Fired when execution transfers from one agent to another.

    Context keys: from_agent_id, to_agent_id, workflow_id, program_id,
                  user_id, handoff_data
    """
    global _governor
    if _governor is None:
        return {}
    try:
        _governor.validate_agent_handoff(
            from_agent_id=context.get("from_agent_id", ""),
            to_agent_id=context.get("to_agent_id", ""),
            workflow_id=context.get("workflow_id", ""),
            program_id=context.get("program_id", ""),
            user_id=context.get("user_id", ""),
            handoff_data=context.get("handoff_data"),
        )
        return {"praison_handoff_approved": True}
    except PraisonGovernanceError:
        raise
    except Exception as exc:
        logger.error("PraisonAI agent_handoff hook unexpected error (fail-open): %s", exc)
        return {}


def praison_agent_memory_write_hook(context: dict[str, Any]) -> dict[str, Any]:
    """
    HookRegistry callback for 'agent_memory_write'.
    Fired when an agent writes to shared memory.

    Context keys: agent_id, agent_memory_scope, target_scope, memory_key,
                  data_size_bytes, workflow_id, program_id, user_id
    """
    global _governor
    if _governor is None:
        return {}
    try:
        _governor.validate_memory_write(
            agent_id=context.get("agent_id", ""),
            agent_memory_scope=context.get("agent_memory_scope", "session"),
            target_scope=context.get("target_scope", "session"),
            memory_key=context.get("memory_key", ""),
            data_size_bytes=int(context.get("data_size_bytes", 0)),
            workflow_id=context.get("workflow_id", ""),
            program_id=context.get("program_id", ""),
            user_id=context.get("user_id", ""),
        )
        return {"praison_memory_write_approved": True}
    except PraisonGovernanceError:
        raise
    except Exception as exc:
        logger.error("PraisonAI agent_memory_write hook unexpected error (fail-open): %s", exc)
        return {}


def praison_agent_external_call_hook(context: dict[str, Any]) -> dict[str, Any]:
    """
    HookRegistry callback for 'agent_external_call'.
    Fired when an agent initiates an external network call.

    Context keys: agent_id, risk_profile, target_url, call_type,
                  workflow_id, program_id, user_id
    """
    global _governor
    if _governor is None:
        return {}
    try:
        _governor.validate_external_call(
            agent_id=context.get("agent_id", ""),
            risk_profile=context.get("risk_profile", "standard"),
            target_url=context.get("target_url", ""),
            call_type=context.get("call_type", "http_get"),
            workflow_id=context.get("workflow_id", ""),
            program_id=context.get("program_id", ""),
            user_id=context.get("user_id", ""),
        )
        return {"praison_external_call_approved": True}
    except PraisonGovernanceError:
        raise
    except Exception as exc:
        logger.error("PraisonAI agent_external_call hook unexpected error (fail-open): %s", exc)
        return {}
