from pathlib import Path

import pytest
import yaml

CREWS_DIR = Path("crews")
REGISTRY = CREWS_DIR / "crew_registry.yaml"


def test_crews_directory_exists():
    assert CREWS_DIR.exists(), "crews/ directory must exist"


def test_crew_registry_exists():
    assert REGISTRY.exists(), "crews/crew_registry.yaml must exist"


def test_crew_registry_valid_yaml():
    parsed = yaml.safe_load(REGISTRY.read_text())
    assert "phase_crews" in parsed
    assert "validation_crews" in parsed
    assert "governance_crews" in parsed


def test_crew_registry_phase_crews_have_primary():
    parsed = yaml.safe_load(REGISTRY.read_text())
    for phase, config in parsed["phase_crews"].items():
        assert "primary" in config, f"{phase} missing primary crew"
        primary_path = Path(config["primary"])
        assert primary_path.exists(), (
            f"Primary crew file missing: {primary_path}"
        )


def test_all_crew_yamls_valid_structure():
    for yaml_file in CREWS_DIR.rglob("*.yaml"):
        if yaml_file.name == "crew_registry.yaml":
            continue
        parsed = yaml.safe_load(yaml_file.read_text())
        assert "framework" in parsed, (
            f"{yaml_file} missing framework field"
        )
        assert "roles" in parsed, f"{yaml_file} missing roles field"
        assert parsed["framework"] in (
            "crewai",
            "autogen",
            "praisonai",
        ), f"{yaml_file} invalid framework value"


def test_all_roles_have_required_fields():
    for yaml_file in CREWS_DIR.rglob("*.yaml"):
        if yaml_file.name == "crew_registry.yaml":
            continue
        parsed = yaml.safe_load(yaml_file.read_text())
        for role_key, role_def in parsed.get("roles", {}).items():
            assert "role" in role_def, (
                f"{yaml_file}/{role_key} missing role"
            )
            assert "goal" in role_def, (
                f"{yaml_file}/{role_key} missing goal"
            )
            assert "backstory" in role_def, (
                f"{yaml_file}/{role_key} missing backstory"
            )
            assert "tasks" in role_def, (
                f"{yaml_file}/{role_key} missing tasks"
            )
            for task_key, task_def in (
                role_def["tasks"].items()
            ):
                assert "description" in task_def, (
                    f"{yaml_file}/{role_key}/{task_key} "
                    f"missing description"
                )
                assert "expected_output" in task_def, (
                    f"{yaml_file}/{role_key}/{task_key} "
                    f"missing expected_output"
                )


def test_recon_primary_crew_has_three_roles():
    crew = Path("crews/recon/primary_recon_crew.yaml")
    assert crew.exists()
    parsed = yaml.safe_load(crew.read_text())
    assert parsed["framework"] == "crewai"
    assert len(parsed["roles"]) == 3
    role_keys = list(parsed["roles"].keys())
    assert "scout" in role_keys
    assert "mapper" in role_keys
    assert "validator" in role_keys


def test_autogen_finding_review_has_two_roles():
    crew = Path(
        "crews/autogen/finding_review_conversation.yaml"
    )
    assert crew.exists()
    parsed = yaml.safe_load(crew.read_text())
    assert parsed["framework"] == "autogen"
    assert "hunter_agent" in parsed["roles"]
    assert "skeptic_agent" in parsed["roles"]


def test_autogen_severity_crew_has_two_roles():
    crew = Path("crews/autogen/severity_consensus.yaml")
    assert crew.exists()
    parsed = yaml.safe_load(crew.read_text())
    assert parsed["framework"] == "autogen"
    assert len(parsed["roles"]) == 2


def test_crew_yaml_runner_importable():
    from core.crew_yaml_runner import (
        get_crew_for_phase,
        list_all_crews,
        run_crew_yaml,
        run_validation_crews,
    )

    assert callable(run_crew_yaml)
    assert callable(get_crew_for_phase)
    assert callable(list_all_crews)
    assert callable(run_validation_crews)


def test_list_all_crews_returns_list():
    from core.crew_yaml_runner import list_all_crews

    crews = list_all_crews()
    assert isinstance(crews, list)
    assert len(crews) >= 11, (
        f"Expected at least 11 crews, got {len(crews)}"
    )


def test_get_crew_for_phase_returns_path():
    from core.crew_yaml_runner import get_crew_for_phase

    path = get_crew_for_phase("phase_1_2_recon")
    assert path is not None
    assert Path(path).exists()


def test_run_crew_yaml_handles_missing_file():
    from core.crew_yaml_runner import run_crew_yaml

    result = run_crew_yaml("crews/nonexistent_crew.yaml")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_crew_count_by_framework():
    crewai_count = 0
    autogen_count = 0
    for yaml_file in CREWS_DIR.rglob("*.yaml"):
        if yaml_file.name == "crew_registry.yaml":
            continue
        parsed = yaml.safe_load(yaml_file.read_text())
        if parsed.get("framework") == "crewai":
            crewai_count += 1
        elif parsed.get("framework") == "autogen":
            autogen_count += 1
    assert crewai_count >= 9, (
        f"Expected 9+ CrewAI crews, got {crewai_count}"
    )
    assert autogen_count >= 2, (
        f"Expected 2+ AutoGen crews, got {autogen_count}"
    )
