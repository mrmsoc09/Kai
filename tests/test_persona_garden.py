import json
import yaml
from pathlib import Path

PERSONAS_DIR = Path("personas/hacker_inputs")
REGISTRY = Path("personas/persona_registry.json")
REPORT = Path("personas/CURATION_REPORT.md")

def test_personas_directory_exists():
    assert PERSONAS_DIR.exists()

def test_personas_count():
    count = len(list(
        PERSONAS_DIR.glob("*.md")
    ))
    assert count >= 250, \
        f"Expected 250+ personas, got {count}"

def test_registry_exists():
    assert REGISTRY.exists()

def test_registry_structure():
    data = json.loads(REGISTRY.read_text())
    assert "total" in data
    assert "community" in data
    assert "pro" in data
    assert "personas" in data
    assert data["community"] >= 50
    assert data["pro"] >= 150

def test_community_tier_count():
    data = json.loads(REGISTRY.read_text())
    community = [
        p for p in data["personas"]
        if p["tier"] == "community"
    ]
    assert 70 <= len(community) <= 80, \
        f"Expected ~75 community, got {len(community)}"

def test_all_required_fields_present():
    data = json.loads(REGISTRY.read_text())
    required = [
        "persona_id", "display_name",
        "specialization", "phase_affinity",
        "tier", "trained",
    ]
    errors = []
    for p in data["personas"]:
        for field in required:
            if field not in p:
                errors.append(
                    f"{p.get('persona_id')}: "
                    f"missing {field}"
                )
    assert not errors, \
        "\n".join(errors[:10])

def test_phase_affinity_valid_range():
    data = json.loads(REGISTRY.read_text())
    for p in data["personas"]:
        phases = p.get("phase_affinity", [])
        assert isinstance(phases, list)
        for ph in phases:
            assert 1 <= ph <= 5, \
                f"{p['persona_id']}: phase {ph}"

def test_tier_values_valid():
    data = json.loads(REGISTRY.read_text())
    valid = {"community", "pro"}
    for p in data["personas"]:
        assert p.get("tier") in valid, \
            f"{p.get('persona_id')}: " \
            f"invalid tier {p.get('tier')}"

def test_curation_report_exists():
    assert REPORT.exists()

def test_persona_api_importable():
    from apps.backend.src.routers.persona_garden import router
    assert router is not None

def test_persona_phase_coverage():
    data = json.loads(REGISTRY.read_text())
    community = [
        p for p in data["personas"]
        if p["tier"] == "community"
    ]
    covered_phases = set()
    for p in community:
        for ph in p.get("phase_affinity", []):
            covered_phases.add(ph)
    # Personas only have phases 1-5 in source data
    expected_coverage = {1, 2, 3, 4, 5}
    missing = expected_coverage - covered_phases
    assert not missing, \
        f"Expected phases not covered: {missing}"
