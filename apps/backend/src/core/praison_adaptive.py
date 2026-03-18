"""
K1 Adaptive Execution Planning (Phase 4)
==========================================
Bounded adaptive autonomy for mission execution.

Agents can optimize execution within pre-authorized policy envelopes
but cannot mutate mission behavior arbitrarily.

Core types:
  ExecutionStrategy  -- full execution plan for a phase/node
  ExecutionPlanPatch -- proposed modification to the execution plan
  ToolProfile        -- approved tool configuration variant
  PromptProfile      -- approved prompt template variant

Allowed adaptive changes (Phase 4):
  - reorder_tools: reorder allowed tools within a phase
  - select_tool_candidate: choose among approved tool candidates
  - select_prompt_profile: choose among approved prompt profiles
  - select_parameter_profile: choose among approved parameter profiles
  - reprioritize_work: reprioritize same-phase work items
  - adjust_retry: adjust retry behavior within limits
  - adjust_schedule: adjust timing/schedule within bounded limits
  - activate_branch: activate pre-approved alternate branch

NOT allowed (always rejected):
  - graph_rewrite: arbitrary graph topology changes
  - scope_expansion: adding targets/tools outside approved set
  - approval_bypass: bypassing required approvals
  - cross_phase_mutation: changing other phases without governance
  - unapproved_tool: introducing tools not in the strategy

Policy validation:
  validate_plan_patch()           -- full patch validation
  validate_tool_profile_change()  -- tool profile switch validation
  validate_schedule_adjustment()  -- timing change validation

Security stance: deny-by-default. Unknown change_types are rejected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# -- Allowed change types (Phase 4) --------------------------------------------

class AdaptiveChangeType(str, Enum):
    REORDER_TOOLS          = "reorder_tools"
    SELECT_TOOL_CANDIDATE  = "select_tool_candidate"
    SELECT_PROMPT_PROFILE  = "select_prompt_profile"
    SELECT_PARAM_PROFILE   = "select_parameter_profile"
    REPRIORITIZE_WORK      = "reprioritize_work"
    ADJUST_RETRY           = "adjust_retry"
    ADJUST_SCHEDULE        = "adjust_schedule"
    ACTIVATE_BRANCH        = "activate_branch"


# Changes that are ALWAYS rejected regardless of context
_FORBIDDEN_CHANGE_TYPES = frozenset({
    "graph_rewrite",
    "scope_expansion",
    "approval_bypass",
    "cross_phase_mutation",
    "unapproved_tool",
    "self_modification",
})

_ALLOWED_CHANGE_TYPES = frozenset(e.value for e in AdaptiveChangeType)


# -- ToolProfile ---------------------------------------------------------------

@dataclass(frozen=True)
class ToolProfile:
    """
    Approved tool configuration variant within an execution strategy.

    An agent may switch between pre-approved tool profiles but cannot
    introduce unapproved tools or parameter combinations.
    """
    profile_id: str       = field(default_factory=lambda: str(uuid.uuid4()))
    tool_id: str          = ""
    profile_name: str     = ""     # e.g. "aggressive", "stealth", "standard"
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str      = ""
    risk_level: str       = "low"  # low | medium | high

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "tool_id": self.tool_id,
            "profile_name": self.profile_name,
            "parameters": self.parameters,
            "description": self.description,
            "risk_level": self.risk_level,
        }


# -- PromptProfile -------------------------------------------------------------

@dataclass(frozen=True)
class PromptProfile:
    """
    Approved prompt template variant for agent reasoning.

    Agents may select among pre-approved prompt profiles to adjust
    their reasoning approach without arbitrary self-modification.
    """
    profile_id: str       = field(default_factory=lambda: str(uuid.uuid4()))
    profile_name: str     = ""     # e.g. "thorough", "fast_triage", "deep_analysis"
    template: str         = ""     # prompt template text
    context_keys: tuple[str, ...] = field(default_factory=tuple)
    description: str      = ""

    def __post_init__(self) -> None:
        if isinstance(self.context_keys, list):
            object.__setattr__(self, "context_keys", tuple(self.context_keys))

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "template": self.template,
            "context_keys": list(self.context_keys),
            "description": self.description,
        }


# -- ExecutionStrategy ---------------------------------------------------------

@dataclass(frozen=True)
class ExecutionStrategy:
    """
    Full execution plan for a phase or node.

    Defines the bounded envelope within which adaptive changes are permitted.
    Everything outside this envelope requires governance approval.
    """
    strategy_id: str                    = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str                     = ""
    phase_id: str                       = ""
    node_id: str                        = ""

    # Tool candidates and ordering
    tool_candidates: tuple[str, ...]    = field(default_factory=tuple)
    tool_order: tuple[str, ...]         = field(default_factory=tuple)
    allowed_parameter_profiles: tuple[ToolProfile, ...] = field(default_factory=tuple)
    allowed_prompt_profiles: tuple[PromptProfile, ...] = field(default_factory=tuple)

    # Schedule and execution bounds
    schedule_window_start: str          = ""   # ISO 8601 or "" for immediate
    schedule_window_end: str            = ""   # ISO 8601 or "" for no deadline
    retry_policy: dict[str, Any]        = field(default_factory=lambda: {
        "max_retries": 3, "backoff_seconds": 5, "max_backoff_seconds": 60,
    })
    parallelism: int                    = 1    # max concurrent specialist executions
    stop_conditions: tuple[str, ...]    = field(default_factory=tuple)
    success_criteria: tuple[str, ...]   = field(default_factory=tuple)

    # Pre-approved alternate branches
    approved_branches: tuple[str, ...]  = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("tool_candidates", "tool_order", "stop_conditions",
                      "success_criteria", "approved_branches",
                      "allowed_parameter_profiles", "allowed_prompt_profiles"):
            val = getattr(self, name)
            if isinstance(val, list):
                object.__setattr__(self, name, tuple(val))

    def has_tool(self, tool_id: str) -> bool:
        return tool_id in self.tool_candidates

    def has_branch(self, branch_id: str) -> bool:
        return branch_id in self.approved_branches

    def has_prompt_profile(self, profile_name: str) -> bool:
        return any(p.profile_name == profile_name for p in self.allowed_prompt_profiles)

    def has_param_profile(self, profile_id: str) -> bool:
        return any(p.profile_id == profile_id for p in self.allowed_parameter_profiles)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "mission_id": self.mission_id,
            "phase_id": self.phase_id,
            "node_id": self.node_id,
            "tool_candidates": list(self.tool_candidates),
            "tool_order": list(self.tool_order),
            "allowed_parameter_profiles": [p.to_dict() for p in self.allowed_parameter_profiles],
            "allowed_prompt_profiles": [p.to_dict() for p in self.allowed_prompt_profiles],
            "schedule_window_start": self.schedule_window_start,
            "schedule_window_end": self.schedule_window_end,
            "retry_policy": self.retry_policy,
            "parallelism": self.parallelism,
            "stop_conditions": list(self.stop_conditions),
            "success_criteria": list(self.success_criteria),
            "approved_branches": list(self.approved_branches),
        }


# -- ExecutionPlanPatch --------------------------------------------------------

@dataclass(frozen=True)
class ExecutionPlanPatch:
    """
    Proposed modification to the execution plan by an agent.

    Must be explicit, validated, recorded in mission state, visible in
    telemetry, and replayable.
    """
    patch_id: str             = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str           = ""
    phase_id: str             = ""
    proposed_by_agent: str    = ""
    change_type: str          = ""       # must be in AdaptiveChangeType
    old_value: Any            = None
    new_value: Any            = None
    justification: str        = ""
    expected_benefit: str     = ""
    risk_impact: str          = "none"   # none | low | medium | high
    requires_governance_review: bool = False
    created_at: str           = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str               = "proposed"  # proposed | applied | rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "mission_id": self.mission_id,
            "phase_id": self.phase_id,
            "proposed_by_agent": self.proposed_by_agent,
            "change_type": self.change_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "justification": self.justification,
            "expected_benefit": self.expected_benefit,
            "risk_impact": self.risk_impact,
            "requires_governance_review": self.requires_governance_review,
            "created_at": self.created_at,
            "status": self.status,
        }


# -- Patch validation result ---------------------------------------------------

@dataclass(frozen=True)
class PatchValidationResult:
    valid: bool
    reason: str
    requires_escalation: bool = False

    @classmethod
    def accept(cls, reason: str = "ok") -> PatchValidationResult:
        return cls(valid=True, reason=reason)

    @classmethod
    def reject(cls, reason: str) -> PatchValidationResult:
        return cls(valid=False, reason=reason)

    @classmethod
    def escalate(cls, reason: str) -> PatchValidationResult:
        return cls(valid=False, reason=reason, requires_escalation=True)


# -- Policy validation functions -----------------------------------------------

def validate_plan_patch(
    patch: ExecutionPlanPatch,
    strategy: ExecutionStrategy,
) -> PatchValidationResult:
    """
    Validate a proposed plan patch against the execution strategy.

    Security stance: deny-by-default. Unknown change_types are rejected.
    Forbidden change types are always rejected.
    """
    # Forbidden changes -- always reject
    if patch.change_type in _FORBIDDEN_CHANGE_TYPES:
        return PatchValidationResult.reject(
            f"Change type '{patch.change_type}' is forbidden. "
            "This change cannot be made through adaptive execution."
        )

    # Unknown change type -- deny by default
    if patch.change_type not in _ALLOWED_CHANGE_TYPES:
        return PatchValidationResult.reject(
            f"Unknown change type '{patch.change_type}'. "
            "Only registered adaptive change types are permitted."
        )

    # Validate based on specific change type
    if patch.change_type == AdaptiveChangeType.REORDER_TOOLS:
        return _validate_tool_reorder(patch, strategy)
    if patch.change_type == AdaptiveChangeType.SELECT_TOOL_CANDIDATE:
        return _validate_tool_selection(patch, strategy)
    if patch.change_type == AdaptiveChangeType.SELECT_PROMPT_PROFILE:
        return _validate_prompt_selection(patch, strategy)
    if patch.change_type == AdaptiveChangeType.SELECT_PARAM_PROFILE:
        return _validate_param_selection(patch, strategy)
    if patch.change_type == AdaptiveChangeType.ADJUST_RETRY:
        return _validate_retry_adjustment(patch, strategy)
    if patch.change_type == AdaptiveChangeType.ADJUST_SCHEDULE:
        return _validate_schedule_adjustment(patch, strategy)
    if patch.change_type == AdaptiveChangeType.ACTIVATE_BRANCH:
        return _validate_branch_activation(patch, strategy)
    if patch.change_type == AdaptiveChangeType.REPRIORITIZE_WORK:
        return PatchValidationResult.accept("Same-phase reprioritization permitted")

    return PatchValidationResult.reject(f"Unhandled change type: {patch.change_type}")


def validate_tool_profile_change(
    from_profile: ToolProfile | None,
    to_profile: ToolProfile,
    strategy: ExecutionStrategy,
) -> PatchValidationResult:
    """Validate switching between tool profiles within a strategy."""
    if not strategy.has_param_profile(to_profile.profile_id):
        return PatchValidationResult.reject(
            f"Tool profile '{to_profile.profile_id}' is not in the approved parameter profiles"
        )
    if to_profile.risk_level == "high":
        return PatchValidationResult.escalate(
            f"High-risk tool profile '{to_profile.profile_name}' requires governance review"
        )
    return PatchValidationResult.accept(
        f"Tool profile switch to '{to_profile.profile_name}' permitted"
    )


def validate_schedule_adjustment(
    current_window: tuple[str, str],
    proposed_window: tuple[str, str],
    strategy: ExecutionStrategy,
) -> PatchValidationResult:
    """Validate adjusting schedule window within strategy bounds."""
    strat_start = strategy.schedule_window_start
    strat_end = strategy.schedule_window_end

    # If strategy has no bounds, any schedule is fine
    if not strat_start and not strat_end:
        return PatchValidationResult.accept("No schedule bounds in strategy")

    proposed_start, proposed_end = proposed_window

    # If strategy has bounds, proposed window must be within them
    if strat_start and proposed_start and proposed_start < strat_start:
        return PatchValidationResult.reject(
            f"Proposed start {proposed_start} is before strategy window start {strat_start}"
        )
    if strat_end and proposed_end and proposed_end > strat_end:
        return PatchValidationResult.reject(
            f"Proposed end {proposed_end} is after strategy window end {strat_end}"
        )

    return PatchValidationResult.accept("Schedule adjustment within bounds")


# -- Internal validators -------------------------------------------------------

def _validate_tool_reorder(
    patch: ExecutionPlanPatch, strategy: ExecutionStrategy
) -> PatchValidationResult:
    """New tool order must contain exactly the same tools as the strategy."""
    new_order = patch.new_value
    if not isinstance(new_order, (list, tuple)):
        return PatchValidationResult.reject("new_value must be a list of tool IDs")
    if set(new_order) != set(strategy.tool_order):
        extra = set(new_order) - set(strategy.tool_order)
        if extra:
            return PatchValidationResult.reject(
                f"Tool reorder introduces unapproved tools: {sorted(extra)}"
            )
        missing = set(strategy.tool_order) - set(new_order)
        return PatchValidationResult.reject(
            f"Tool reorder removes required tools: {sorted(missing)}"
        )
    return PatchValidationResult.accept("Tool reorder within approved set")


def _validate_tool_selection(
    patch: ExecutionPlanPatch, strategy: ExecutionStrategy
) -> PatchValidationResult:
    """Selected tool must be in the strategy's tool_candidates."""
    tool_id = patch.new_value
    if not isinstance(tool_id, str):
        return PatchValidationResult.reject("new_value must be a tool ID string")
    if not strategy.has_tool(tool_id):
        return PatchValidationResult.reject(
            f"Tool '{tool_id}' is not in approved candidates: {list(strategy.tool_candidates)}"
        )
    return PatchValidationResult.accept(f"Tool '{tool_id}' selected from approved candidates")


