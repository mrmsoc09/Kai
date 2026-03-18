"""
Tests for Simulation Mode Integration
========================================
Covers:
  1. graph_only mode executes real graph topology deterministically
  2. graph_only mode never invokes live tools or live models
  3. tool_mock mode uses mocked tools and preserves governance
  4. replay mode uses replay source rather than live execution
  5. state reducers behave correctly in all simulation modes
  6. approval and interrupt behavior still works in simulation
  7. DeepAgents simulation preserves telemetry and contract lineage
  8. LangSmith tagging/correlation works for simulation and replay
  9. artifacts are clearly marked as simulation or replay generated
  10. missing fixtures fail safely when configured to do so
  11. regression suite still passes

All tests are self-contained — no external services required.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# -- Import targets (config) ---------------------------------------------------

from apps.backend.src.core.praison_simulation_config import (
    ArtifactPolicy,
    EventVerbosity,
    FixtureStrictness,
    SimulationConfig,
    SimulationMode,
    load_simulation_config_from_env,
    make_graph_only_config,
    make_replay_config,
    make_tool_mock_config,
)

# -- Import targets (fixtures) -------------------------------------------------

from apps.backend.src.core.praison_simulation_fixtures import (
    SCENARIO_PACKS,
    FixtureProvenance,
    FixtureRegistry,
    fixture_evidence_analysis,
    fixture_governance_admission,
    fixture_governance_review,
    fixture_handoff_liaison,
    fixture_mission_director,
    fixture_phase_coordinator,
    fixture_report_synthesis,
    fixture_specialist_cluster,
    fixture_specialist_output,
    fixture_tool_result,
)

# -- Import targets (simulation core) -----------------------------------------

from apps.backend.src.core.praison_simulation import (
    SIMULATION_EVENT_TYPES,
    SimulationRunner,
    assert_simulation_safe,
    build_simulation_node_callables,
    get_simulation_langsmith_metadata,
    get_simulation_langsmith_tags,
    is_live_sandbox_blocked,
    is_live_tool_blocked,
    make_simulation_node_executor,
)

# -- Import targets (replay) --------------------------------------------------

from apps.backend.src.core.praison_replay import (
    ReplayEngine,
    ReplayResult,
    ReplayTimelineEntry,
    load_replay_node_state,
    replay_mission,
)

# -- Import targets (event bus for verification) -------------------------------

from apps.backend.src.core.praison_execution_events import EventBus, MissionEvent


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def graph_only_config():
    return make_graph_only_config()


@pytest.fixture
def graph_only_config_seeded():
    return make_graph_only_config(deterministic_seed=42)


@pytest.fixture
def tool_mock_config():
    return make_tool_mock_config()


@pytest.fixture
def tool_mock_config_no_reasoning():
    return make_tool_mock_config(allow_model_reasoning=False)


@pytest.fixture
def replay_config():
    return make_replay_config(replay_mission_id="m-replay-source-001")


@pytest.fixture
def high_signal_config():
    return make_graph_only_config(
        fixture_profile="high_signal",
        scenario_pack="high_signal",
    )


@pytest.fixture
def approval_heavy_config():
    return make_graph_only_config(scenario_pack="approval_heavy")


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def sample_state():
    return {
        "mission_id": "m-sim-test-001",
        "workflow_id": "wf-sim-test-001",
        "program_id": "prog-sim-test-001",
        "phase": "recon",
        "execution_mode": "graph_only",
        "active_node": "",
        "progress": 0.0,
        "error": "",
        "completed": False,
    }


@pytest.fixture
def replay_artifacts_dir():
    """Create a temporary artifacts directory with mock replay events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_dir = Path(tmpdir) / "telemetry"
        telemetry_dir.mkdir(parents=True)
        events_file = telemetry_dir / "mission_events.jsonl"

        mission_id = "m-replay-001"
        events = [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "mission_started",
                "timestamp": "2026-03-17T10:00:00+00:00",
                "mission_id": mission_id,
                "workflow_id": "wf-001",
                "program_id": "prog-001",
                "detail": {"execution_mode": "live", "mission_name": "Test Replay"},
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "node_entered",
                "timestamp": "2026-03-17T10:00:01+00:00",
                "mission_id": mission_id,
                "node_id": "GovernanceDirector",
                "phase": "governance",
                "detail": {},
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "node_completed",
                "timestamp": "2026-03-17T10:00:02+00:00",
                "mission_id": mission_id,
                "node_id": "GovernanceDirector",
                "phase": "governance",
                "detail": {"artifact_ids": []},
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "node_completed",
                "timestamp": "2026-03-17T10:00:05+00:00",
                "mission_id": mission_id,
                "node_id": "MissionDirector",
                "phase": "recon",
                "detail": {"artifact_ids": []},
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "phase_transition",
                "timestamp": "2026-03-17T10:00:06+00:00",
                "mission_id": mission_id,
                "phase": "recon",
                "detail": {"from_phase": "governance", "to_phase": "recon"},
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "mission_completed",
                "timestamp": "2026-03-17T10:01:00+00:00",
                "mission_id": mission_id,
                "detail": {"success": True, "final_report_id": "rpt-001"},
            },
        ]

        with events_file.open("w") as fh:
            for event in events:
                fh.write(json.dumps(event) + "\n")

        yield tmpdir, mission_id


