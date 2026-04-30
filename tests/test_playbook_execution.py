from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

KAI_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_SCHEMA_PATH = KAI_ROOT / "tools" / "playbooks" / "playbook_schema.yaml"
PLAYBOOK_REGISTRY_PATH = KAI_ROOT / "tools" / "playbooks" / "playbook_registry.yaml"
PLAYBOOK_EXECUTOR_CONFIG_PATH = KAI_ROOT / "tools" / "playbooks" / "playbook_executor_config.yaml"
TOOL_REGISTRY_PATH = KAI_ROOT / "tools" / "registry" / "tool_registry.yaml"
PERSONA_REGISTRY_PATH = KAI_ROOT / "personas" / "persona_registry.json"

PLAYBOOK_PATHS = [
    KAI_ROOT / "tools" / "playbooks" / "reconnaissance" / "web_app_recon.yaml",
    KAI_ROOT / "tools" / "playbooks" / "exploitation" / "sql_injection.yaml",
    KAI_ROOT / "tools" / "playbooks" / "exploitation" / "xss_discovery.yaml",
    KAI_ROOT / "tools" / "playbooks" / "exploitation" / "auth_bypass.yaml",
    KAI_ROOT / "tools" / "playbooks" / "exploitation" / "graphql_attacks.yaml",
]


@dataclass
class PlaybookExecutor:
    config: dict[str, Any]
    playbooks: dict[str, dict[str, Any]]

    def assign_persona(self, playbook_key: str, step_number: int) -> str:
        return self.config["playbooks"][playbook_key]["persona_assignments"][
            f"step_{step_number}"
        ]["assigned_persona"]

    def resolve_step_tool(self, playbook_key: str, step_number: int) -> str:
        return self.config["playbooks"][playbook_key]["persona_assignments"][
            f"step_{step_number}"
        ]["tool"]

    def simulate_execution(self, playbook_key: str) -> list[dict[str, Any]]:
        cfg = self.config["playbooks"][playbook_key]
        steps = cfg["execution_flow"]["sequential"]
        events: list[dict[str, Any]] = []
        for step in steps:
            events.append(
                {
                    "step": step,
                    "persona": self.assign_persona(playbook_key, step),
                    "tool": self.resolve_step_tool(playbook_key, step),
                }
            )
        return events


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_playbook(path: Path) -> dict[str, Any]:
    data = _load_yaml(path)
    return data["playbook"]


def _playbook_key_for_path(path: Path) -> str:
    stem = path.stem
    if stem == "web_app_recon":
        return "web_app_recon"
    return stem


@pytest.fixture(scope="module")
def playbooks() -> dict[str, dict[str, Any]]:
    return {p.stem: _load_playbook(p) for p in PLAYBOOK_PATHS}


@pytest.fixture(scope="module")
def persona_ids() -> set[str]:
    raw = json.loads(PERSONA_REGISTRY_PATH.read_text(encoding="utf-8"))
    return {item["persona_id"] for item in raw.get("personas", [])}


@pytest.fixture(scope="module")
def tool_names() -> set[str]:
    data = _load_yaml(TOOL_REGISTRY_PATH)
    return {item["name"] for item in data.get("tools", [])}


@pytest.fixture(scope="module")
def executor_config() -> dict[str, Any]:
    return _load_yaml(PLAYBOOK_EXECUTOR_CONFIG_PATH)["executor_config"]


def test_playbook_schema_validation() -> None:
    """Verify all playbooks conform to schema."""
    assert PLAYBOOK_SCHEMA_PATH.exists()
    schema = _load_yaml(PLAYBOOK_SCHEMA_PATH)
    top = schema.get("playbook_schema", {})
    assert top.get("id")
    assert top.get("safety_baseline", {}).get("authorized_only") is True
    required = top.get("playbook_contract", {}).get("required_sections", [])
    assert set(required) == {
        "metadata",
        "objective",
        "constraints",
        "required_tools",
        "steps",
        "decision_branches",
        "reporting",
    }


