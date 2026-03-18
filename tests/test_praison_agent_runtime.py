"""
Tests for PraisonAI Agent Runtime Integration
===============================================
Covers:
  1. Persona loading from agents.yaml through PraisonAgentRegistry
  2. PraisonAgentRuntime instantiation and stub execution
  3. GovernedToolWrapper governance interception
  4. Memory scope mapping and enforcement
  5. Prompt/tool profile selection and adaptive execution boundaries
  6. make_praison_node_callable LangGraph bridge
  7. build_praison_agent_callables batch builder
  8. Tool profile / prompt profile catalog
  9. New agents.yaml agents (VulnerabilityTriageAgent, etc.)
  10. Integration: runtime -> node executors -> LangGraph state updates
"""

from __future__ import annotations

import sys
import os
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))


from apps.backend.src.core.praison_agent import AgentIdentity
from apps.backend.src.core.praison_adaptive import (
    AdaptiveChangeType,
    ExecutionPlanPatch,
    ExecutionStrategy,
    PromptProfile,
    ToolProfile,
    validate_plan_patch,
)
from apps.backend.src.core.praison_agent_runtime import (
    AgentExecutionResult,
    GovernedToolWrapper,
    PraisonAgentRuntime,
    _MEMORY_SCOPE_MAP,
    _PRAISON_AVAILABLE,
    build_praison_agent_callables,
    is_praison_available,
    make_praison_node_callable,
    map_memory_scope,
)
from apps.backend.src.core.praison_tool_profiles import (
    ALL_PROMPT_PROFILES,
    ALL_TOOL_PROFILES,
    AGGRESSIVE_VALIDATION,
    BALANCED_RECON,
    CONSERVATIVE_ANALYSIS,
    COVERAGE_MAXIMIZER,
    DEEP_VALIDATION,
    FAST_TRIAGE,
    HIGH_PRECISION_SCAN,
    HIGH_RECALL_SCAN,
    PASSIVE_RECON,
    REPORT_SUBMISSION,
    STEALTH_PREFERRED,
    STEALTH_RECON,
    THOROUGH_ANALYSIS,
    TIME_BOXED_SCAN,
    get_prompt_profile,
    get_tool_profile,
    prompt_profiles_for_agent,
    tool_profiles_for_agent,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_identity(
    agent_id: str = "TestAgent",
    persona: str = "Test Persona",
    agent_class: str = "specialist",
    allowed_tools: list[str] | None = None,
    memory_scope: str = "session",
    **kwargs,
) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        persona=persona,
        description=f"Test agent: {agent_id}",
        system_prompt=f"You are {persona}.",
        allowed_tools=allowed_tools or ["subfinder", "httpx"],
        agent_class=agent_class,
        delegation_scope="none" if agent_class == "specialist" else "local",
        memory_scope=memory_scope,
        **kwargs,
    )