# ===========================================================================
# Test SimulationMode Enum
# ===========================================================================


class TestSimulationMode:
    """Tests for SimulationMode enum properties."""

    def test_live_is_not_simulation(self):
        assert SimulationMode.LIVE.is_simulation is False

    def test_graph_only_is_simulation(self):
        assert SimulationMode.GRAPH_ONLY.is_simulation is True

    def test_tool_mock_is_simulation(self):
        assert SimulationMode.TOOL_MOCK.is_simulation is True

    def test_replay_is_simulation(self):
        assert SimulationMode.REPLAY.is_simulation is True

    def test_live_allows_live_tools(self):
        assert SimulationMode.LIVE.allows_live_tools is True

    def test_simulation_blocks_live_tools(self):
        for mode in (SimulationMode.GRAPH_ONLY, SimulationMode.TOOL_MOCK, SimulationMode.REPLAY):
            assert mode.allows_live_tools is False, f"{mode} should block live tools"

    def test_graph_only_blocks_live_models(self):
        assert SimulationMode.GRAPH_ONLY.allows_live_models is False

    def test_tool_mock_allows_live_models(self):
        assert SimulationMode.TOOL_MOCK.allows_live_models is True

    def test_replay_blocks_live_models(self):
        assert SimulationMode.REPLAY.allows_live_models is False

    def test_uses_fixtures(self):
        assert SimulationMode.GRAPH_ONLY.uses_fixtures is True
        assert SimulationMode.TOOL_MOCK.uses_fixtures is True
        assert SimulationMode.LIVE.uses_fixtures is False
        assert SimulationMode.REPLAY.uses_fixtures is False

    def test_uses_replay_source(self):
        assert SimulationMode.REPLAY.uses_replay_source is True
        assert SimulationMode.LIVE.uses_replay_source is False


# ===========================================================================
# Test SimulationConfig
# ===========================================================================


class TestSimulationConfig:
    """Tests for SimulationConfig dataclass."""

    def test_default_is_live(self):
        cfg = SimulationConfig()
        assert cfg.mode == SimulationMode.LIVE
        assert cfg.is_simulation is False

    def test_graph_only_factory(self):
        cfg = make_graph_only_config(fixture_profile="high_signal", deterministic_seed=42)
        assert cfg.mode == SimulationMode.GRAPH_ONLY
        assert cfg.fixture_profile == "high_signal"
        assert cfg.deterministic_seed == 42
        assert cfg.is_simulation is True

    def test_tool_mock_factory(self):
        cfg = make_tool_mock_config(allow_model_reasoning=False)
        assert cfg.mode == SimulationMode.TOOL_MOCK
        assert cfg.allow_model_reasoning_in_tool_mock is False

    def test_replay_factory(self):
        cfg = make_replay_config(replay_mission_id="m-123")
        assert cfg.mode == SimulationMode.REPLAY
        assert cfg.replay_mission_id == "m-123"

    def test_hard_block_live_tools(self):
        cfg = SimulationConfig(mode=SimulationMode.GRAPH_ONLY, hard_block_live_tools=True)
        assert cfg.allows_live_tools is False

    def test_to_metadata(self, graph_only_config_seeded):
        meta = graph_only_config_seeded.to_metadata()
        assert meta["simulation_mode"] == "graph_only"
        assert meta["deterministic_seed"] == 42
        assert meta["is_simulation"] is True

    def test_to_state_fields(self, graph_only_config):
        fields = graph_only_config.to_state_fields()
        assert fields["execution_mode"] == "graph_only"
        assert "_simulation_config" in fields

    def test_load_from_env_defaults_to_live(self):
        with patch.dict(os.environ, {"K1_SIMULATION_MODE": ""}, clear=False):
            # Remove the env var
            env = {k: v for k, v in os.environ.items() if k != "K1_SIMULATION_MODE"}
            with patch.dict(os.environ, env, clear=True):
                cfg = load_simulation_config_from_env()
                assert cfg.mode == SimulationMode.LIVE

    def test_load_from_env_graph_only(self):
        env = {"K1_SIMULATION_MODE": "graph_only"}
        with patch.dict(os.environ, env, clear=False):
            cfg = load_simulation_config_from_env()
            assert cfg.mode == SimulationMode.GRAPH_ONLY

    def test_comparison_metadata(self):
        cfg = SimulationConfig(
            mode=SimulationMode.GRAPH_ONLY,
            strategy_comparison_mode=True,
            comparison_label="variant_a",
        )
        meta = cfg.to_metadata()
        assert meta["strategy_comparison"] is True
        assert meta["comparison_label"] == "variant_a"


# ===========================================================================
# Test Safety Barriers
# ===========================================================================


