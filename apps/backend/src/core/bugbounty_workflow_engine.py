from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..schemas.campaigns import PhaseSeedSpec
from .scope_guardrails import ScopePolicy, enforce_safe_mode_for_tool, enforce_target_in_scope
from .tool_adapters_bugbounty import catalog_name_to_registry_tool_id, tool_entry_or_none


STAGES: tuple[str, ...] = (
    "passive_recon",
    "active_recon",
    "live_host_validation",
    "web_crawling",
    "endpoint_discovery",
    "parameter_discovery",
    "vuln_scan",
    "secret_scan",
    "tech_fingerprint",
    "prioritization_and_correlation",
    "report_prep",
)


@dataclass(frozen=True)
class WorkflowStep:
    stage: str
    tool: str
    approval_required: bool = False
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    description: str
    steps: tuple[WorkflowStep, ...]


WORKFLOW_TEMPLATES: dict[str, WorkflowTemplate] = {
    "workflow_recon_surface_map": WorkflowTemplate(
        name="workflow_recon_surface_map",
        description="Map domain attack surface through passive and low-noise active recon.",
        steps=(
            WorkflowStep("passive_recon", "subfinder"),
            WorkflowStep("passive_recon", "assetfinder"),
            WorkflowStep("passive_recon", "amass"),
            WorkflowStep("passive_recon", "gau"),
            WorkflowStep("passive_recon", "waybackurls"),
            WorkflowStep("active_recon", "dnsx"),
            WorkflowStep("live_host_validation", "httpx"),
            WorkflowStep("live_host_validation", "naabu"),
            WorkflowStep("tech_fingerprint", "tlsx"),
            WorkflowStep("prioritization_and_correlation", "k1_correlation"),
            WorkflowStep("report_prep", "k1_priority_ranking"),
        ),
    ),
    "workflow_web_attack_surface": WorkflowTemplate(
        name="workflow_web_attack_surface",
        description="Discover crawlable endpoints and content-discovery surface for web targets.",
        steps=(
            WorkflowStep("passive_recon", "subfinder"),
            WorkflowStep("live_host_validation", "httpx"),
            WorkflowStep("web_crawling", "katana"),
            WorkflowStep("web_crawling", "hakrawler"),
            WorkflowStep("web_crawling", "gospider"),
            WorkflowStep("endpoint_discovery", "waymore"),
            WorkflowStep("parameter_discovery", "ffuf", approval_required=True),
            WorkflowStep("tech_fingerprint", "httpx"),
            WorkflowStep("prioritization_and_correlation", "k1_correlation"),
            WorkflowStep("report_prep", "k1_priority_ranking"),
        ),
    ),
    "workflow_quick_vuln_sweep": WorkflowTemplate(
        name="workflow_quick_vuln_sweep",
        description="Fast vulnerability signal sweep over discovered web services.",
        steps=(
            WorkflowStep("passive_recon", "subfinder"),
            WorkflowStep("live_host_validation", "httpx"),
            WorkflowStep("live_host_validation", "naabu"),
            WorkflowStep("vuln_scan", "nuclei"),
            WorkflowStep("vuln_scan", "nikto"),
            WorkflowStep("vuln_scan", "dalfox", approval_required=True),
            WorkflowStep("prioritization_and_correlation", "k1_correlation"),
            WorkflowStep("report_prep", "k1_sandbox_critic"),
            WorkflowStep("report_prep", "k1_priority_ranking"),
        ),
    ),
    "workflow_secret_exposure_scan": WorkflowTemplate(
        name="workflow_secret_exposure_scan",
        description="Scan repository/path targets for accidental secret exposure.",
        steps=(
            WorkflowStep("secret_scan", "trufflehog"),
            WorkflowStep("secret_scan", "gitleaks"),
            WorkflowStep("secret_scan", "git-secrets"),
            WorkflowStep("secret_scan", "gitrob_alt"),
            WorkflowStep("prioritization_and_correlation", "k1_correlation"),
            WorkflowStep("report_prep", "k1_priority_ranking"),
        ),
    ),
    "workflow_priority_target_ranking": WorkflowTemplate(
        name="workflow_priority_target_ranking",
        description="Produce a conservative target-priority output from recon signals.",
        steps=(
            WorkflowStep("passive_recon", "subfinder"),
            WorkflowStep("passive_recon", "assetfinder"),
            WorkflowStep("live_host_validation", "httpx"),
            WorkflowStep("prioritization_and_correlation", "k1_correlation"),
            WorkflowStep("report_prep", "k1_priority_ranking"),
        ),
    ),
}