def test_all_requested_playbooks_exist() -> None:
    for p in PLAYBOOK_PATHS:
        assert p.exists(), f"Missing playbook: {p}"


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_playbook_has_required_top_sections(playbook_path: Path) -> None:
    playbook = _load_playbook(playbook_path)
    for key in (
        "metadata",
        "objective",
        "constraints",
        "required_tools",
        "steps",
        "decision_branches",
        "reporting",
    ):
        assert key in playbook, f"{playbook_path} missing {key}"


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_playbook_metadata_fields(playbook_path: Path) -> None:
    playbook = _load_playbook(playbook_path)
    metadata = playbook["metadata"]
    required = {
        "name",
        "id",
        "version",
        "author",
        "created",
        "description",
        "target_environment",
        "complexity",
        "duration_minutes",
        "phases_enabled",
        "prerequisites",
    }
    assert required.issubset(set(metadata))


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_playbook_objective_fields(playbook_path: Path) -> None:
    playbook = _load_playbook(playbook_path)
    objective = playbook["objective"]
    assert "primary" in objective
    assert "secondary" in objective and isinstance(objective["secondary"], list)
    assert "success_criteria" in objective and isinstance(
        objective["success_criteria"], list
    )


def test_playbook_registry_completeness() -> None:
    """Verify all playbooks are registered."""
    registry = _load_yaml(PLAYBOOK_REGISTRY_PATH)["playbook_registry"]
    registered_paths = {entry["path"] for entry in registry["playbooks"] if "path" in entry}
    expected_paths = {str(p.relative_to(KAI_ROOT)) for p in PLAYBOOK_PATHS}
    assert expected_paths.issubset(registered_paths)


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_playbook_step_sequencing(playbook_path: Path) -> None:
    """Verify step sequences are logical and complete."""
    playbook = _load_playbook(playbook_path)
    step_ids = [s["step_id"] for s in playbook["steps"]]
    assert step_ids == sorted(step_ids)
    assert step_ids == list(range(1, len(step_ids) + 1))


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_step_persona_count(playbook_path: Path) -> None:
    playbook = _load_playbook(playbook_path)
    for step in playbook["steps"]:
        personas = step["executor"]["personas"]
        assert 2 <= len(personas) <= 4


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_step_transition_handlers(playbook_path: Path) -> None:
    playbook = _load_playbook(playbook_path)
    for step in playbook["steps"]:
        if "on_success" in step:
            assert "message" in step["on_success"]
            assert "next_step" in step["on_success"]
        if "on_failure" in step:
            assert "message" in step["on_failure"]
            assert "next_step" in step["on_failure"]


def test_persona_assignments_valid(
    playbooks: dict[str, dict[str, Any]],
    persona_ids: set[str],
    executor_config: dict[str, Any],
) -> None:
    """Verify assigned personas exist in persona registry."""
    referenced: set[str] = set()

    for playbook in playbooks.values():
        for step in playbook["steps"]:
            referenced.update(step["executor"]["personas"])
            referenced.add(step["executor"]["primary_persona"])
        for branch in playbook.get("decision_branches", []):
            referenced.update(branch.get("personas", []))

    for cfg in executor_config["playbooks"].values():
        for step_cfg in cfg["persona_assignments"].values():
            referenced.add(step_cfg["assigned_persona"])
            referenced.add(step_cfg["fallback_persona"])
            referenced.update(step_cfg.get("support_personas", []))

    missing = sorted(referenced - persona_ids)
    assert not missing, f"Unknown personas: {missing}"


def test_tool_references_valid(
    playbooks: dict[str, dict[str, Any]],
    tool_names: set[str],
    executor_config: dict[str, Any],
) -> None:
    """Verify tools referenced exist in tool registry."""
    allow = {"none"}
    referenced: set[str] = set()

    for playbook in playbooks.values():
        for t in playbook["required_tools"]:
            referenced.add(t["name"])
        for step in playbook["steps"]:
            referenced.add(step["tool_usage"]["tool_name"])

    for cfg in executor_config["playbooks"].values():
        for step_cfg in cfg["persona_assignments"].values():
            referenced.add(step_cfg["tool"])

    missing = sorted(referenced - tool_names - allow)
    assert not missing, f"Unknown tools: {missing}"