class TestSafetyBarriers:
    """Tests for simulation safety enforcement."""

    def test_assert_safe_live_passes(self):
        assert_simulation_safe(SimulationConfig())  # No exception

    def test_assert_safe_graph_only_passes(self, graph_only_config):
        assert_simulation_safe(graph_only_config)  # No exception

    def test_is_live_tool_blocked_in_graph_only(self, graph_only_config):
        assert is_live_tool_blocked(graph_only_config, "nmap") is True

    def test_is_live_tool_blocked_in_tool_mock(self, tool_mock_config):
        assert is_live_tool_blocked(tool_mock_config, "nmap") is True

    def test_is_live_tool_blocked_in_replay(self, replay_config):
        assert is_live_tool_blocked(replay_config, "nuclei") is True

    def test_is_live_tool_not_blocked_in_live(self):
        cfg = SimulationConfig()  # Live
        assert is_live_tool_blocked(cfg, "nmap") is False

    def test_is_live_tool_not_blocked_none_config(self):
        assert is_live_tool_blocked(None, "nmap") is False

    def test_is_live_sandbox_blocked(self, graph_only_config):
        assert is_live_sandbox_blocked(graph_only_config) is True

    def test_is_live_sandbox_not_blocked_live(self):
        assert is_live_sandbox_blocked(SimulationConfig()) is False

    def test_is_live_sandbox_not_blocked_none(self):
        assert is_live_sandbox_blocked(None) is False


# ===========================================================================
# Test Fixture Provenance
# ===========================================================================


class TestFixtureProvenance:
    """Tests for fixture provenance tracking."""

    def test_provenance_to_dict(self):
        prov = FixtureProvenance(
            fixture_id="fix-abc",
            fixture_type="tool_result",
            profile="default",
            tool_name="nmap",
        )
        d = prov.to_dict()
        assert d["fixture_id"] == "fix-abc"
        assert d["fixture_type"] == "tool_result"
        assert d["source"] == "simulation_fixture"
        assert d["tool_name"] == "nmap"

    def test_provenance_excludes_empty(self):
        prov = FixtureProvenance(
            fixture_id="fix-1",
            fixture_type="node_output",
            profile="default",
        )
        d = prov.to_dict()
        assert "tool_name" not in d
        assert "specialist_type" not in d


# ===========================================================================
# Test Node Output Fixtures
# ===========================================================================


class TestNodeFixtures:
    """Tests for deterministic node output fixtures."""

    def test_governance_admission_default(self):
        result = fixture_governance_admission()
        assert result["governance_decision"] == "approved"
        assert result["phase"] == "governance"
        assert len(result["policy_events"]) == 1

    def test_governance_admission_blocked(self):
        result = fixture_governance_admission(scenario_pack="blocked_mission")
        assert result["governance_decision"] == "blocked"

    def test_mission_director(self):
        result = fixture_mission_director()
        assert result["phase"] == "recon"
        assert result["phase_complete"] is False

    def test_phase_coordinator(self):
        result = fixture_phase_coordinator(phase_name="scanning")
        assert result["phase"] == "scanning"

    def test_specialist_cluster_surface_scan(self):
        result = fixture_specialist_cluster(cluster_name="surface_scan")
        assert "artifacts" in result
        assert "cluster_status" in result
        assert "surface_scan" in result["cluster_status"]
        assert result["last_artifact_type"] == "recon_surface"

    def test_specialist_cluster_high_signal(self):
        result = fixture_specialist_cluster(scenario_pack="high_signal")
        assert result["last_artifact_type"] == "vulnerability_signal"

    def test_evidence_analysis_default(self):
        result = fixture_evidence_analysis()
        assert len(result["findings"]) >= 1
        assert result["last_artifact_type"] == "recon_surface"

    def test_evidence_analysis_high_signal(self):
        result = fixture_evidence_analysis(scenario_pack="high_signal")
        assert any(f["severity"] in ("critical", "high") for f in result["findings"])
        assert result["last_artifact_type"] == "vulnerability_signal"

    def test_governance_review_approved(self):
        result = fixture_governance_review()
        assert result["governance_decision"] == "approved"
        assert len(result["approvals_required"]) == 0

    def test_governance_review_pending(self):
        result = fixture_governance_review(scenario_pack="approval_heavy")
        assert result["governance_decision"] == "pending"
        assert len(result["approvals_required"]) == 1

    def test_report_synthesis(self):
        result = fixture_report_synthesis()
        assert result["final_report_id"]
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["artifact_type"] == "final_report"

    def test_handoff_liaison(self):
        result = fixture_handoff_liaison()
        assert result["completed"] is True
        assert result["progress"] == 1.0

    def test_deterministic_with_seed(self):
        """Same seed produces same fixture IDs."""
        r1 = fixture_governance_admission(seed=42)
        r2 = fixture_governance_admission(seed=42)
        assert r1["policy_events"][0]["_fixture"]["fixture_id"] == \
               r2["policy_events"][0]["_fixture"]["fixture_id"]

    def test_different_seeds_differ(self):
        r1 = fixture_governance_admission(seed=1)
        r2 = fixture_governance_admission(seed=2)
        assert r1["policy_events"][0]["_fixture"]["fixture_id"] != \
               r2["policy_events"][0]["_fixture"]["fixture_id"]


# ===========================================================================
# Test Tool Result Fixtures
# ===========================================================================