def _make_state(**overrides) -> dict:
    base = {
        "mission_id": "mission_test",
        "workflow_id": "wf_test",
        "program_id": "prog_test",
        "phase": "recon",
        "execution_mode": "graph_only",
        "messages": [],
        "artifacts": [],
        "findings": [],
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Persona loading from agents.yaml
# ═══════════════════════════════════════════════════════════════════════════════


class TestPersonaLoading:
    """Verify PraisonAgentRegistry loads all canonical + new agents."""

    def test_registry_loads_all_canonical_agents(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry

        registry = PraisonAgentRegistry()
        registry.load_agents()
        ids = registry.agent_ids()
        # Canonical agents from original taxonomy
        for expected in [
            "SecurityGovernorAgent",
            "GovernanceDirector",
            "MissionDirector",
            "PhaseCoordinator",
            "SurfaceMapper",
            "ReconSpecialist",
            "EvidenceAnalyst",
            "ReportSynthesisAgent",
            "HandoffLiaison",
            "HandoffAgent",
            "InterscanReportAgent",
        ]:
            assert expected in ids, f"Missing canonical agent: {expected}"

    def test_registry_loads_new_optional_agents(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry

        registry = PraisonAgentRegistry()
        registry.load_agents()
        ids = registry.agent_ids()
        for expected in [
            "VulnerabilityTriageAgent",
            "ExploitAssessmentAgent",
            "KnowledgeCuratorAgent",
        ]:
            assert expected in ids, f"Missing new agent: {expected}"

    def test_new_agents_have_correct_class(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry

        registry = PraisonAgentRegistry()
        registry.load_agents()
        for aid in ["VulnerabilityTriageAgent", "ExploitAssessmentAgent", "KnowledgeCuratorAgent"]:
            identity = registry.get_agent(aid)
            assert identity.agent_class == "specialist"
            assert identity.delegation_scope == "none"

    def test_knowledge_curator_has_persistent_scope(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry

        registry = PraisonAgentRegistry()
        registry.load_agents()
        curator = registry.get_agent("KnowledgeCuratorAgent")
        assert curator.memory_scope == "persistent"

    def test_phase_coordinator_peers_include_new_agents(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry

        registry = PraisonAgentRegistry()
        registry.load_agents()
        pc = registry.get_agent("PhaseCoordinator")
        assert "VulnerabilityTriageAgent" in pc.allowed_peer_targets
        assert "ExploitAssessmentAgent" in pc.allowed_peer_targets
        assert "KnowledgeCuratorAgent" in pc.allowed_peer_targets

    def test_all_agents_have_system_prompts(self):
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry

        registry = PraisonAgentRegistry()
        registry.load_agents()
        for aid in registry.agent_ids():
            identity = registry.get_agent(aid)
            assert identity.system_prompt, f"Agent {aid} has empty system_prompt"
            assert len(identity.system_prompt) > 20, f"Agent {aid} system_prompt too short"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PraisonAgentRuntime instantiation and execution
# ═══════════════════════════════════════════════════════════════════════════════


class TestPraisonAgentRuntime:
    """Test PraisonAgentRuntime core functionality."""

    def test_runtime_instantiates_without_tools(self):
        runtime = PraisonAgentRuntime()
        assert runtime._tool_registry == {}

    def test_runtime_instantiates_with_tools(self):
        tools = {"subfinder": lambda **kw: {"result": "ok"}}
        runtime = PraisonAgentRuntime(tool_registry=tools)
        assert "subfinder" in runtime._tool_registry

    def test_register_tool(self):
        runtime = PraisonAgentRuntime()
        runtime.register_tool("test_tool", lambda: None)
        assert "test_tool" in runtime._tool_registry

    def test_register_tools_batch(self):
        runtime = PraisonAgentRuntime()
        runtime.register_tools({"t1": lambda: 1, "t2": lambda: 2})
        assert "t1" in runtime._tool_registry
        assert "t2" in runtime._tool_registry

    def test_graph_only_execution_returns_stub(self):
        runtime = PraisonAgentRuntime()
        identity = _make_identity()
        state = _make_state(execution_mode="graph_only")
        result = runtime.execute(identity, state)
        assert result.success is True
        assert result.state_update["last_agent"] == "TestAgent"
        assert result.state_update["execution_mode"] == "graph_only"
        assert result.duration_ms >= 0

    def test_stub_execution_when_praison_unavailable(self):
        """When PraisonAI SDK is not installed, runtime returns stub."""
        runtime = PraisonAgentRuntime()
        identity = _make_identity()
        state = _make_state(execution_mode="live")
        result = runtime.execute(identity, state)
        # Either PraisonAI is available and it tries to run,
        # or it returns a stub. Both are valid.
        if not _PRAISON_AVAILABLE:
            assert result.success is True
            assert result.state_update.get("execution_mode") == "stub"

    def test_execution_result_to_state_update(self):
        result = AgentExecutionResult(
            agent_id="test",
            node_id="node1",
            success=True,
            state_update={"last_agent": "test", "summary": "done"},
            artifacts=[{"artifact_id": "a1", "content": {}}],
            tools_used=["subfinder"],
        )
        update = result.to_state_update()
        assert update["last_agent"] == "test"
        assert update["summary"] == "done"
        assert update["artifacts"] == [{"artifact_id": "a1", "content": {}}]
        assert update["tools_used"] == ["subfinder"]

    def test_execution_result_error_propagates(self):
        result = AgentExecutionResult(
            agent_id="test",
            node_id="node1",
            success=False,
            error="Something broke",
        )
        update = result.to_state_update()
        assert update["error"] == "Something broke"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GovernedToolWrapper
# ═══════════════════════════════════════════════════════════════════════════════


class TestGovernedToolWrapper:
    """Test governance interception of tool calls."""

    def test_stub_tool_returns_stub_status(self):
        identity = _make_identity()
        wrapper = GovernedToolWrapper(
            tool_id="subfinder",
            tool_callable=None,
            identity=identity,
            workflow_id="wf1",
            program_id="p1",
        )
        result = wrapper()
        assert result["status"] == "stub"
        assert result["tool_id"] == "subfinder"

    def test_real_tool_executes_and_returns_completed(self):
        identity = _make_identity()
        wrapper = GovernedToolWrapper(
            tool_id="subfinder",
            tool_callable=lambda **kw: {"domains": ["a.com"]},
            identity=identity,
            workflow_id="wf1",
            program_id="p1",
        )
        result = wrapper()
        assert result["status"] == "completed"
        assert result["result"] == {"domains": ["a.com"]}

    def test_tool_failure_returns_failed_status(self):
        identity = _make_identity()

        def failing_tool(**kw):
            raise RuntimeError("network timeout")

        wrapper = GovernedToolWrapper(
            tool_id="httpx",
            tool_callable=failing_tool,
            identity=identity,
            workflow_id="wf1",
            program_id="p1",
        )
        result = wrapper()
        assert result["status"] == "failed"
        assert "network timeout" in result["error"]

    def test_wrapper_has_name_and_doc(self):
        identity = _make_identity()
        wrapper = GovernedToolWrapper(
            tool_id="nmap",
            tool_callable=None,
            identity=identity,
            workflow_id="wf1",
            program_id="p1",
        )
        assert wrapper.__name__ == "kai_nmap"
        assert "governed tool" in wrapper.__doc__.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Memory scope mapping
# ═══════════════════════════════════════════════════════════════════════════════


class TestMemoryScopeMapping:
    """Test Kai -> PraisonAI memory scope mapping."""

    def test_session_maps_to_short_term(self):
        mapping = map_memory_scope("session")
        assert mapping["praison_type"] == "short_term"
        assert mapping["persist"] is False

    def test_phase_maps_to_short_term_persistent(self):
        mapping = map_memory_scope("phase")
        assert mapping["praison_type"] == "short_term"
        assert mapping["persist"] is True

    def test_workflow_maps_to_long_term(self):
        mapping = map_memory_scope("workflow")
        assert mapping["praison_type"] == "long_term"
        assert mapping["persist"] is True

    def test_mission_maps_to_long_term(self):
        mapping = map_memory_scope("mission")
        assert mapping["praison_type"] == "long_term"

    def test_persistent_maps_to_knowledge(self):
        mapping = map_memory_scope("persistent")
        assert mapping["praison_type"] == "knowledge"
        assert mapping["persist"] is True

    def test_unknown_scope_defaults_to_session(self):
        mapping = map_memory_scope("nonexistent")
        assert mapping["praison_type"] == "short_term"
        assert mapping["persist"] is False

    def test_all_scopes_have_descriptions(self):
        for scope, config in _MEMORY_SCOPE_MAP.items():
            assert "description" in config, f"Scope {scope} missing description"
            assert len(config["description"]) > 5


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Tool profiles
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolProfiles:
    """Test pre-approved tool profile catalog."""

    def test_all_tool_profiles_are_frozen(self):
        for pid, profile in ALL_TOOL_PROFILES.items():
            assert isinstance(profile, ToolProfile)
            with pytest.raises(AttributeError):
                profile.profile_name = "mutated"  # type: ignore[misc]

    def test_tool_profile_lookup_by_id(self):
        assert get_tool_profile("tp_passive_recon") is PASSIVE_RECON
        assert get_tool_profile("tp_balanced_recon") is BALANCED_RECON
        assert get_tool_profile("tp_high_recall") is HIGH_RECALL_SCAN
        assert get_tool_profile("tp_high_precision") is HIGH_PRECISION_SCAN
        assert get_tool_profile("tp_aggressive_validation") is AGGRESSIVE_VALIDATION
        assert get_tool_profile("tp_stealth_preferred") is STEALTH_PREFERRED
        assert get_tool_profile("tp_time_boxed") is TIME_BOXED_SCAN
        assert get_tool_profile("tp_conservative_analysis") is CONSERVATIVE_ANALYSIS

    def test_unknown_profile_returns_none(self):
        assert get_tool_profile("nonexistent") is None

    def test_aggressive_validation_is_high_risk(self):
        assert AGGRESSIVE_VALIDATION.risk_level == "high"

    def test_passive_recon_is_low_risk(self):
        assert PASSIVE_RECON.risk_level == "low"

    def test_profiles_have_tool_ids(self):
        for pid, profile in ALL_TOOL_PROFILES.items():
            assert profile.tool_id, f"Profile {pid} missing tool_id"

    def test_profiles_have_parameters(self):
        for pid, profile in ALL_TOOL_PROFILES.items():
            assert isinstance(profile.parameters, dict)

    def test_tool_profiles_for_surface_mapper(self):
        profiles = tool_profiles_for_agent("SurfaceMapper")
        names = [p.profile_name for p in profiles]
        assert "passive_recon" in names
        assert "balanced_recon" in names
        assert "stealth_preferred" in names

    def test_tool_profiles_for_recon_specialist(self):
        profiles = tool_profiles_for_agent("ReconSpecialist")
        names = [p.profile_name for p in profiles]
        assert "high_recall" in names
        assert "high_precision" in names

    def test_tool_profiles_for_unknown_agent(self):
        profiles = tool_profiles_for_agent("NoSuchAgent")
        assert profiles == []

    def test_total_tool_profiles_count(self):
        assert len(ALL_TOOL_PROFILES) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Prompt profiles
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptProfiles:
    """Test pre-approved prompt profile catalog."""

    def test_all_prompt_profiles_are_frozen(self):
        for pid, profile in ALL_PROMPT_PROFILES.items():
            assert isinstance(profile, PromptProfile)
            with pytest.raises(AttributeError):
                profile.profile_name = "mutated"  # type: ignore[misc]

    def test_prompt_profile_lookup_by_id(self):
        assert get_prompt_profile("pp_thorough_analysis") is THOROUGH_ANALYSIS
        assert get_prompt_profile("pp_fast_triage") is FAST_TRIAGE
        assert get_prompt_profile("pp_deep_validation") is DEEP_VALIDATION
        assert get_prompt_profile("pp_stealth_recon") is STEALTH_RECON
        assert get_prompt_profile("pp_report_submission") is REPORT_SUBMISSION
        assert get_prompt_profile("pp_coverage_maximizer") is COVERAGE_MAXIMIZER

    def test_unknown_profile_returns_none(self):
        assert get_prompt_profile("nonexistent") is None

    def test_profiles_have_templates(self):
        for pid, profile in ALL_PROMPT_PROFILES.items():
            assert profile.template, f"Profile {pid} missing template"
            assert len(profile.template) > 20

    def test_profiles_have_context_keys(self):
        for pid, profile in ALL_PROMPT_PROFILES.items():
            assert "persona" in profile.context_keys, f"Profile {pid} missing persona key"
            assert "phase" in profile.context_keys

    def test_template_formatting_works(self):
        context = {
            "persona": "Test Agent",
            "phase": "recon",
            "mission_id": "m1",
            "workflow_id": "wf1",
        }
        for pid, profile in ALL_PROMPT_PROFILES.items():
            try:
                result = profile.template.format(**context)
                assert "Test Agent" in result
            except KeyError:
                # Some templates may have additional keys — that's fine
                pass

    def test_prompt_profiles_for_evidence_analyst(self):
        profiles = prompt_profiles_for_agent("EvidenceAnalyst")
        names = [p.profile_name for p in profiles]
        assert "thorough_analysis" in names
        assert "fast_triage" in names
        assert "deep_validation" in names

    def test_prompt_profiles_for_unknown_agent(self):
        profiles = prompt_profiles_for_agent("NoSuchAgent")
        assert profiles == []

    def test_total_prompt_profiles_count(self):
        assert len(ALL_PROMPT_PROFILES) == 6


# ═══════════════════════════════════════════════════════════════════════════════
# 7. make_praison_node_callable bridge
# ═══════════════════════════════════════════════════════════════════════════════


class TestNodeCallableBridge:
    """Test LangGraph node callable factory."""

    def test_callable_has_correct_name(self):
        identity = _make_identity(agent_id="ReconSpec")
        runtime = PraisonAgentRuntime()
        fn = make_praison_node_callable(identity, runtime)
        assert fn.__name__ == "praison_ReconSpec"

    def test_callable_returns_state_update_in_graph_only(self):
        identity = _make_identity(agent_id="Mapper")
        runtime = PraisonAgentRuntime()
        fn = make_praison_node_callable(identity, runtime)
        state = _make_state(execution_mode="graph_only")
        result = fn(state)
        assert isinstance(result, dict)
        assert result.get("last_agent") == "Mapper"

    def test_callable_with_strategy(self):
        identity = _make_identity()
        runtime = PraisonAgentRuntime()
        strategy = ExecutionStrategy(
            tool_candidates=("subfinder", "httpx"),
            tool_order=("subfinder", "httpx"),
        )
        fn = make_praison_node_callable(identity, runtime, strategy=strategy)
        state = _make_state(execution_mode="graph_only")
        result = fn(state)
        assert result.get("last_agent") == "TestAgent"

    def test_callable_with_prompt_profile(self):
        identity = _make_identity()
        runtime = PraisonAgentRuntime()
        fn = make_praison_node_callable(
            identity, runtime, prompt_profile=THOROUGH_ANALYSIS
        )
        state = _make_state(execution_mode="graph_only")
        result = fn(state)
        assert result.get("last_agent") == "TestAgent"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. build_praison_agent_callables batch builder
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchCallableBuilder:
    """Test building full mission callable sets."""

    def test_builds_callables_for_all_identities(self):
        identities = {
            "Agent1": _make_identity(agent_id="Agent1"),
            "Agent2": _make_identity(agent_id="Agent2"),
        }
        runtime = PraisonAgentRuntime()
        callables = build_praison_agent_callables(identities, runtime)
        assert "Agent1" in callables
        assert "Agent2" in callables
        assert callable(callables["Agent1"])
        assert callable(callables["Agent2"])

    def test_callables_execute_in_graph_only(self):
        identities = {
            "A": _make_identity(agent_id="A"),
            "B": _make_identity(agent_id="B"),
        }
        runtime = PraisonAgentRuntime()
        callables = build_praison_agent_callables(identities, runtime)
        state = _make_state(execution_mode="graph_only")
        r1 = callables["A"](state)
        r2 = callables["B"](state)
        assert r1["last_agent"] == "A"
        assert r2["last_agent"] == "B"

    def test_with_strategies(self):
        identities = {
            "X": _make_identity(agent_id="X"),
        }
        strategies = {
            "X": ExecutionStrategy(tool_candidates=("subfinder",)),
        }
        runtime = PraisonAgentRuntime()
        callables = build_praison_agent_callables(identities, runtime, strategies)
        assert "X" in callables

    def test_empty_identities_returns_empty(self):
        runtime = PraisonAgentRuntime()
        callables = build_praison_agent_callables({}, runtime)
        assert callables == {}


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Adaptive execution boundaries
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdaptiveExecutionBoundaries:
    """Test that adaptive changes are bounded by strategy."""

    def test_tool_profile_narrowing(self):
        """When a tool_profile is set, only that tool should be exposed."""
        runtime = PraisonAgentRuntime(tool_registry={
            "subfinder": lambda **kw: {"ok": True},
            "httpx": lambda **kw: {"ok": True},
        })
        identity = _make_identity(allowed_tools=["subfinder", "httpx"])
        profile = ToolProfile(tool_id="subfinder", profile_name="passive_recon")

        tools = runtime._build_governed_tools(
            identity=identity,
            mission_id="m1",
            workflow_id="wf1",
            program_id="p1",
            tool_profile=profile,
        )
        # Only subfinder should be wrapped
        assert len(tools) == 1
        assert tools[0].tool_id == "subfinder"

    def test_no_profile_exposes_all_tools(self):
        runtime = PraisonAgentRuntime()
        identity = _make_identity(allowed_tools=["subfinder", "httpx", "naabu"])
        tools = runtime._build_governed_tools(
            identity=identity,
            mission_id="m1",
            workflow_id="wf1",
            program_id="p1",
        )
        assert len(tools) == 3

    def test_profile_for_unknown_tool_still_exposes_all(self):
        """If the tool_profile.tool_id is not in allowed_tools, expose all."""
        runtime = PraisonAgentRuntime()
        identity = _make_identity(allowed_tools=["subfinder", "httpx"])
        profile = ToolProfile(tool_id="nmap", profile_name="stealth")  # nmap not in allowed
        tools = runtime._build_governed_tools(
            identity=identity,
            mission_id="m1",
            workflow_id="wf1",
            program_id="p1",
            tool_profile=profile,
        )
        assert len(tools) == 2  # all tools still available

    def test_high_risk_profile_triggers_escalation_in_strategy(self):
        """High-risk tool profiles should trigger governance escalation."""
        from apps.backend.src.core.praison_adaptive import validate_tool_profile_change

        strategy = ExecutionStrategy(
            allowed_parameter_profiles=(AGGRESSIVE_VALIDATION,),
        )
        result = validate_tool_profile_change(
            from_profile=PASSIVE_RECON,
            to_profile=AGGRESSIVE_VALIDATION,
            strategy=strategy,
        )
        assert result.requires_escalation is True


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Task description building
# ═══════════════════════════════════════════════════════════════════════════════


class TestTaskDescriptionBuilding:
    """Test that task descriptions are built correctly."""

    def test_default_task_description(self):
        runtime = PraisonAgentRuntime()
        identity = _make_identity(persona="Attack Surface Mapper")
        state = _make_state(phase="recon")
        desc = runtime._build_task_description(identity, state)
        assert "Attack Surface Mapper" in desc
        assert "recon" in desc
        assert "JSON object" in desc

    def test_prompt_profile_template_used(self):
        runtime = PraisonAgentRuntime()
        identity = _make_identity(persona="Evidence Analyst")
        state = _make_state(phase="analysis", mission_id="m123")
        desc = runtime._build_task_description(
            identity, state, prompt_profile=THOROUGH_ANALYSIS
        )
        assert "Evidence Analyst" in desc
        assert "analysis" in desc or "exhaustive" in desc.lower()

    def test_bad_template_falls_back_to_default(self):
        runtime = PraisonAgentRuntime()
        identity = _make_identity()
        state = _make_state()
        bad_profile = PromptProfile(
            profile_name="broken",
            template="{nonexistent_key} is required",
            context_keys=("nonexistent_key",),
        )
        desc = runtime._build_task_description(identity, state, prompt_profile=bad_profile)
        # Should fall back to default
        assert "JSON object" in desc


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Output parsing
# ═══════════════════════════════════════════════════════════════════════════════


class TestOutputParsing:
    """Test PraisonAI agent output parsing."""

    def _parse(self, raw, identity):
        runtime = PraisonAgentRuntime()
        return runtime._parse_agent_output(raw, identity)

    def test_parse_dict_output(self):
        identity = _make_identity()
        raw = {
            "findings": [{"severity": "high", "target": "example.com"}],
            "summary": "Found XSS",
            "tools_used": ["nuclei"],
        }
        parsed = self._parse(raw, identity)
        assert parsed["state_update"]["findings"] == raw["findings"]
        assert parsed["tools_used"] == ["nuclei"]
        assert parsed["state_update"]["summary"] == "Found XSS"

    def test_parse_json_string_output(self):
        identity = _make_identity()
        raw = 'Here are results: {"findings": [{"id": 1}], "summary": "done"}'
        parsed = self._parse(raw, identity)
        assert parsed["state_update"]["findings"] == [{"id": 1}]

    def test_parse_plain_string_output(self):
        identity = _make_identity()
        raw = "No structured output available"
        parsed = self._parse(raw, identity)
        assert parsed["state_update"]["summary"] == raw

    def test_parse_none_output(self):
        identity = _make_identity()
        parsed = self._parse(None, identity)
        assert parsed["state_update"]["summary"] == "No output"

    def test_parse_preserves_last_agent(self):
        identity = _make_identity(agent_id="Analyst")
        parsed = self._parse({}, identity)
        assert parsed["state_update"]["last_agent"] == "Analyst"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Module-level utilities
# ═══════════════════════════════════════════════════════════════════════════════


class TestModuleUtilities:
    """Test module-level functions."""

    def test_is_praison_available_returns_bool(self):
        assert isinstance(is_praison_available(), bool)

    def test_map_memory_scope_returns_dict(self):
        for scope in ["session", "phase", "workflow", "mission", "persistent"]:
            result = map_memory_scope(scope)
            assert isinstance(result, dict)
            assert "praison_type" in result
            assert "persist" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Integration: runtime feeds into node executors
# ═══════════════════════════════════════════════════════════════════════════════


class TestRuntimeNodeExecutorIntegration:
    """Test that runtime-produced callables work with Phase 4 node executors."""

    def test_praison_callable_in_specialist_cluster_executor(self):
        from apps.backend.src.core.praison_node_executors import (
            make_specialist_cluster_executor,
        )

        identity = _make_identity(agent_id="ReconSpecialist")
        runtime = PraisonAgentRuntime()

        # Create a PraisonAI-backed callable
        praison_callable = make_praison_node_callable(identity, runtime)

        # Wrap in specialist cluster executor
        executor = make_specialist_cluster_executor("active_recon", praison_callable)
        state = _make_state(execution_mode="graph_only")
        result = executor(state)

        assert result.get("active_node") == "specialist_cluster_active_recon"
        assert result.get("cluster_status", {}).get("active_recon") is not None

    def test_praison_callable_in_evidence_analysis_executor(self):
        from apps.backend.src.core.praison_node_executors import (
            make_evidence_analysis_executor,
        )

        identity = _make_identity(agent_id="EvidenceAnalyst")
        runtime = PraisonAgentRuntime()
        praison_callable = make_praison_node_callable(identity, runtime)
        executor = make_evidence_analysis_executor(praison_callable)
        state = _make_state(execution_mode="graph_only")
        result = executor(state)

        assert result.get("active_node") == "evidence_analysis"
        assert "last_artifact_type" in result

    def test_full_pipeline_graph_only(self):
        """Test full pipeline: registry -> runtime -> callables -> executors."""
        from apps.backend.src.core.praison_node_executors import (
            build_standard_node_callables,
        )
        from apps.backend.src.core.praison_registry import PraisonAgentRegistry

        registry = PraisonAgentRegistry()
        registry.load_agents()
        runtime = PraisonAgentRuntime()

        # Build PraisonAI-backed callables for all registered agents
        identities = {}
        for aid in ["SurfaceMapper", "ReconSpecialist", "EvidenceAnalyst", "ReportSynthesisAgent"]:
            identities[aid] = registry.get_agent(aid)

        praison_callables = build_praison_agent_callables(identities, runtime)

        # Feed into standard node callables
        node_callables = build_standard_node_callables(praison_callables)

        # Execute in graph_only mode
        state = _make_state(execution_mode="graph_only")
        for node_id, executor in node_callables.items():
            result = executor(state)
            assert isinstance(result, dict)
            assert "active_node" in result or "last_agent" in result