def _validate_prompt_selection(
    patch: ExecutionPlanPatch, strategy: ExecutionStrategy
) -> PatchValidationResult:
    """Selected prompt profile must be in the strategy's approved list."""
    profile_name = patch.new_value
    if not isinstance(profile_name, str):
        return PatchValidationResult.reject("new_value must be a prompt profile name")
    if not strategy.has_prompt_profile(profile_name):
        return PatchValidationResult.reject(
            f"Prompt profile '{profile_name}' is not in approved profiles"
        )
    return PatchValidationResult.accept(f"Prompt profile '{profile_name}' selected")


def _validate_param_selection(
    patch: ExecutionPlanPatch, strategy: ExecutionStrategy
) -> PatchValidationResult:
    """Selected parameter profile must be in the strategy's approved list."""
    profile_id = patch.new_value
    if not isinstance(profile_id, str):
        return PatchValidationResult.reject("new_value must be a parameter profile ID")
    if not strategy.has_param_profile(profile_id):
        return PatchValidationResult.reject(
            f"Parameter profile '{profile_id}' is not in approved profiles"
        )
    return PatchValidationResult.accept(f"Parameter profile '{profile_id}' selected")


def _validate_retry_adjustment(
    patch: ExecutionPlanPatch, strategy: ExecutionStrategy
) -> PatchValidationResult:
    """Retry adjustment must stay within strategy bounds."""
    new_retry = patch.new_value
    if not isinstance(new_retry, dict):
        return PatchValidationResult.reject("new_value must be a retry policy dict")
    max_allowed = strategy.retry_policy.get("max_retries", 3)
    proposed_max = new_retry.get("max_retries", 0)
    if proposed_max > max_allowed:
        return PatchValidationResult.reject(
            f"Proposed max_retries ({proposed_max}) exceeds strategy limit ({max_allowed})"
        )
    max_backoff = strategy.retry_policy.get("max_backoff_seconds", 60)
    proposed_backoff = new_retry.get("max_backoff_seconds", 0)
    if proposed_backoff > max_backoff:
        return PatchValidationResult.reject(
            f"Proposed max_backoff ({proposed_backoff}s) exceeds limit ({max_backoff}s)"
        )
    return PatchValidationResult.accept("Retry adjustment within bounds")


def _validate_schedule_adjustment(
    patch: ExecutionPlanPatch, strategy: ExecutionStrategy
) -> PatchValidationResult:
    """Schedule must stay within strategy window."""
    result = validate_schedule_adjustment(
        current_window=(strategy.schedule_window_start, strategy.schedule_window_end),
        proposed_window=patch.new_value if isinstance(patch.new_value, tuple) else ("", ""),
        strategy=strategy,
    )
    return result


def _validate_branch_activation(
    patch: ExecutionPlanPatch, strategy: ExecutionStrategy
) -> PatchValidationResult:
    """Branch must be in the pre-approved list."""
    branch_id = patch.new_value
    if not isinstance(branch_id, str):
        return PatchValidationResult.reject("new_value must be a branch ID string")
    if not strategy.has_branch(branch_id):
        return PatchValidationResult.reject(
            f"Branch '{branch_id}' is not in pre-approved branches: {list(strategy.approved_branches)}"
        )
    return PatchValidationResult.accept(f"Branch '{branch_id}' activation approved")