class TestToolFixtures:
    """Tests for mock tool result fixtures."""

    def test_nmap_fixture(self):
        result = fixture_tool_result("nmap")
        assert result["tool_name"] == "nmap"
        assert result["success"] is True
        assert result["_simulation"] is True
        assert "structured_output" in result
        assert len(result["structured_output"]["hosts"][0]["ports"]) >= 3

    def test_nmap_high_signal(self):
        result = fixture_tool_result("nmap", scenario_pack="high_signal")
        ports = result["structured_output"]["hosts"][0]["ports"]
        port_numbers = [p["port"] for p in ports]
        assert 3306 in port_numbers  # MySQL

    def test_subfinder_fixture(self):
        result = fixture_tool_result("subfinder")
        assert "subdomains" in result["structured_output"]

    def test_nuclei_fixture(self):
        result = fixture_tool_result("nuclei")
        assert result["_simulation"] is True

    def test_unknown_tool_default(self):
        result = fixture_tool_result("unknown_tool_xyz")
        assert result["success"] is True
        assert "[SIMULATED]" in result["output"]

    def test_tool_fixture_has_provenance(self):
        result = fixture_tool_result("nmap")
        assert "_fixture" in result
        assert result["_fixture"]["fixture_type"] == "tool_result"
        assert result["_fixture"]["source"] == "simulation_fixture"


# ===========================================================================
# Test Specialist Output Fixtures
# ===========================================================================


class TestSpecialistFixtures:
    """Tests for mock specialist output fixtures."""

    def test_evidence_analyst(self):
        result = fixture_specialist_output("evidence_analyst")
        assert result["success"] is True
        assert "[SIMULATED]" in result["text"]
        assert "_fixture" in result

    def test_triage_specialist(self):
        result = fixture_specialist_output("triage_specialist")
        assert "severity" in result
        assert "confidence" in result

    def test_triage_specialist_high_signal(self):
        result = fixture_specialist_output("triage_specialist", scenario_pack="high_signal")
        assert result["severity"] == "high"

    def test_exploit_assessor(self):
        result = fixture_specialist_output("exploit_assessor")
        assert "exploitable" in result

    def test_report_synthesizer(self):
        result = fixture_specialist_output("report_synthesizer")
        assert len(result.get("artifacts_produced", [])) >= 1

    def test_unknown_specialist_default(self):
        result = fixture_specialist_output("unknown_specialist")
        assert result["success"] is True
        assert "[SIMULATED]" in result["text"]


# ===========================================================================
# Test FixtureRegistry
# ===========================================================================


class TestFixtureRegistry:
    """Tests for the FixtureRegistry."""

    def test_get_node_fixture_known(self):
        registry = FixtureRegistry()
        fixture = registry.get_node_fixture("GovernanceDirector")
        assert fixture["governance_decision"] == "approved"

    def test_get_node_fixture_unknown_lenient(self):
        registry = FixtureRegistry(strictness="lenient")
        fixture = registry.get_node_fixture("NonExistentNode")
        assert fixture.get("_fixture_missing") is True

    def test_get_node_fixture_unknown_strict(self):
        registry = FixtureRegistry(strictness="strict")
        with pytest.raises(KeyError, match="No fixture found"):
            registry.get_node_fixture("NonExistentNode")

    def test_get_tool_fixture(self):
        registry = FixtureRegistry()
        fixture = registry.get_tool_fixture("nmap")
        assert fixture["tool_name"] == "nmap"

    def test_get_specialist_fixture(self):
        registry = FixtureRegistry()
        fixture = registry.get_specialist_fixture("evidence_analyst")
        assert fixture["success"] is True

    def test_registry_passes_scenario(self):
        registry = FixtureRegistry(scenario_pack="high_signal")
        fixture = registry.get_node_fixture("EvidenceAnalyst")
        assert any(f["severity"] in ("critical", "high") for f in fixture["findings"])


# ===========================================================================
# Test Scenario Packs
# ===========================================================================


class TestScenarioPacks:
    """Tests for scenario pack definitions."""

    def test_all_packs_have_description(self):
        for name, pack in SCENARIO_PACKS.items():
            assert "description" in pack, f"Pack {name} missing description"
            assert "fixture_profile" in pack, f"Pack {name} missing fixture_profile"

    def test_expected_packs_exist(self):
        expected = {"default", "high_signal", "noisy_false_positive", "approval_heavy",
                    "blocked_mission", "exploit_heavy"}
        assert expected.issubset(set(SCENARIO_PACKS.keys()))


# ===========================================================================
# Test Simulation Node Executor — graph_only
# ===========================================================================