def test_decision_branch_conditions(playbooks: dict[str, dict[str, Any]]) -> None:
    """Verify decision conditions are valid."""
    for name, playbook in playbooks.items():
        branches = playbook["decision_branches"]
        assert branches, f"{name} missing decision branches"
        for branch in branches:
            assert branch.get("condition")
            assert branch.get("action")
            assert isinstance(branch.get("personas", []), list)
            assert len(branch.get("personas", [])) >= 2


def test_playbook_executor_initialization(
    playbooks: dict[str, dict[str, Any]], executor_config: dict[str, Any]
) -> None:
    """Verify PlaybookExecutor initializes correctly."""
    executor = PlaybookExecutor(config=executor_config, playbooks=playbooks)
    assert executor is not None
    assert executor.config["executor_defaults"]["enforce_scope_guardrails"] is True


def test_persona_executor_assignment(executor_config: dict[str, Any], persona_ids: set[str]) -> None:
    """Verify personas are correctly assigned to steps."""
    for cfg in executor_config["playbooks"].values():
        for step, assignment in cfg["persona_assignments"].items():
            assert step.startswith("step_")
            assert assignment["assigned_persona"] in persona_ids
            assert assignment["fallback_persona"] in persona_ids


def test_tool_execution_through_playbook(
    playbooks: dict[str, dict[str, Any]], executor_config: dict[str, Any]
) -> None:
    """Simulate playbook execution, verify tool invocation."""
    executor = PlaybookExecutor(config=executor_config, playbooks=playbooks)
    for playbook_key in executor_config["playbooks"]:
        events = executor.simulate_execution(playbook_key)
        assert len(events) >= 2
        assert all("persona" in e and "tool" in e for e in events)


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_playbook_output_format(playbook_path: Path) -> None:
    """Verify playbook output matches expected format."""
    playbook = _load_playbook(playbook_path)
    for step in playbook["steps"]:
        expected = step.get("expected_output", {})
        assert "findings" in expected or "report" in expected


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_playbook_reporting_structure(playbook_path: Path) -> None:
    """Verify reporting section produces valid reports."""
    reporting = _load_playbook(playbook_path)["reporting"]
    assert isinstance(reporting.get("findings_to_include", []), list)
    assert reporting.get("severity_aggregation")
    assert reporting.get("template")
    assert isinstance(reporting.get("output_destinations", []), list)


def test_decision_branch_execution(
    playbooks: dict[str, dict[str, Any]], executor_config: dict[str, Any]
) -> None:
    """Test decision branches switch playbooks correctly."""
    known_targets = set(executor_config["playbooks"].keys())
    for playbook in playbooks.values():
        for branch in playbook["decision_branches"]:
            action = branch["action"]
            if "switch_to_" in action:
                target = action.split("switch_to_")[-1]
                assert target in known_targets


def test_executor_flow_matches_step_count(
    playbooks: dict[str, dict[str, Any]], executor_config: dict[str, Any]
) -> None:
    for path in PLAYBOOK_PATHS:
        key = _playbook_key_for_path(path)
        step_count = len(_load_playbook(path)["steps"])
        seq = executor_config["playbooks"][key]["execution_flow"]["sequential"]
        assert len(seq) == step_count
        assert seq == list(range(1, step_count + 1))


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_required_tools_cover_step_tools(playbook_path: Path) -> None:
    playbook = _load_playbook(playbook_path)
    required = {t["name"] for t in playbook["required_tools"]}
    used = {s["tool_usage"]["tool_name"] for s in playbook["steps"]}
    assert used - {"none"} <= required


@pytest.mark.parametrize("playbook_path", PLAYBOOK_PATHS)
def test_safety_guardrails_present(playbook_path: Path) -> None:
    playbook = _load_playbook(playbook_path)
    constraints = "\n".join(playbook.get("constraints", []))
    assert "Authorized scope" in constraints
    assert any("No " in c for c in playbook.get("constraints", []))
    for step in playbook["steps"]:
        notes = step["tool_usage"].get("safety_notes", [])
        assert isinstance(notes, list)
        assert len(notes) >= 1


def test_executor_config_paths_exist(executor_config: dict[str, Any]) -> None:
    for cfg in executor_config["playbooks"].values():
        path = KAI_ROOT / cfg["path"]
        assert path.exists(), f"Executor path missing: {path}"
