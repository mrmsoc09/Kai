from __future__ import annotations

import pytest

from apps.backend.src.core.bugbounty_workflow_engine import (
    STAGES,
    WORKFLOW_TEMPLATES,
    build_phase_specs_for_template,
    list_workflow_templates,
)
from apps.backend.src.core.scope_guardrails import ScopePolicy


def test_workflow_templates_include_minimum_mvp_set():
    templates = {item["name"] for item in list_workflow_templates()}
    assert "workflow_recon_surface_map" in templates
    assert "workflow_web_attack_surface" in templates
    assert "workflow_quick_vuln_sweep" in templates
    assert "workflow_secret_exposure_scan" in templates
    assert "workflow_priority_target_ranking" in templates


def test_build_phase_specs_safe_mode_blocks_intrusive_tools():
    policy = ScopePolicy(allowlist=["*.example.com"])
    with pytest.raises(ValueError):
        build_phase_specs_for_template(
            template_name="workflow_web_attack_surface",
            target="api.example.com",
            safe_mode=True,
            scope_policy=policy,
        )


def test_build_phase_specs_works_with_intrusive_mode_disabled():
    policy = ScopePolicy(allowlist=["*.example.com"])
    phases, metadata = build_phase_specs_for_template(
        template_name="workflow_web_attack_surface",
        target="api.example.com",
        safe_mode=False,
        scope_policy=policy,
    )
    assert phases
    assert metadata["workflow_template"] == "workflow_web_attack_surface"
    assert any("dispatch" in phase.input_payload_json for phase in phases)


def test_out_of_scope_target_is_rejected():
    policy = ScopePolicy(allowlist=["*.example.com"])
    with pytest.raises(ValueError):
        build_phase_specs_for_template(
            template_name="workflow_recon_surface_map",
            target="evil.com",
            safe_mode=True,
            scope_policy=policy,
        )


def test_unknown_template_name_raises():
    policy = ScopePolicy()
    with pytest.raises(ValueError, match="Unknown workflow template"):
        build_phase_specs_for_template(
            template_name="nonexistent_template",
            target="example.com",
            safe_mode=True,
            scope_policy=policy,
        )


def test_disable_all_steps_raises():
    policy = ScopePolicy()
    template = WORKFLOW_TEMPLATES["workflow_priority_target_ranking"]
    all_tools = [step.tool for step in template.steps]
    with pytest.raises(ValueError, match="no enabled phase steps"):
        build_phase_specs_for_template(
            template_name="workflow_priority_target_ranking",
            target="example.com",
            safe_mode=True,
            scope_policy=policy,
            disable_steps=all_tools,
        )


def test_disable_specific_step():
    policy = ScopePolicy()
    phases_all, _ = build_phase_specs_for_template(
        template_name="workflow_priority_target_ranking",
        target="example.com",
        safe_mode=True,
        scope_policy=policy,
    )
    phases_reduced, _ = build_phase_specs_for_template(
        template_name="workflow_priority_target_ranking",
        target="example.com",
        safe_mode=True,
        scope_policy=policy,
        disable_steps=["subfinder"],
    )
    phase_names = {p.phase_name for p in phases_reduced}
    assert all("subfinder" not in name for name in phase_names)
    assert len(phases_reduced) < len(phases_all)


def test_dry_run_flag_propagated_to_payload():
    policy = ScopePolicy()
    phases, metadata = build_phase_specs_for_template(
        template_name="workflow_priority_target_ranking",
        target="example.com",
        safe_mode=True,
        scope_policy=policy,
        dry_run=True,
    )
    assert metadata["dry_run"] is True
    assert all(phase.input_payload_json["dry_run"] is True for phase in phases)


def test_phase_order_is_monotonically_non_decreasing():
    policy = ScopePolicy()
    phases, _ = build_phase_specs_for_template(
        template_name="workflow_recon_surface_map",
        target="example.com",
        safe_mode=True,
        scope_policy=policy,
    )
    orders = [p.phase_order for p in phases]
    assert orders == sorted(orders), "Phase orders must be non-decreasing"


def test_stage_dependency_anchors_to_last_step_of_previous_stage():
    """
    Regression test: the last phase of each stage must be the dependency anchor
    for the first phase of the next stage, not just the first phase of the stage.
    """
    policy = ScopePolicy()
    # workflow_recon_surface_map has multiple passive_recon steps followed by active_recon
    phases, _ = build_phase_specs_for_template(
        template_name="workflow_recon_surface_map",
        target="example.com",
        safe_mode=True,
        scope_policy=policy,
    )
    by_name = {p.phase_name: p for p in phases}

    # Find all passive_recon phases and the first active_recon phase
    passive_phases = [p for p in phases if p.phase_name.startswith("passive_recon__")]
    active_phases = [p for p in phases if p.phase_name.startswith("active_recon__")]

    if passive_phases and active_phases:
        last_passive = passive_phases[-1]
        first_active = active_phases[0]
        assert first_active.depends_on_phase_name == last_passive.phase_name, (
            f"First active_recon phase should depend on last passive_recon phase "
            f"({last_passive.phase_name!r}), got {first_active.depends_on_phase_name!r}"
        )


def test_first_stage_phases_have_no_dependency():
    policy = ScopePolicy()
    phases, _ = build_phase_specs_for_template(
        template_name="workflow_recon_surface_map",
        target="example.com",
        safe_mode=True,
        scope_policy=policy,
    )
    first_stage = phases[0].phase_name.split("__")[0]
    first_stage_phases = [p for p in phases if p.phase_name.startswith(f"{first_stage}__")]
    for phase in first_stage_phases:
        assert phase.depends_on_phase_name is None, (
            f"First-stage phases must have no dependency, got {phase.depends_on_phase_name!r}"
        )


def test_list_workflow_templates_returns_sorted_output():
    templates = list_workflow_templates()
    names = [t["name"] for t in templates]
    assert names == sorted(names)


def test_all_template_tools_present_in_phase_payloads():
    policy = ScopePolicy()
    for template_name, template in WORKFLOW_TEMPLATES.items():
        phases, _ = build_phase_specs_for_template(
            template_name=template_name,
            target="example.com",
            safe_mode=False,
            scope_policy=policy,
        )
        for phase in phases:
            assert "dispatch" in phase.input_payload_json
            assert "tool_id" in phase.input_payload_json["dispatch"]
            assert "target" in phase.input_payload_json


def test_target_is_injected_into_all_phase_payloads():
    policy = ScopePolicy()
    target = "api.example.com"
    phases, _ = build_phase_specs_for_template(
        template_name="workflow_priority_target_ranking",
        target=target,
        safe_mode=True,
        scope_policy=policy,
    )
    for phase in phases:
        assert phase.input_payload_json["target"] == target
        assert phase.input_payload_json["dispatch"]["params"]["target"] == target