class TestGraphOnlyExecution:
    """Tests for graph_only simulation mode."""

    def test_graph_only_returns_fixture_state(self, graph_only_config, sample_state):
        executor = make_simulation_node_executor(
            "GovernanceDirector", graph_only_config
        )
        result = executor(sample_state)
        assert result["active_node"] == "GovernanceDirector"
        assert result["governance_decision"] == "approved"

    def test_graph_only_never_calls_inner(self, graph_only_config, sample_state):
        """Inner callable must NEVER be called in graph_only mode."""
        inner = MagicMock(side_effect=RuntimeError("SHOULD NOT BE CALLED"))
        executor = make_simulation_node_executor(
            "GovernanceDirector", graph_only_config, inner_callable=inner,
        )
        result = executor(sample_state)
        inner.assert_not_called()
        assert result["governance_decision"] == "approved"

    def test_graph_only_produces_node_history(self, graph_only_config, sample_state):
        executor = make_simulation_node_executor(
            "MissionDirector", graph_only_config
        )
        result = executor(sample_state)
        assert len(result["node_history"]) == 1
        assert result["node_history"][0]["node_id"] == "MissionDirector"
        assert result["node_history"][0]["_simulation"] is True

    def test_graph_only_tags_artifacts(self, graph_only_config, sample_state):
        executor = make_simulation_node_executor(
            "ReportSynthesisAgent", graph_only_config
        )
        result = executor(sample_state)
        for art in result.get("artifacts", []):
            assert art.get("_simulation") is True
            assert art.get("_simulation_mode") == "graph_only"

    def test_graph_only_deterministic_with_seed(self, sample_state):
        """Same seed produces identical outputs."""
        cfg1 = make_graph_only_config(deterministic_seed=42)
        cfg2 = make_graph_only_config(deterministic_seed=42)
        exec1 = make_simulation_node_executor("EvidenceAnalyst", cfg1)
        exec2 = make_simulation_node_executor("EvidenceAnalyst", cfg2)
        r1 = exec1(sample_state)
        r2 = exec2(sample_state)
        # Findings should have same fixture IDs
        assert r1["findings"][0]["finding_id"] == r2["findings"][0]["finding_id"]

    def test_graph_only_all_standard_nodes(self, graph_only_config, sample_state):
        """All standard nodes produce valid output in graph_only mode."""
        standard_nodes = [
            "GovernanceDirector", "MissionDirector", "PhaseCoordinator",
            "SurfaceMapper", "ReconSpecialist", "EvidenceAnalyst",
            "ReportSynthesisAgent", "HandoffLiaison",
        ]
        for node_id in standard_nodes:
            executor = make_simulation_node_executor(node_id, graph_only_config)
            result = executor(sample_state)
            assert result["active_node"] == node_id, f"Failed for {node_id}"
            assert len(result["node_history"]) >= 1, f"Missing history for {node_id}"


# ===========================================================================
# Test Simulation Node Executor — tool_mock
# ===========================================================================


class TestToolMockExecution:
    """Tests for tool_mock simulation mode."""

    def test_tool_mock_calls_inner_when_allowed(self, tool_mock_config, sample_state):
        """tool_mock calls inner callable when model reasoning is allowed."""
        inner = MagicMock(return_value={"findings": [{"severity": "high"}]})
        executor = make_simulation_node_executor(
            "EvidenceAnalyst", tool_mock_config, inner_callable=inner,
        )
        result = executor(sample_state)
        inner.assert_called_once()

    def test_tool_mock_no_reasoning_uses_fixture(self, tool_mock_config_no_reasoning, sample_state):
        """tool_mock without model reasoning uses fixtures."""
        inner = MagicMock(side_effect=RuntimeError("SHOULD NOT BE CALLED"))
        executor = make_simulation_node_executor(
            "EvidenceAnalyst", tool_mock_config_no_reasoning, inner_callable=inner,
        )
        result = executor(sample_state)
        inner.assert_not_called()
        assert result["active_node"] == "EvidenceAnalyst"

    def test_tool_mock_falls_back_on_inner_failure(self, tool_mock_config, sample_state):
        """tool_mock falls back to fixture if inner callable fails."""
        inner = MagicMock(side_effect=RuntimeError("Inner failed"))
        executor = make_simulation_node_executor(
            "GovernanceDirector", tool_mock_config, inner_callable=inner,
        )
        result = executor(sample_state)
        assert result["governance_decision"] == "approved"

    def test_tool_mock_preserves_inner_result_structure(self, tool_mock_config, sample_state):
        """tool_mock preserves the state update structure from inner callable."""
        inner_result = {
            "findings": [{"severity": "critical", "title": "Real finding"}],
            "artifacts": [{"artifact_id": "art-1", "artifact_type": "evidence"}],
        }
        inner = MagicMock(return_value=inner_result)
        executor = make_simulation_node_executor(
            "EvidenceAnalyst", tool_mock_config, inner_callable=inner,
        )
        result = executor(sample_state)
        assert result["findings"][0]["severity"] == "critical"
        # Artifacts should be tagged as simulation
        for art in result.get("artifacts", []):
            assert art.get("_simulation") is True


# ===========================================================================
# Test Simulation Node Executor — replay
# ===========================================================================


