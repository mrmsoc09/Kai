"""
LangChain Structured Output Schemas for K1 / Kai Platform
==========================================================
Pydantic v2 models used as structured-output targets for LangChain-based
reasoning steps.  Every model:

  * Uses ``model_config = ConfigDict(extra="forbid")`` to reject undeclared
    fields at validation time, preventing prompt-injection via unexpected keys.
  * Declares all fields with ``Field(description=…)`` so that LangChain's tool
    schema introspection produces accurate JSON Schema for the calling model.
  * Validates constrained numeric fields (confidence, priority) via Pydantic
    field constraints rather than post-validators, keeping schema clean.

Schema registry:
  ``SCHEMA_REGISTRY`` maps short names to classes.  Use ``get_schema()`` to
  resolve by name and ``validate_schema_output()`` to parse raw dicts.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared constants referenced by multiple schemas
# ---------------------------------------------------------------------------

# Fields that adaptive learning is permitted to propose changes for.
# Mirrors ``_ALLOWED_LEARNING_FIELDS`` in ``praison_strategy_learning.py``
# but is scoped here to schema-level documentation; runtime enforcement lives
# in the learning module.
_ALLOWED_LEARNING_FIELDS: frozenset[str] = frozenset(
    {
        "tool_order",
        "tool_profile_id",
        "prompt_profile_id",
        "retry_policy",
        "parallelism",
        "work_priority",
    }
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SeverityLevel(str, Enum):
    """Canonical severity levels used across triage, findings, and reports."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Schema: PlanPatchProposal
# ---------------------------------------------------------------------------


class PlanPatchProposal(BaseModel):
    """
    A structured plan-patch proposed by the adaptive learning subsystem.

    The ``field`` must reference a key in ``_ALLOWED_LEARNING_FIELDS``; the
    runtime enforcement in ``praison_strategy_learning.py`` rejects any
    proposal that touches governance-sensitive fields such as ``scope`` or
    ``targets``.
    """

    model_config = ConfigDict(extra="forbid")

    field: str = Field(
        description=(
            "Plan field to adjust.  Must be one of: "
            + ", ".join(sorted(_ALLOWED_LEARNING_FIELDS))
        )
    )
    current_value: Any = Field(description="The field's value before the proposed patch.")
    recommended_value: Any = Field(description="The suggested replacement value.")
    reason: str = Field(description="Human-readable rationale for the patch.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in this recommendation (0.0–1.0).",
    )
    based_on_executions: int = Field(
        ge=0,
        description="Number of historical executions that inform this recommendation.",
    )
    source_node_id: str = Field(
        default="",
        description="Workflow node that generated this proposal.",
    )
    mission_id: str = Field(
        default="",
        description="Mission context in which the proposal was generated.",
    )


# ---------------------------------------------------------------------------
# Schema: EvidenceSummary
# ---------------------------------------------------------------------------


class EvidenceSummary(BaseModel):
    """Summarised evidence produced by an artifact-analysis reasoning step."""

    model_config = ConfigDict(extra="forbid")

    findings_count: int = Field(
        ge=0,
        description="Total number of findings included in this summary.",
    )
    high_confidence_count: int = Field(
        ge=0,
        description="Number of findings with confidence >= 0.7.",
    )
    severity_distribution: dict[str, int] = Field(
        description="Mapping of severity label to finding count, e.g. {'high': 3, 'medium': 5}.",
    )
    top_findings: list[dict[str, Any]] = Field(
        description=(
            "Up to 10 highest-priority findings. "
            "Each dict contains: title, severity, target, confidence."
        ),
    )
    affected_targets: list[str] = Field(
        description="Unique targets (hostnames, URLs, IPs) referenced by the findings.",
    )
    signal_strength: str = Field(
        description="Overall signal quality: 'high' | 'medium' | 'low' | 'none'.",
    )
    summary_text: str = Field(
        description="Free-text executive summary of the evidence.",
    )
    artifact_ids_referenced: list[str] = Field(
        default_factory=list,
        description="IDs of artifacts consulted when building this summary.",
    )

    @field_validator("signal_strength")
    @classmethod
    def _validate_signal_strength(cls, v: str) -> str:
        allowed = {"high", "medium", "low", "none"}
        if v.lower() not in allowed:
            raise ValueError(f"signal_strength must be one of {allowed}, got '{v}'")
        return v.lower()