def list_workflow_templates() -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for template in WORKFLOW_TEMPLATES.values():
        output.append(
            {
                "name": template.name,
                "description": template.description,
                "stage_count": len(template.steps),
                "tools": [step.tool for step in template.steps],
                "stages": [step.stage for step in template.steps],
            }
        )
    return sorted(output, key=lambda item: item["name"])


def _order_for_stage(stage: str, index: int) -> int:
    base = STAGES.index(stage) * 100 if stage in STAGES else 1000
    return base + index


def build_phase_specs_for_template(
    *,
    template_name: str,
    target: str,
    safe_mode: bool,
    scope_policy: ScopePolicy,
    enable_steps: list[str] | None = None,
    disable_steps: list[str] | None = None,
    dry_run: bool = False,
) -> tuple[list[PhaseSeedSpec], dict[str, Any]]:
    template = WORKFLOW_TEMPLATES.get(template_name)
    if template is None:
        raise ValueError(f"Unknown workflow template: {template_name}")

    enforce_target_in_scope(target, scope_policy)
    enabled_set = {step.strip().lower() for step in (enable_steps or []) if step.strip()}
    disabled_set = {step.strip().lower() for step in (disable_steps or []) if step.strip()}

    phase_specs: list[PhaseSeedSpec] = []
    current_stage: str | None = None
    stage_dependency_anchor: str | None = None
    last_stage_anchor: str | None = None

    for idx, step in enumerate(template.steps, start=1):
        step_name = f"{step.stage}:{step.tool}".lower()
        if enabled_set and step_name not in enabled_set and step.tool not in enabled_set:
            continue
        if step_name in disabled_set or step.tool in disabled_set:
            continue

        catalog_entry = tool_entry_or_none(step.tool)
        if catalog_entry is not None:
            enforce_safe_mode_for_tool(step.tool, safe_mode=safe_mode, tool_entry=catalog_entry.as_dict())

        adapter_tool_id = catalog_name_to_registry_tool_id(step.tool)
        phase_name = f"{step.stage}__{step.tool}"
        if step.stage != current_stage:
            current_stage = step.stage
            stage_dependency_anchor = last_stage_anchor
        # Always track the last processed phase so the next stage depends on it.
        last_stage_anchor = phase_name
        payload = {
            "target": target,
            "dispatch": {
                "tool_id": adapter_tool_id,
                "params": {"target": target, **step.params},
            },
            "workflow_stage": step.stage,
            "workflow_template": template.name,
            "dry_run": dry_run,
        }
        phase_specs.append(
            PhaseSeedSpec(
                phase_name=phase_name,
                phase_order=_order_for_stage(step.stage, idx),
                depends_on_phase_name=stage_dependency_anchor,
                approval_required=step.approval_required,
                queue_name="campaigns",
                input_payload_json=payload,
            )
        )

    if not phase_specs:
        raise ValueError("Workflow template produced no enabled phase steps")

    metadata = {
        "workflow_template": template.name,
        "workflow_description": template.description,
        "target": target,
        "safe_mode": safe_mode,
        "dry_run": dry_run,
        "steps_total": len(template.steps),
        "steps_enabled": len(phase_specs),
        "stage_order": STAGES,
    }
    return phase_specs, metadata