class TestReplayExecution:
    """Tests for replay simulation mode."""

    def test_replay_falls_back_to_fixture_without_data(self, sample_state):
        """Replay with no replay data falls back to fixture."""
        cfg = make_replay_config(replay_mission_id="nonexistent-mission")
        executor = make_simulation_node_executor("GovernanceDirector", cfg)
        result = executor(sample_state)
        # Should get fixture data as fallback
        assert result["active_node"] == "GovernanceDirector"

    def test_replay_uses_historical_data(self, sample_state, replay_artifacts_dir):
        """Replay uses persisted event data when available."""
        tmpdir, mission_id = replay_artifacts_dir
        cfg = make_replay_config(replay_mission_id=mission_id)

        # Patch the replay engine to use our temp dir
        with patch(
            "apps.backend.src.core.praison_simulation._load_replay_node_data"
        ) as mock_load:
            mock_load.return_value = {
                "governance_decision": "approved",
                "phase": "governance",
                "_replay": True,
            }
            executor = make_simulation_node_executor("GovernanceDirector", cfg)
            result = executor(sample_state)
            assert result.get("node_history", [{}])[0].get("_replay") is True


# ===========================================================================
# Test Simulation Callables Builder
# ===========================================================================


class TestBuildSimulationCallables:
    """Tests for build_simulation_node_callables."""

    def test_builds_all_standard_nodes(self, graph_only_config):
        callables = build_simulation_node_callables(graph_only_config)
        expected_nodes = {
            "GovernanceDirector", "MissionDirector", "PhaseCoordinator",
            "SurfaceMapper", "ReconSpecialist", "EvidenceAnalyst",
            "ReportSynthesisAgent", "HandoffLiaison",
        }
        assert expected_nodes.issubset(set(callables.keys()))

    def test_all_callables_are_callable(self, graph_only_config):
        callables = build_simulation_node_callables(graph_only_config)
        for node_id, fn in callables.items():
            assert callable(fn), f"{node_id} is not callable"


# ===========================================================================
# Test SimulationRunner
# ===========================================================================


class TestSimulationRunner:
    """Tests for SimulationRunner high-level orchestration."""

    def test_run_graph_only_simulation(self, graph_only_config):
        runner = SimulationRunner(config=graph_only_config)
        result = runner.run_simulation(
            workflow_id="wf-test",
            program_id="prog-test",
            mission_name="test-sim",
        )
        assert result.get("_simulation") is True
        assert result.get("_simulation_config", {}).get("simulation_mode") == "graph_only"
        # Mission should complete
        assert result.get("completed") is True
        assert result.get("progress") == 1.0

    def test_run_graph_only_high_signal(self, high_signal_config):
        runner = SimulationRunner(config=high_signal_config)
        result = runner.run_simulation(
            workflow_id="wf-hs",
            program_id="prog-hs",
        )
        assert result.get("_simulation") is True
        # Should have findings
        findings = result.get("findings", [])
        assert len(findings) > 0

    def test_run_graph_only_has_node_history(self, graph_only_config):
        runner = SimulationRunner(config=graph_only_config)
        result = runner.run_simulation(
            workflow_id="wf-hist",
            program_id="prog-hist",
        )
        history = result.get("node_history", [])
        assert len(history) >= 4  # At least governance → director → coordinator → ...

    def test_run_comparison(self):
        """Comparison run returns labeled results."""
        configs = [
            ("baseline", make_graph_only_config()),
            ("variant_a", make_graph_only_config(
                scenario_pack="high_signal",
                fixture_profile="high_signal",
            )),
        ]
        runner = SimulationRunner()
        results = runner.run_comparison(
            workflow_id="wf-cmp",
            program_id="prog-cmp",
            configs=configs,
        )
        assert "baseline" in results
        assert "variant_a" in results
        assert results["baseline"].get("_comparison_label") == "baseline"
        assert results["variant_a"].get("_comparison_label") == "variant_a"


# ===========================================================================
# Test Governance Fidelity in Simulation
# ===========================================================================


class TestGovernanceFidelity:
    """Tests that governance behavior is preserved in simulation."""

    def test_approval_fixture_in_approval_heavy(self, approval_heavy_config, sample_state):
        """Approval-heavy scenario generates approval requests."""
        executor = make_simulation_node_executor(
            "governance_review", approval_heavy_config
        )
        result = executor(sample_state)
        approvals = result.get("approvals_required", [])
        assert len(approvals) >= 1
        assert approvals[0]["reason"]

    def test_blocked_mission_scenario(self, sample_state):
        """Blocked mission scenario blocks at governance admission."""
        cfg = make_graph_only_config(scenario_pack="blocked_mission")
        executor = make_simulation_node_executor("GovernanceDirector", cfg)
        result = executor(sample_state)
        assert result["governance_decision"] == "blocked"


# ===========================================================================
# Test Artifact Simulation Tagging
# ===========================================================================


class TestArtifactTagging:
    """Tests that simulation artifacts carry proper provenance."""

    def test_artifacts_tagged_graph_only(self, graph_only_config, sample_state):
        executor = make_simulation_node_executor("ReportSynthesisAgent", graph_only_config)
        result = executor(sample_state)
        for art in result.get("artifacts", []):
            assert art["_simulation"] is True
            assert art["_simulation_mode"] == "graph_only"

    def test_artifacts_tagged_tool_mock(self, tool_mock_config, sample_state):
        # Use fixture fallback (no inner callable)
        executor = make_simulation_node_executor("ReportSynthesisAgent", tool_mock_config)
        result = executor(sample_state)
        for art in result.get("artifacts", []):
            assert art["_simulation"] is True

    def test_comparison_label_on_artifacts(self, sample_state):
        cfg = SimulationConfig(
            mode=SimulationMode.GRAPH_ONLY,
            comparison_label="variant_b",
        )
        executor = make_simulation_node_executor("ReportSynthesisAgent", cfg)
        result = executor(sample_state)
        for art in result.get("artifacts", []):
            assert art.get("_comparison_label") == "variant_b"