# ---------------------------------------------------------------------------
# Schema: TriageResult
# ---------------------------------------------------------------------------


class TriageResult(BaseModel):
    """Structured triage decision output for a single finding."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(description="Unique identifier of the finding being triaged.")
    title: str = Field(description="Short human-readable title of the finding.")
    severity: SeverityLevel = Field(description="Assessed severity level.")
    exploitability: str = Field(
        description=(
            "Exploitability assessment: "
            "'confirmed' | 'likely' | 'possible' | 'unlikely' | 'unknown'."
        ),
    )
    priority: int = Field(
        ge=1,
        le=10,
        description="Urgency priority from 1 (lowest) to 10 (highest).",
    )
    recommendation: str = Field(
        description="Suggested action: 'escalate' | 'investigate' | 'monitor' | 'close'.",
    )
    rationale: str = Field(description="Explanation justifying the triage decision.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the triage decision (0.0–1.0).",
    )
    affected_target: str = Field(
        default="",
        description="Primary affected host, URL, or IP address.",
    )
    cve_ids: list[str] = Field(
        default_factory=list,
        description="Associated CVE identifiers, e.g. ['CVE-2024-1234'].",
    )

    @field_validator("exploitability")
    @classmethod
    def _validate_exploitability(cls, v: str) -> str:
        allowed = {"confirmed", "likely", "possible", "unlikely", "unknown"}
        if v.lower() not in allowed:
            raise ValueError(f"exploitability must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("recommendation")
    @classmethod
    def _validate_recommendation(cls, v: str) -> str:
        allowed = {"escalate", "investigate", "monitor", "close"}
        if v.lower() not in allowed:
            raise ValueError(f"recommendation must be one of {allowed}, got '{v}'")
        return v.lower()


# ---------------------------------------------------------------------------
# Schema: ExploitAssessmentSummary
# ---------------------------------------------------------------------------


class ExploitAssessmentSummary(BaseModel):
    """Assessment of a vulnerability's exploit potential and recommended mitigation."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(description="Host, URL, or IP being assessed.")
    vulnerability_description: str = Field(
        description="Brief description of the vulnerability.",
    )
    cve_ids: list[str] = Field(
        description="CVE identifiers associated with the vulnerability.",
    )
    cvss_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="CVSS base score (0.0–10.0), or null if unavailable.",
    )
    is_exploitable: bool = Field(description="True if exploitation is assessed as feasible.")
    exploit_complexity: str = Field(
        description="Assessed exploit complexity: 'low' | 'medium' | 'high'.",
    )
    recommendation: str = Field(
        description="Recommended response action (e.g., 'patch immediately', 'monitor').",
    )
    mitigation_notes: str = Field(
        description="Specific mitigation steps or compensating controls.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the exploit assessment (0.0–1.0).",
    )

    @field_validator("exploit_complexity")
    @classmethod
    def _validate_exploit_complexity(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v.lower() not in allowed:
            raise ValueError(f"exploit_complexity must be one of {allowed}, got '{v}'")
        return v.lower()


# ---------------------------------------------------------------------------
# Schema: ReportSectionOutput
# ---------------------------------------------------------------------------


class ReportSectionOutput(BaseModel):
    """A structured section of an auto-generated mission report."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(description="Unique identifier for this report section.")
    section_type: str = Field(
        description=(
            "Section category: 'executive_summary' | 'technical_findings' | "
            "'methodology' | 'recommendations' | 'appendix'."
        ),
    )
    title: str = Field(description="Display title for this section.")
    content: str = Field(description="Full rendered content for this section (Markdown).")
    evidence_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifact IDs cited as evidence in this section.",
    )
    finding_ids: list[str] = Field(
        default_factory=list,
        description="Finding IDs discussed in this section.",
    )
    severity_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Severity label → count for findings in this section.",
    )
    word_count: int = Field(
        default=0,
        ge=0,
        description="Approximate word count of ``content``.",
    )

    @field_validator("section_type")
    @classmethod
    def _validate_section_type(cls, v: str) -> str:
        allowed = {
            "executive_summary",
            "technical_findings",
            "methodology",
            "recommendations",
            "appendix",
        }
        if v.lower() not in allowed:
            raise ValueError(f"section_type must be one of {allowed}, got '{v}'")
        return v.lower()


# ---------------------------------------------------------------------------
# Schema: ToolSelectionRationale
# ---------------------------------------------------------------------------


class ToolSelectionRationale(BaseModel):
    """Rationale produced by the reasoning layer for selecting a specific tool."""

    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(description="Unique tool identifier from the tool registry.")
    tool_name: str = Field(description="Human-readable tool name.")
    category: str = Field(
        description="Tool category, e.g. 'recon', 'scanning', 'validation'.",
    )
    reason: str = Field(description="Why this tool was selected for the current task.")
    expected_output_types: list[str] = Field(
        description="Artifact/output types this tool is expected to produce.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that this tool is appropriate (0.0–1.0).",
    )
    estimated_time_seconds: int = Field(
        default=0,
        ge=0,
        description="Expected wall-clock execution time in seconds (0 = unknown).",
    )
    requires_scope_validation: bool = Field(
        default=True,
        description="Whether this tool must pass scope validation before execution.",
    )
    safety_classification: str = Field(
        default="unknown",
        description="Policy band: 'band0' | 'band1' | 'band2' | 'band3' | 'unknown'.",
    )


# ---------------------------------------------------------------------------
# Schema: PromptProfileRecommendation
# ---------------------------------------------------------------------------


class PromptProfileRecommendation(BaseModel):
    """Recommendation to adopt a specific prompt profile for a workflow node."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(description="Unique identifier of the recommended profile.")
    profile_type: str = Field(
        description="Profile kind: 'tool_profile' | 'prompt_profile'.",
    )
    reason: str = Field(description="Explanation of why this profile is recommended.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that switching to this profile will improve outcomes (0.0–1.0).",
    )
    based_on_executions: int = Field(
        ge=0,
        description="Number of executions supporting this recommendation.",
    )
    expected_improvement: str = Field(
        default="",
        description="Free-text description of the expected performance improvement.",
    )

    @field_validator("profile_type")
    @classmethod
    def _validate_profile_type(cls, v: str) -> str:
        allowed = {"tool_profile", "prompt_profile"}
        if v.lower() not in allowed:
            raise ValueError(f"profile_type must be one of {allowed}, got '{v}'")
        return v.lower()


# ---------------------------------------------------------------------------
# Schema: KnowledgeLessonCandidate
# ---------------------------------------------------------------------------


class KnowledgeLessonCandidate(BaseModel):
    """
    A candidate knowledge lesson extracted from execution traces.

    Lessons with confidence < 0.5 are quarantined pending further evidence
    accumulation before being promoted to the knowledge base.
    """

    model_config = ConfigDict(extra="forbid")

    lesson_type: str = Field(
        description=(
            "Lesson category, e.g.: 'tool_order_lesson' | 'prompt_effectiveness' | "
            "'false_positive_indicator' | 'scope_edge_case' | 'timing_pattern'."
        ),
    )
    content: dict[str, Any] = Field(
        description="Structured lesson payload; shape varies by lesson_type.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0–1.0).  Values < 0.5 are quarantined.",
    )
    source_node_id: str = Field(
        description="Workflow node that generated this lesson candidate.",
    )
    source_mission_id: str = Field(
        description="Mission in which the lesson was observed.",
    )
    evidence_count: int = Field(
        ge=1,
        description="Number of independent observations supporting this lesson.",
    )
    lesson_id: str = Field(
        default="",
        description="Assigned upon acceptance into the knowledge base; empty while pending.",
    )


# ---------------------------------------------------------------------------
# Schema: NodeReasoningRequest
# ---------------------------------------------------------------------------


class NodeReasoningRequest(BaseModel):
    """
    Input schema for node-local LLM reasoning calls.

    Passed into a K1ChatModel invocation to provide the full execution context
    needed for the node to reason about next actions, triage findings, or
    synthesise evidence.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(description="Unique identifier of the workflow node invoking reasoning.")
    mission_id: str = Field(description="Parent mission context.")
    workflow_id: str = Field(description="Workflow instance ID.")
    program_id: str = Field(description="Bug bounty program or engagement ID.")
    phase: str = Field(
        description=(
            "Current workflow phase, e.g.: 'recon' | 'scanning' | 'triage' | "
            "'hil_review' | 'reporting'."
        ),
    )
    execution_mode: str = Field(
        description="Runtime mode: 'live' | 'graph_only' | 'tool_mock' | 'replay'.",
    )
    artifacts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Artifact metadata objects available to this node.",
    )
    findings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Finding objects in scope for this reasoning step.",
    )
    available_tools: list[str] = Field(
        default_factory=list,
        description="Tool IDs the node is authorised to invoke.",
    )
    system_context: str = Field(
        default="",
        description="Additional system-level context injected into the reasoning prompt.",
    )
    task_description: str = Field(
        default="",
        description="Free-text description of the task this reasoning step should perform.",
    )

    @field_validator("execution_mode")
    @classmethod
    def _validate_execution_mode(cls, v: str) -> str:
        allowed = {"live", "graph_only", "tool_mock", "replay"}
        if v.lower() not in allowed:
            raise ValueError(f"execution_mode must be one of {allowed}, got '{v}'")
        return v.lower()


# ---------------------------------------------------------------------------
# Schema: NodeReasoningResult
# ---------------------------------------------------------------------------


class NodeReasoningResult(BaseModel):
    """
    Output schema from a node-local LLM reasoning call.

    The ``output`` field carries a typed sub-result (e.g., an ``EvidenceSummary``
    or ``TriageResult`` serialised to dict); the caller is responsible for
    re-parsing it against the appropriate schema.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(description="Node that produced this reasoning result.")
    mission_id: str = Field(description="Parent mission context.")
    success: bool = Field(description="True if reasoning completed without error.")
    reasoning_type: str = Field(
        description=(
            "What kind of reasoning was performed, e.g.: "
            "'evidence_summary' | 'triage' | 'tool_selection' | 'plan_patch'."
        ),
    )
    output: dict[str, Any] = Field(
        description=(
            "Typed sub-result serialised to dict "
            "(e.g., EvidenceSummary, TriageResult, ToolSelectionRationale)."
        ),
    )
    tokens_used: int = Field(
        default=0,
        ge=0,
        description="Total tokens consumed by this reasoning call.",
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Wall-clock latency of the reasoning call in milliseconds.",
    )
    error: str = Field(
        default="",
        description="Error message if ``success`` is False; empty otherwise.",
    )


# ---------------------------------------------------------------------------
# Schema registry
# ---------------------------------------------------------------------------

SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "PlanPatchProposal": PlanPatchProposal,
    "EvidenceSummary": EvidenceSummary,
    "TriageResult": TriageResult,
    "ExploitAssessmentSummary": ExploitAssessmentSummary,
    "ReportSectionOutput": ReportSectionOutput,
    "ToolSelectionRationale": ToolSelectionRationale,
    "PromptProfileRecommendation": PromptProfileRecommendation,
    "KnowledgeLessonCandidate": KnowledgeLessonCandidate,
    "NodeReasoningRequest": NodeReasoningRequest,
    "NodeReasoningResult": NodeReasoningResult,
}


def get_schema(name: str) -> type[BaseModel] | None:
    """
    Look up a schema class by its short name.

    Args:
        name: Schema name, e.g. ``"TriageResult"``.

    Returns:
        The ``BaseModel`` subclass, or ``None`` if not found.
    """
    schema = SCHEMA_REGISTRY.get(name)
    if schema is None:
        logger.debug("get_schema: '%s' not found in SCHEMA_REGISTRY.", name)
    return schema


def validate_schema_output(name: str, data: dict[str, Any]) -> BaseModel:
    """
    Validate a raw dict against a named schema and return a typed instance.

    Args:
        name: Schema name (must exist in ``SCHEMA_REGISTRY``).
        data: Raw dictionary to validate and coerce.

    Returns:
        A validated ``BaseModel`` instance of the requested schema type.

    Raises:
        KeyError: If ``name`` is not registered.
        pydantic.ValidationError: If ``data`` fails schema validation.
    """
    schema = SCHEMA_REGISTRY.get(name)
    if schema is None:
        raise KeyError(
            f"Schema '{name}' not found in SCHEMA_REGISTRY. "
            f"Available schemas: {sorted(SCHEMA_REGISTRY.keys())}"
        )
    return schema.model_validate(data)