# ===========================================================================
# Test Replay Engine
# ===========================================================================


class TestReplayEngine:
    """Tests for the ReplayEngine."""

    def test_replay_from_events(self, replay_artifacts_dir):
        tmpdir, mission_id = replay_artifacts_dir
        engine = ReplayEngine(artifacts_root=tmpdir)
        result = engine.replay_mission(mission_id)

        assert result.success
        assert result.source_mission_id == mission_id
        assert result.source_type == "events"
        assert len(result.timeline) >= 4  # At least 4 events

    def test_replay_timeline_sorted(self, replay_artifacts_dir):
        tmpdir, mission_id = replay_artifacts_dir
        engine = ReplayEngine(artifacts_root=tmpdir)
        result = engine.replay_mission(mission_id)

        timestamps = [e.timestamp for e in result.timeline]
        assert timestamps == sorted(timestamps)

    def test_replay_extracts_node_states(self, replay_artifacts_dir):
        tmpdir, mission_id = replay_artifacts_dir
        engine = ReplayEngine(artifacts_root=tmpdir)
        result = engine.replay_mission(mission_id)

        assert "GovernanceDirector" in result.node_states
        assert "MissionDirector" in result.node_states
        for ns in result.node_states.values():
            assert ns.get("_replay") is True

    def test_replay_reconstructs_final_state(self, replay_artifacts_dir):
        tmpdir, mission_id = replay_artifacts_dir
        engine = ReplayEngine(artifacts_root=tmpdir)
        result = engine.replay_mission(mission_id)

        assert result.final_state.get("_replay") is True
        assert result.final_state.get("completed") is True
        assert result.final_state.get("final_report_id") == "rpt-001"

    def test_replay_nonexistent_mission(self):
        engine = ReplayEngine(artifacts_root="/tmp/nonexistent_replay_dir")
        result = engine.replay_mission("nonexistent")
        assert not result.success
        assert "No replay data" in result.error

    def test_replay_node_state_lookup(self, replay_artifacts_dir):
        tmpdir, mission_id = replay_artifacts_dir
        engine = ReplayEngine(artifacts_root=tmpdir)
        state = engine.get_replay_node_state(mission_id, "GovernanceDirector")
        assert state is not None
        assert state["_replay"] is True
        assert state["active_node"] == "GovernanceDirector"

    def test_replay_node_state_missing(self, replay_artifacts_dir):
        tmpdir, mission_id = replay_artifacts_dir
        engine = ReplayEngine(artifacts_root=tmpdir)
        state = engine.get_replay_node_state(mission_id, "NonExistentNode")
        assert state is None

    def test_replay_result_to_dict(self, replay_artifacts_dir):
        tmpdir, mission_id = replay_artifacts_dir
        engine = ReplayEngine(artifacts_root=tmpdir)
        result = engine.replay_mission(mission_id)
        d = result.to_dict()
        assert d["success"] is True
        assert d["source_type"] == "events"
        assert d["timeline_length"] >= 4


# ===========================================================================
# Test LangSmith Integration for Simulation
# ===========================================================================


class TestSimulationLangSmith:
    """Tests for LangSmith tagging and metadata in simulation."""

    def test_langsmith_tags_graph_only(self, graph_only_config):
        tags = get_simulation_langsmith_tags(graph_only_config)
        assert "simulation" in tags
        assert "sim_mode:graph_only" in tags

    def test_langsmith_tags_tool_mock(self, tool_mock_config):
        tags = get_simulation_langsmith_tags(tool_mock_config)
        assert "sim_mode:tool_mock" in tags

    def test_langsmith_tags_replay(self, replay_config):
        tags = get_simulation_langsmith_tags(replay_config)
        assert "sim_mode:replay" in tags

    def test_langsmith_tags_scenario(self):
        cfg = make_graph_only_config(scenario_pack="high_signal")
        tags = get_simulation_langsmith_tags(cfg)
        assert "scenario:high_signal" in tags

    def test_langsmith_tags_comparison(self):
        cfg = SimulationConfig(
            mode=SimulationMode.GRAPH_ONLY,
            comparison_label="baseline",
        )
        tags = get_simulation_langsmith_tags(cfg)
        assert "comparison:baseline" in tags

    def test_langsmith_metadata(self, graph_only_config):
        meta = get_simulation_langsmith_metadata(graph_only_config)
        assert meta["kai_is_simulation"] is True
        assert meta["simulation_mode"] == "graph_only"

    def test_langsmith_metadata_includes_config(self, graph_only_config_seeded):
        meta = get_simulation_langsmith_metadata(graph_only_config_seeded)
        assert meta["deterministic_seed"] == 42


# ===========================================================================
# Test Event Emission in Simulation
# ===========================================================================


class TestSimulationEvents:
    """Tests for simulation event emission."""

    def test_simulation_event_types_defined(self):
        """All expected simulation event types are defined."""
        expected = {
            "simulation_started", "simulation_completed", "simulation_failed",
            "replay_started", "replay_completed", "fixture_applied",
            "mock_tool_result_emitted",
        }
        assert expected.issubset(SIMULATION_EVENT_TYPES)

    def test_graph_only_emits_events(self, graph_only_config):
        """graph_only simulation emits events through EventBus."""
        bus = EventBus()
        events: list[MissionEvent] = []
        bus.subscribe(lambda e: events.append(e))

        # Patch the module-level event bus
        with patch("apps.backend.src.core.praison_simulation.emit") as mock_emit:
            executor = make_simulation_node_executor("GovernanceDirector", graph_only_config)
            executor({
                "mission_id": "m-evt", "workflow_id": "wf-evt",
                "program_id": "prog-evt", "phase": "governance",
                "execution_mode": "graph_only",
            })
            # Should emit fixture_applied and node events
            assert mock_emit.call_count >= 1

    def test_silent_verbosity_suppresses_events(self, sample_state):
        """SILENT event verbosity suppresses event emission."""
        cfg = SimulationConfig(
            mode=SimulationMode.GRAPH_ONLY,
            event_verbosity=EventVerbosity.SILENT,
        )
        with patch("apps.backend.src.core.praison_simulation.emit") as mock_emit:
            executor = make_simulation_node_executor("GovernanceDirector", cfg)
            executor(sample_state)
            # Should NOT emit node_entered/completed events (fixture_applied still emits)
            for call in mock_emit.call_args_list:
                event = call[0][0]
                assert event.event_type not in ("node_entered", "node_completed")


# ===========================================================================
# Test Missing Fixture Handling
# ===========================================================================


class TestMissingFixtures:
    """Tests for missing fixture behavior."""

    def test_strict_raises_on_missing(self):
        cfg = SimulationConfig(
            mode=SimulationMode.GRAPH_ONLY,
            fixture_strictness=FixtureStrictness.STRICT,
        )
        executor = make_simulation_node_executor("TotallyUnknownNode", cfg)
        with pytest.raises(KeyError, match="No fixture found"):
            executor({
                "mission_id": "m-1", "workflow_id": "wf-1",
                "program_id": "p-1", "phase": "", "execution_mode": "graph_only",
            })

    def test_lenient_returns_empty_on_missing(self, sample_state):
        cfg = SimulationConfig(
            mode=SimulationMode.GRAPH_ONLY,
            fixture_strictness=FixtureStrictness.LENIENT,
        )
        executor = make_simulation_node_executor("UnknownNode", cfg)
        result = executor(sample_state)
        assert result["active_node"] == "UnknownNode"


# ===========================================================================
# Test Full Mission Simulation (integration)
# ===========================================================================


class TestFullMissionSimulation:
    """Integration tests for complete mission simulation runs."""

    def test_full_graph_only_mission_completes(self):
        """A full graph_only mission runs from start to completion."""
        cfg = make_graph_only_config()
        runner = SimulationRunner(config=cfg)
        result = runner.run_simulation(
            workflow_id="wf-full",
            program_id="prog-full",
            mission_name="full-graph-only",
        )
        assert result["completed"] is True
        assert result["progress"] == 1.0
        assert result["_simulation"] is True

    def test_full_graph_only_produces_history(self):
        """Graph-only mission has node execution history."""
        cfg = make_graph_only_config()
        runner = SimulationRunner(config=cfg)
        result = runner.run_simulation(
            workflow_id="wf-hist2",
            program_id="prog-hist2",
        )
        history = result.get("node_history", [])
        # Should have entries for multiple nodes
        node_ids = [h["node_id"] for h in history]
        assert "GovernanceDirector" in node_ids or "governance_admission" in node_ids

    def test_full_tool_mock_mission_completes(self):
        """A full tool_mock mission with no inner callables uses fixtures."""
        cfg = make_tool_mock_config(allow_model_reasoning=False)
        runner = SimulationRunner(config=cfg)
        result = runner.run_simulation(
            workflow_id="wf-mock",
            program_id="prog-mock",
        )
        assert result["completed"] is True
        assert result["_simulation"] is True

    def test_full_high_signal_produces_findings(self):
        """High-signal scenario produces vulnerability findings."""
        cfg = make_graph_only_config(
            fixture_profile="high_signal",
            scenario_pack="high_signal",
        )
        runner = SimulationRunner(config=cfg)
        result = runner.run_simulation(
            workflow_id="wf-hs2",
            program_id="prog-hs2",
        )
        findings = result.get("findings", [])
        assert len(findings) > 0
        severities = [f.get("severity") for f in findings]
        assert any(s in ("critical", "high") for s in severities)

    def test_simulation_never_reaches_live_tools(self):
        """Verify simulation safety barrier prevents live tool execution."""
        cfg = make_graph_only_config()
        assert is_live_tool_blocked(cfg, "nmap") is True
        assert is_live_tool_blocked(cfg, "nuclei") is True
        assert is_live_sandbox_blocked(cfg) is True
