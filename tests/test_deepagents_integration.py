"""
DeepAgents Integration Layer — Production-Grade Test Suite
===========================================================
Tests for the five DeepAgents integration modules in apps/backend/src/core/:

  * praison_adapters/deepagents_adapter  — DeepAgent, DeepAgentConfig,
        DeepAgentResult, create_deep_agent, to_deepagents_config,
        to_deepagents_agent, _SPECIALIST_DEFAULTS
  * praison_deepagents_bridge            — DeepAgentsBridge,
        DeepAgentExecutionContext, get_deepagents_bridge,
        initialize_deepagents_bridge
  * praison_deepagents_backends          — BackendPolicy, BackendViolation,
        BackendConfig, EphemeralBackend, ScratchBackend, DurableBackend,
        create_backend
  * praison_sandbox_manager              — SandboxManager, SandboxHandle,
        SandboxConfig, SandboxResult, SandboxState, SandboxLimitExceeded,
        get_sandbox_manager, initialize_sandbox_manager
  * telemetry/deepagents_stream_adapter  — DeepAgentStreamAdapter,
        StreamEvent, StreamEventFilter

Coverage targets:
  1.  DeepAgentConfig immutability, serialization, specialist defaults
  2.  DeepAgent creation via factory with identity, contract, specialist_type
  3.  DeepAgentResult serialization and state-update mapping
  4.  DeepAgent execution in graph_only / tool_mock simulation modes
  5.  Backend policy enforcement: ephemeral, scratch, durable, path traversal
  6.  Backend factory with production/dev mode overrides
  7.  Sandbox config safe defaults and blocked modules
  8.  Sandbox handle lifecycle, execution modes, TTL, destroy
  9.  SandboxManager concurrency limits, bulk destroy, TTL cleanup
  10. Stream adapter event recording, step counting, truncation
  11. StreamEventFilter namespace/type filtering and timeline format
  12. DeepAgentsBridge specialist execution, result conversion, events
  13. Security: no bypass paths for tools, models, sandbox, backends
  14. Regression: imports do not break existing platform modules

Design rules:
  - All tests are deterministic (no network I/O, no live LLM invocations)
  - No filesystem side effects outside tmpdir
  - Suite completes in < 5 seconds
  - Tests are independent (no shared mutable state between test methods)
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure apps/backend/src is on sys.path so that lazy imports inside
# implementation files resolve correctly when executed under pytest from
# the repo root.
# ---------------------------------------------------------------------------
_SRC_ROOT = str(Path(__file__).resolve().parents[1] / "apps" / "backend" / "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from apps.backend.src.core.praison_agent import AgentIdentity
from apps.backend.src.core.praison_adapters import FrameworkNotInstalledError
from apps.backend.src.core.praison_adapters.deepagents_adapter import (
    DeepAgent,
    DeepAgentConfig,
    DeepAgentResult,
    _DEEPAGENTS_AVAILABLE,
    _SPECIALIST_DEFAULTS,
    _VALID_EXECUTION_MODES,
    _VALID_SPECIALIST_TYPES,
    build_k1_subagent_spec,
    create_deep_agent,
    is_deepagents_available,
    to_deepagents_agent,
    to_deepagents_config,
)
from apps.backend.src.core.praison_deepagents_backends import (
    BackendConfig,
    BackendPolicy,
    BackendViolation,
    DurableBackend,
    EphemeralBackend,
    K1BackendProtocolAdapter,
    ScratchBackend,
    _DEEPAGENTS_BACKEND_AVAILABLE,
    create_backend,
    create_protocol_adapter,
    is_deepagents_backend_available,
)
from apps.backend.src.core.praison_deepagents_bridge import (
    DeepAgentExecutionContext,
    DeepAgentsBridge,
    get_deepagents_bridge,
    initialize_deepagents_bridge,
)
from apps.backend.src.core.praison_sandbox_manager import (
    SandboxConfig,
    SandboxHandle,
    SandboxLimitExceeded,
    SandboxManager,
    SandboxResult,
    SandboxState,
    get_sandbox_manager,
    initialize_sandbox_manager,
)
from apps.backend.src.core.telemetry.deepagents_stream_adapter import (
    DeepAgentStreamAdapter,
    StreamEvent,
    StreamEventFilter,
    _CONTENT_PREVIEW_MAX,
)


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _make_identity(
    agent_id: str = "test_specialist",
    agent_class: str = "specialist",
    allowed_tools: tuple[str, ...] = ("nmap", "subfinder"),
    delegation_scope: str = "none",
    **kwargs: Any,
) -> AgentIdentity:
    """Create a minimal AgentIdentity for testing."""
    defaults: dict[str, Any] = {
        "persona": "Test Specialist",
        "description": "Test specialist agent",
        "system_prompt": "You are a test specialist.",
        "risk_profile": "standard",
        "workflow_id": "wf-test",
        "program_id": "prog-test",
    }
    defaults.update(kwargs)
    return AgentIdentity(
        agent_id=agent_id,
        agent_class=agent_class,
        allowed_tools=allowed_tools,
        delegation_scope=delegation_scope,
        **defaults,
    )


def _make_coordinator() -> AgentIdentity:
    """Create a coordinator identity for delegation tests."""
    return AgentIdentity(
        agent_id="test_coordinator",
        persona="Test Coordinator",
        description="Test coordinator",
        system_prompt="Coordinator",
        agent_class="coordinator",
        delegation_scope="local",
        allowed_peer_targets=("test_specialist",),
        allowed_tools=("nmap", "subfinder", "httpx"),
        workflow_id="wf-test",
        program_id="prog-test",
    )


def _make_execution_context(**overrides: Any) -> DeepAgentExecutionContext:
    """Create a minimal execution context for bridge tests."""
    defaults: dict[str, Any] = {
        "mission_id": "m-test",
        "workflow_id": "wf-test",
        "program_id": "prog-test",
        "phase": "recon",
        "node_id": "node-01",
        "execution_mode": "graph_only",
        "parent_agent_id": "test_coordinator",
    }
    defaults.update(overrides)
    return DeepAgentExecutionContext(**defaults)


# ============================================================================
# 1. TestDeepAgentConfig (5 tests)
# ============================================================================


class TestDeepAgentConfig:
    """DeepAgentConfig immutability, serialization, and specialist defaults."""

    def test_config_frozen(self) -> None:
        """DeepAgentConfig is immutable -- attribute assignment raises."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only")
        cfg = agent.config
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.agent_id = "changed"  # type: ignore[misc]

    def test_config_to_dict(self) -> None:
        """to_dict() includes all required fields for audit trail."""
        identity = _make_identity()
        agent = create_deep_agent(
            identity,
            specialist_type="evidence_analyst",
            execution_mode="graph_only",
            phase="recon",
            mission_id="m1",
        )
        d = agent.config.to_dict()
        required_keys = {
            "agent_id", "specialist_type", "identity_id", "system_prompt_length",
            "model_name", "preferred_provider", "tool_ids", "target_ids",
            "phase", "execution_mode", "mission_id", "workflow_id", "program_id",
            "max_iterations", "max_subagents", "max_tokens_budget",
            "response_format", "contract_id", "backend_policy",
            "scratch_prefix", "sandbox_enabled", "interrupt_on_band2", "metadata",
        }
        assert required_keys.issubset(set(d.keys())), (
            f"Missing keys: {required_keys - set(d.keys())}"
        )
        assert d["agent_id"] == "test_specialist"
        assert d["specialist_type"] == "evidence_analyst"
        assert d["execution_mode"] == "graph_only"

    def test_specialist_defaults_exist(self) -> None:
        """_SPECIALIST_DEFAULTS contains all 5 specialist types."""
        expected_types = {
            "evidence_analyst",
            "triage_specialist",
            "exploit_assessor",
            "report_synthesizer",
            "knowledge_curator",
        }
        assert set(_SPECIALIST_DEFAULTS.keys()) == expected_types

    def test_specialist_defaults_have_required_keys(self) -> None:
        """Each specialist default has max_iterations, max_subagents, max_tokens_budget."""
        required = {"max_iterations", "max_subagents", "max_tokens_budget"}
        for spec_type, defaults in _SPECIALIST_DEFAULTS.items():
            assert required.issubset(set(defaults.keys())), (
                f"{spec_type} missing keys: {required - set(defaults.keys())}"
            )

    def test_config_tool_ids_frozenset(self) -> None:
        """tool_ids is coerced to frozenset even when supplied as list/tuple."""
        identity = _make_identity(allowed_tools=("nmap", "subfinder"))
        agent = create_deep_agent(identity, execution_mode="graph_only")
        assert isinstance(agent.config.tool_ids, frozenset)
        assert agent.config.tool_ids == frozenset({"nmap", "subfinder"})


# ============================================================================
# 2. TestDeepAgentCreation (8 tests)
# ============================================================================


class TestDeepAgentCreation:
    """Factory function create_deep_agent and adapter entry points."""

    def test_create_deep_agent_basic(self) -> None:
        """create_deep_agent returns a DeepAgent instance."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only")
        assert isinstance(agent, DeepAgent)
        assert agent.config.agent_id == "test_specialist"

    def test_create_deep_agent_with_specialist_type(self) -> None:
        """specialist_type propagates to the config."""
        identity = _make_identity()
        agent = create_deep_agent(
            identity, specialist_type="triage_specialist", execution_mode="graph_only"
        )
        assert agent.config.specialist_type == "triage_specialist"

    def test_create_deep_agent_defaults_from_specialist_type(self) -> None:
        """Specialist defaults are applied when explicit values are not given."""
        identity = _make_identity()
        agent = create_deep_agent(
            identity, specialist_type="evidence_analyst", execution_mode="graph_only"
        )
        defaults = _SPECIALIST_DEFAULTS["evidence_analyst"]
        assert agent.config.max_iterations == defaults["max_iterations"]
        assert agent.config.max_subagents == defaults["max_subagents"]
        assert agent.config.max_tokens_budget == defaults["max_tokens_budget"]

    def test_create_deep_agent_with_contract(self) -> None:
        """When a contract is supplied, tool_ids come from the contract."""
        identity = _make_identity(allowed_tools=("nmap", "subfinder", "httpx"))
        mock_contract = MagicMock()
        mock_contract.allowed_tools = ("nmap",)
        mock_contract.allowed_targets = ("example.com",)
        agent = create_deep_agent(
            identity, contract=mock_contract, execution_mode="graph_only"
        )
        assert agent.config.tool_ids == frozenset({"nmap"})
        assert agent.config.target_ids == frozenset({"example.com"})

    def test_create_deep_agent_execution_mode(self) -> None:
        """execution_mode propagates to config."""
        identity = _make_identity()
        for mode in ("graph_only", "tool_mock"):
            agent = create_deep_agent(identity, execution_mode=mode)
            assert agent.config.execution_mode == mode

    def test_to_deepagents_config_returns_dict(self) -> None:
        """to_deepagents_config returns a framework-agnostic dict."""
        identity = _make_identity()
        cfg_dict = to_deepagents_config(identity)
        assert isinstance(cfg_dict, dict)
        assert cfg_dict["agent_id"] == "test_specialist"
        assert "tool_whitelist" in cfg_dict
        assert set(cfg_dict["tool_whitelist"]) == {"nmap", "subfinder"}

    def test_to_deepagents_agent_returns_deep_agent(self) -> None:
        """to_deepagents_agent returns a DeepAgent instance."""
        identity = _make_identity()
        agent = to_deepagents_agent(identity)
        assert isinstance(agent, DeepAgent)
        assert agent.config.agent_id == identity.agent_id

    def test_create_deep_agent_respects_identity_tools(self) -> None:
        """tool_ids are sourced from identity.allowed_tools when no contract."""
        identity = _make_identity(allowed_tools=("nmap", "subfinder", "httpx"))
        agent = create_deep_agent(identity, execution_mode="graph_only")
        assert agent.config.tool_ids == frozenset({"nmap", "subfinder", "httpx"})


# ============================================================================
# 3. TestDeepAgentResult (5 tests)
# ============================================================================


class TestDeepAgentResult:
    """DeepAgentResult serialization and state-update mapping."""

    def test_result_to_state_update_with_artifacts(self) -> None:
        """Artifacts in the result map to state update dict."""
        result = DeepAgentResult(
            agent_id="a1",
            success=True,
            artifacts_produced=[{"artifact_id": "art1", "type": "scan"}],
            events=[{"event_type": "deep_agent_completed"}],
        )
        update = result.to_state_update()
        assert "artifacts" in update
        assert len(update["artifacts"]) == 1
        assert update["artifacts"][0]["artifact_id"] == "art1"

    def test_result_to_state_update_with_error(self) -> None:
        """Error in the result maps to state update."""
        result = DeepAgentResult(
            agent_id="a1", success=False, error="Something failed"
        )
        update = result.to_state_update()
        assert update["error"] == "Something failed"

    def test_result_to_state_update_empty(self) -> None:
        """Empty result produces a minimal update (no artifacts, no error)."""
        result = DeepAgentResult(agent_id="a1", success=True)
        update = result.to_state_update()
        assert "artifacts" not in update
        assert "error" not in update

    def test_result_to_dict(self) -> None:
        """to_dict() serialization includes all expected fields."""
        result = DeepAgentResult(
            agent_id="a1",
            specialist_type="evidence_analyst",
            success=True,
            tokens_used=1500,
            latency_ms=42.5,
        )
        d = result.to_dict()
        assert d["agent_id"] == "a1"
        assert d["specialist_type"] == "evidence_analyst"
        assert d["success"] is True
        assert d["tokens_used"] == 1500
        assert d["latency_ms"] == 42.5
        assert "artifacts_count" in d
        assert "events_count" in d

    def test_result_success_flag(self) -> None:
        """success field is correctly propagated."""
        success_result = DeepAgentResult(agent_id="a1", success=True)
        failure_result = DeepAgentResult(agent_id="a1", success=False)
        assert success_result.success is True
        assert failure_result.success is False


# ============================================================================
# 4. TestDeepAgentExecution (8 tests)
# ============================================================================


class TestDeepAgentExecution:
    """DeepAgent execution in graph_only / tool_mock simulation modes."""

    def test_execute_graph_only_returns_simulation(self) -> None:
        """graph_only execution returns a simulation result with [SIMULATION] prefix."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only")

        result = asyncio.run(agent.execute("Test task"))
        assert result.success is True
        assert "[SIMULATION]" in result.output.get("text", "")

    def test_execute_tool_mock_returns_simulation(self) -> None:
        """tool_mock execution returns a simulation result."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="tool_mock")

        result = asyncio.run(agent.execute("Test task"))
        assert result.success is True
        assert "[SIMULATION]" in result.output.get("text", "")

    def test_execute_graph_only_success(self) -> None:
        """graph_only result has success=True."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only")

        result = asyncio.run(agent.execute("Analyze vulnerability"))
        assert result.success is True
        assert result.error == ""

    def test_execute_graph_only_zero_tokens(self) -> None:
        """graph_only uses zero tokens and near-zero latency."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only")

        result = asyncio.run(agent.execute("Task"))
        assert result.tokens_used == 0
        assert result.iterations_used == 0

    def test_execute_structured_graph_only(self) -> None:
        """Structured execution in graph_only returns a simulation result."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only")

        result = asyncio.run(agent.execute_structured("Task", schema=dict))
        assert result.success is True

    def test_execute_sets_specialist_type(self) -> None:
        """result.specialist_type matches the configured specialist_type."""
        identity = _make_identity()
        agent = create_deep_agent(
            identity, specialist_type="triage_specialist", execution_mode="graph_only"
        )

        result = asyncio.run(agent.execute("Triage finding"))
        assert result.specialist_type == "triage_specialist"

    def test_execute_graph_only_has_events(self) -> None:
        """graph_only execution produces at least one event."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only")

        result = asyncio.run(agent.execute("Scan target"))
        assert len(result.events) >= 1

    def test_execute_preserves_agent_id(self) -> None:
        """result.agent_id matches the configured agent_id."""
        identity = _make_identity(agent_id="my_agent_42")
        agent = create_deep_agent(identity, execution_mode="graph_only")

        result = asyncio.run(agent.execute("Run"))
        assert result.agent_id == "my_agent_42"


# ============================================================================
# 5. TestBackendPolicy (8 tests)
# ============================================================================


class TestBackendPolicy:
    """EphemeralBackend operations and path traversal prevention."""

    def _make_ephemeral(self) -> EphemeralBackend:
        """Create an EphemeralBackend with safe defaults."""
        config = BackendConfig.safe_default("agent1", "thread1")
        return EphemeralBackend(config)

    def test_ephemeral_backend_write_read(self) -> None:
        """Write + read round-trips correctly."""
        backend = self._make_ephemeral()
        backend.write("output.json", '{"result": 42}')
        data = backend.read("output.json")
        assert data == '{"result": 42}'

    def test_ephemeral_backend_list_keys(self) -> None:
        """list_keys returns written keys in sorted order."""
        backend = self._make_ephemeral()
        backend.write("b.txt", "B")
        backend.write("a.txt", "A")
        keys = backend.list_keys()
        assert keys == ["a.txt", "b.txt"]

    def test_ephemeral_backend_delete(self) -> None:
        """delete removes the key; subsequent read returns None."""
        backend = self._make_ephemeral()
        backend.write("temp.txt", "data")
        assert backend.delete("temp.txt") is True
        assert backend.read("temp.txt") is None

    def test_ephemeral_backend_cleanup(self) -> None:
        """cleanup clears all keys and resets usage."""
        backend = self._make_ephemeral()
        backend.write("a.txt", "AAA")
        backend.write("b.txt", "BBB")
        backend.cleanup()
        assert backend.list_keys() == []
        assert backend.usage_bytes() == 0

    def test_ephemeral_backend_usage_bytes(self) -> None:
        """usage_bytes tracks cumulative size of stored data."""
        backend = self._make_ephemeral()
        backend.write("file.txt", "hello")  # 5 bytes
        assert backend.usage_bytes() == 5
        backend.write("file2.txt", "world!")  # 6 bytes
        assert backend.usage_bytes() == 11

    def test_path_traversal_blocked(self) -> None:
        """'..' in key raises BackendViolation."""
        backend = self._make_ephemeral()
        with pytest.raises(BackendViolation, match="traversal"):
            backend.write("../etc/passwd", "malicious")

    def test_absolute_path_blocked(self) -> None:
        """'/' prefix raises BackendViolation."""
        backend = self._make_ephemeral()
        with pytest.raises(BackendViolation, match="Absolute path"):
            backend.write("/etc/shadow", "malicious")

    def test_null_byte_blocked(self) -> None:
        """Null byte in key raises BackendViolation."""
        backend = self._make_ephemeral()
        with pytest.raises(BackendViolation, match="Null byte"):
            backend.write("file\x00.txt", "data")


# ============================================================================
# 6. TestBackendFactory (6 tests)
# ============================================================================


class TestBackendFactory:
    """Backend factory with production/dev mode overrides."""

    def test_create_backend_ephemeral(self) -> None:
        """create_backend('ephemeral') returns an EphemeralBackend."""
        backend = create_backend("agent1", "thread1", "ephemeral", production_mode=False)
        assert isinstance(backend, EphemeralBackend)

    def test_create_backend_scratch(self) -> None:
        """create_backend('scratch') returns a ScratchBackend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"K1_ARTIFACTS_ROOT": tmpdir}):
                backend = create_backend(
                    "agent1", "thread1", "scratch", production_mode=False
                )
                assert isinstance(backend, ScratchBackend)

    def test_create_backend_durable_blocked_by_default(self) -> None:
        """Durable policy falls back to ScratchBackend in production when not allowed.

        BackendConfig.for_production() silently downgrades durable -> scratch when
        K1_DEEPAGENT_ALLOW_DURABLE is not true. The factory follows that decision.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                "K1_DEEPAGENT_ALLOW_DURABLE": "false",
                "K1_DEEPAGENT_DEV_MODE": "false",
                "K1_ARTIFACTS_ROOT": tmpdir,
            }):
                backend = create_backend("agent1", "thread1", "durable", production_mode=True)
                # for_production downgrades durable -> scratch when not allowed
                assert isinstance(backend, ScratchBackend)

    def test_production_mode_defaults(self) -> None:
        """_is_production returns True when K1_DEEPAGENT_DEV_MODE is not set."""
        with patch.dict(os.environ, {"K1_DEEPAGENT_DEV_MODE": "false"}, clear=False):
            from apps.backend.src.core.praison_deepagents_backends import _is_production
            assert _is_production() is True

    def test_dev_mode_override(self) -> None:
        """K1_DEEPAGENT_DEV_MODE=true makes _is_production return False."""
        with patch.dict(os.environ, {"K1_DEEPAGENT_DEV_MODE": "true"}):
            from apps.backend.src.core.praison_deepagents_backends import _is_production
            assert _is_production() is False

    def test_backend_config_safe_default(self) -> None:
        """BackendConfig.safe_default creates valid config with safe settings."""
        config = BackendConfig.safe_default("agent1", "thread1")
        assert config.policy == BackendPolicy.EPHEMERAL
        assert config.allow_host_fs is False
        assert config.allow_shell is False
        assert config.max_size_bytes == 50 * 1024 * 1024
        assert config.ttl_seconds == 3600


# ============================================================================
# 7. TestSandboxConfig (4 tests)
# ============================================================================


class TestSandboxConfig:
    """SandboxConfig immutability, safe defaults, and blocked modules."""

    def test_sandbox_config_safe_default(self) -> None:
        """safe_default creates config with blocked modules populated."""
        config = SandboxConfig.safe_default("agent1")
        assert isinstance(config.blocked_modules, frozenset)
        assert len(config.blocked_modules) > 0
        assert config.agent_id == "agent1"

    def test_sandbox_config_blocks_dangerous_modules(self) -> None:
        """os, subprocess, shutil, socket are in blocked_modules."""
        config = SandboxConfig.safe_default("agent1")
        dangerous = {"os", "subprocess", "shutil", "socket"}
        assert dangerous.issubset(config.blocked_modules), (
            f"Missing from blocked_modules: {dangerous - config.blocked_modules}"
        )

    def test_sandbox_config_frozen(self) -> None:
        """SandboxConfig is immutable."""
        config = SandboxConfig.safe_default("agent1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.agent_id = "changed"  # type: ignore[misc]

    def test_sandbox_config_defaults(self) -> None:
        """max_ttl, max_memory, max_output have sane default values."""
        config = SandboxConfig.safe_default("agent1")
        assert config.max_ttl_seconds > 0
        assert config.max_memory_mb > 0
        assert config.max_output_bytes > 0
        assert config.allow_network is False
        assert config.allow_filesystem is False


# ============================================================================
# 8. TestSandboxHandle (6 tests)
# ============================================================================


class TestSandboxHandle:
    """SandboxHandle lifecycle, execution modes, and serialization."""

    def _make_handle(self, execution_mode: str = "graph_only") -> SandboxHandle:
        config = SandboxConfig.safe_default("agent1", execution_mode=execution_mode)
        return SandboxHandle(config)

    def test_sandbox_execute_graph_only(self) -> None:
        """graph_only execution returns a simulation fixture result."""
        handle = self._make_handle("graph_only")
        result = asyncio.run(handle.execute("print('hello')"))
        assert result.success is True
        assert "[SIMULATION]" in result.stdout
        assert result.exit_code == 0

    def test_sandbox_execute_tool_mock(self) -> None:
        """tool_mock execution returns mock result."""
        handle = self._make_handle("tool_mock")
        result = asyncio.run(handle.execute("x = 1 + 1"))
        assert result.success is True
        assert "[MOCK]" in result.stdout
        assert result.exit_code == 0

    def test_sandbox_execute_live_blocked_by_default(self) -> None:
        """Live mode is blocked without K1_SANDBOX_ALLOW_INPROCESS=true."""
        with patch.dict(os.environ, {"K1_SANDBOX_ALLOW_INPROCESS": "false"}):
            handle = self._make_handle("live")
            result = asyncio.run(handle.execute("print(1)"))
            assert result.success is False
            assert "blocked" in result.error.lower() or "In-process" in result.error

    def test_sandbox_state_lifecycle(self) -> None:
        """Sandbox state transitions: CREATED -> RUNNING -> COMPLETED."""
        handle = self._make_handle("graph_only")
        assert handle.state == SandboxState.CREATED
        asyncio.run(handle.execute("pass"))
        assert handle.state == SandboxState.COMPLETED

    def test_sandbox_destroy(self) -> None:
        """destroy() sets state to DESTROYED."""
        handle = self._make_handle("graph_only")
        assert handle.state == SandboxState.CREATED
        handle.destroy()
        assert handle.state == SandboxState.DESTROYED

    def test_sandbox_result_to_dict(self) -> None:
        """SandboxResult.to_dict() serialization includes all required fields."""
        result = SandboxResult(
            sandbox_id="sb-1",
            success=True,
            stdout="output",
            stderr="",
            exit_code=0,
            execution_time_ms=12.5,
            truncated=False,
            error="",
        )
        d = result.to_dict()
        assert d["sandbox_id"] == "sb-1"
        assert d["success"] is True
        assert d["stdout"] == "output"
        assert d["exit_code"] == 0
        assert d["execution_time_ms"] == 12.5
        assert "truncated" in d
        assert "error" in d


# ============================================================================
# 9. TestSandboxManager (6 tests)
# ============================================================================


class TestSandboxManager:
    """SandboxManager concurrency limits, bulk destroy, and singleton."""

    def _make_manager(self, max_concurrent: int = 5) -> SandboxManager:
        """Create an isolated SandboxManager with a mock event bus."""
        mock_bus = MagicMock()
        return SandboxManager(event_bus=mock_bus, max_concurrent=max_concurrent)

    def test_create_sandbox(self) -> None:
        """create() returns a SandboxHandle and tracks it."""
        mgr = self._make_manager()
        handle = mgr.create("agent1", execution_mode="graph_only")
        assert isinstance(handle, SandboxHandle)
        assert mgr.active_count() == 1

    def test_max_concurrent_limit(self) -> None:
        """SandboxLimitExceeded after reaching max_concurrent."""
        mgr = self._make_manager(max_concurrent=2)
        mgr.create("agent1", execution_mode="graph_only")
        mgr.create("agent2", execution_mode="graph_only")
        with pytest.raises(SandboxLimitExceeded):
            mgr.create("agent3", execution_mode="graph_only")

    def test_destroy_sandbox(self) -> None:
        """destroy() removes sandbox from active tracking."""
        mgr = self._make_manager()
        handle = mgr.create("agent1", execution_mode="graph_only")
        assert mgr.destroy(handle.sandbox_id) is True
        # After destroy, it is in a terminal state so active_count should drop
        assert mgr.active_count() == 0

    def test_destroy_for_mission(self) -> None:
        """destroy_for_mission() bulk-destroys all sandboxes for a mission."""
        mgr = self._make_manager()
        mgr.create("agent1", mission_id="m1", execution_mode="graph_only")
        mgr.create("agent2", mission_id="m1", execution_mode="graph_only")
        mgr.create("agent3", mission_id="m2", execution_mode="graph_only")
        count = mgr.destroy_for_mission("m1")
        assert count == 2
        assert mgr.active_count() == 1

    def test_cleanup_expired(self) -> None:
        """Expired sandboxes end up in terminal state and are no longer active.

        The SandboxHandle.state property auto-transitions to EXPIRED when TTL
        is exceeded. After that, cleanup_expired reflects the terminal state
        and the sandbox is no longer counted as active.
        """
        mgr = self._make_manager()
        handle = mgr.create("agent1", execution_mode="graph_only", max_ttl_seconds=1)
        # Force the sandbox to be expired by setting _created_at far in the past
        handle._created_at = time.monotonic() - 100
        # Also set the TTL to something small to ensure is_expired is True
        object.__setattr__(handle._config, "max_ttl_seconds", 0)
        # Accessing .state triggers auto-transition to EXPIRED (terminal)
        assert handle.is_expired is True
        # cleanup_expired will find this sandbox already expired (auto-transition)
        mgr.cleanup_expired()
        # The key invariant: active_count is 0 because the sandbox is terminal
        assert mgr.active_count() == 0

    def test_sandbox_manager_singleton(self) -> None:
        """get_sandbox_manager returns same instance on repeated calls."""
        import apps.backend.src.core.praison_sandbox_manager as sm_mod
        # Reset the singleton
        original = sm_mod._manager
        try:
            sm_mod._manager = None
            m1 = get_sandbox_manager()
            m2 = get_sandbox_manager()
            assert m1 is m2
        finally:
            sm_mod._manager = original


# ============================================================================
# 10. TestStreamAdapter (8 tests)
# ============================================================================


class TestStreamAdapter:
    """DeepAgentStreamAdapter event recording and output truncation."""

    def _make_adapter(self, **kwargs: Any) -> DeepAgentStreamAdapter:
        defaults: dict[str, Any] = {
            "mission_id": "m1",
            "workflow_id": "w1",
            "program_id": "p1",
            "agent_id": "EvidenceAnalyst",
            "specialist_type": "evidence_analyst",
        }
        defaults.update(kwargs)
        return DeepAgentStreamAdapter(**defaults)

    def test_record_start_creates_event(self) -> None:
        """record_start creates a StreamEvent with deep_agent_started type."""
        adapter = self._make_adapter()
        event = adapter.record_start()
        assert isinstance(event, StreamEvent)
        assert event.event_type == "deep_agent_started"
        assert len(adapter.get_events()) == 1

    def test_record_step_increments(self) -> None:
        """step_number increments with each recorded step."""
        adapter = self._make_adapter()
        adapter.record_step(step=1, content="Step 1")
        adapter.record_step(step=2, content="Step 2")
        adapter.record_step(step=3, content="Step 3")
        assert adapter.step_count == 3
        events = adapter.get_events()
        assert len(events) == 3

    def test_record_tool_call_event(self) -> None:
        """Tool call event has correct event_type and detail."""
        adapter = self._make_adapter()
        event = adapter.record_tool_call(tool_id="nmap", target="example.com")
        assert event.event_type == "deep_agent_tool_call"
        assert event.detail["tool_id"] == "nmap"
        assert event.detail["target"] == "example.com"

    def test_record_subagent_events(self) -> None:
        """Subagent started and completed events have correct namespace."""
        adapter = self._make_adapter()
        start_evt = adapter.record_subagent_started("sub-01", objective="Scan ports")
        complete_evt = adapter.record_subagent_completed("sub-01", success=True)
        assert start_evt.event_type == "deep_agent_subagent_started"
        assert start_evt.namespace == "subagent:sub-01"
        assert complete_evt.event_type == "deep_agent_subagent_completed"
        assert complete_evt.namespace == "subagent:sub-01"

    def test_record_planning_with_todos(self) -> None:
        """Planning event captures todo items."""
        adapter = self._make_adapter()
        todos = ["Run nmap scan", "Analyze results", "Draft report"]
        event = adapter.record_planning(
            plan_summary="Phase 1 plan", todos=todos
        )
        assert event.event_type == "deep_agent_planning"
        assert event.detail["todos"] == todos
        assert event.detail["todo_count"] == 3

    def test_record_completed_with_tokens(self) -> None:
        """Completion event includes success and tokens_used in detail."""
        adapter = self._make_adapter()
        event = adapter.record_completed(success=True, tokens_used=5000)
        assert event.event_type == "deep_agent_completed"
        assert event.detail["success"] is True
        assert event.detail["tokens_used"] == 5000

    def test_record_error_event(self) -> None:
        """Error event is recorded and has_errors is set."""
        adapter = self._make_adapter()
        event = adapter.record_error("Connection timeout")
        assert event.event_type == "deep_agent_error"
        assert adapter.has_errors is True
        assert event.detail["error"] == "Connection timeout"

    def test_content_preview_truncation(self) -> None:
        """Content exceeding 500 chars is truncated with ellipsis."""
        adapter = self._make_adapter()
        long_content = "A" * 600
        event = adapter.record_step(step=1, content=long_content)
        # _CONTENT_PREVIEW_MAX is 500; truncated means <= 500 chars
        assert len(event.content_preview) <= _CONTENT_PREVIEW_MAX
        assert event.content_preview.endswith("...")


# ============================================================================
# 11. TestStreamEventFilter (5 tests)
# ============================================================================


class TestStreamEventFilter:
    """StreamEventFilter filtering by namespace, type, and timeline format."""

    def _build_events(self) -> list[StreamEvent]:
        """Build a list of mixed events for filtering tests."""
        adapter = DeepAgentStreamAdapter(
            mission_id="m1", workflow_id="w1", program_id="p1",
            agent_id="A1", specialist_type="evidence_analyst",
        )
        adapter.record_start()
        adapter.record_step(step=1, content="reasoning")
        adapter.record_tool_call("nmap", "example.com")
        adapter.record_subagent_started("sub-01", "scan ports")
        adapter.record_subagent_completed("sub-01", success=True)
        adapter.record_planning(plan_summary="Plan", todos=["item"])
        adapter.record_completed(success=True, tokens_used=100)
        return adapter.get_events()

    def test_filter_by_namespace_main(self) -> None:
        """main_agent_only returns only events with namespace='main'."""
        events = self._build_events()
        main_events = StreamEventFilter.main_agent_only(events)
        for e in main_events:
            assert e.namespace == "main"
        # At least the start, step, tool_call, planning, completed events
        assert len(main_events) >= 4

    def test_filter_by_namespace_subagent(self) -> None:
        """subagent_only returns only events with namespace starting with 'subagent:'."""
        events = self._build_events()
        sub_events = StreamEventFilter.subagent_only(events)
        for e in sub_events:
            assert e.namespace.startswith("subagent:")
        assert len(sub_events) == 2  # started + completed

    def test_filter_by_type(self) -> None:
        """by_type filters events by specific event_type."""
        events = self._build_events()
        tool_events = StreamEventFilter.by_type(events, "deep_agent_tool_call")
        assert len(tool_events) == 1
        assert tool_events[0].event_type == "deep_agent_tool_call"

    def test_planning_events_filter(self) -> None:
        """planning_events returns only deep_agent_planning events."""
        events = self._build_events()
        plan_events = StreamEventFilter.planning_events(events)
        assert len(plan_events) == 1
        assert plan_events[0].event_type == "deep_agent_planning"

    def test_to_timeline_format(self) -> None:
        """to_timeline returns list of dicts with required keys."""
        events = self._build_events()
        timeline = StreamEventFilter.to_timeline(events)
        assert isinstance(timeline, list)
        assert len(timeline) == len(events)
        required_keys = {"timestamp", "type", "agent", "namespace", "step", "preview", "contract_id"}
        for entry in timeline:
            assert required_keys.issubset(set(entry.keys())), (
                f"Missing keys: {required_keys - set(entry.keys())}"
            )


# ============================================================================
# 12. TestDeepAgentsBridge (7 tests)
# ============================================================================


class TestDeepAgentsBridge:
    """DeepAgentsBridge specialist execution, result conversion, and events."""

    def _make_bridge(
        self,
        mock_bus: Any = None,
        mock_policy: Any = None,
    ) -> DeepAgentsBridge:
        """Create a bridge with mock dependencies."""
        bus = mock_bus or MagicMock()
        policy = mock_policy or MagicMock()
        policy.validate_identity = MagicMock(return_value=[])  # no errors
        return DeepAgentsBridge(event_bus=bus, runtime_policy=policy)

    def test_bridge_execute_specialist_graph_only(self) -> None:
        """execute_specialist in graph_only returns DeepAgentResult."""
        bridge = self._make_bridge()
        identity = _make_identity()
        ctx = _make_execution_context()

        result = asyncio.run(
            bridge.execute_specialist(
                identity=identity,
                specialist_type="evidence_analyst",
                task="Analyze artifacts",
                context=ctx,
            )
        )
        assert isinstance(result, DeepAgentResult)
        assert result.success is True
        assert result.specialist_type == "evidence_analyst"

    def test_bridge_result_to_state_update(self) -> None:
        """result_to_state_update maps to K1GraphState-compatible dict."""
        bridge = self._make_bridge()
        result = DeepAgentResult(
            agent_id="a1",
            specialist_type="evidence_analyst",
            success=True,
            output={"text": "Analysis complete"},
            artifacts_produced=[{"artifact_id": "art1"}],
            events=[{"event_type": "deep_agent_completed"}],
            tokens_used=500,
            latency_ms=10.0,
        )
        update = bridge.result_to_state_update(result)
        assert "last_output" in update
        assert "artifacts" in update
        assert "events" in update
        assert "_specialist_meta" in update
        meta = update["_specialist_meta"]
        assert meta["agent_id"] == "a1"
        assert meta["success"] is True
        assert meta["tokens_used"] == 500

    def test_bridge_result_to_artifacts_adds_provenance(self) -> None:
        """result_to_artifacts enriches each artifact with provenance."""
        bridge = self._make_bridge()
        result = DeepAgentResult(
            agent_id="a1",
            specialist_type="evidence_analyst",
            success=True,
            artifacts_produced=[
                {"artifact_id": "art1", "type": "scan_result"},
                {"artifact_id": "art2", "type": "evidence"},
            ],
        )
        artifacts = bridge.result_to_artifacts(result)
        assert len(artifacts) == 2
        for art in artifacts:
            assert "provenance" in art
            assert art["provenance"]["bridge"] == "deepagents"
            assert art["provenance"]["specialist_type"] == "evidence_analyst"
            assert art["provenance"]["agent_id"] == "a1"

    def test_bridge_create_subagent_contract(self) -> None:
        """create_subagent_contract creates a DelegationContract.

        The coordinator's allowed_peer_targets must include the child agent ID
        for the bidirectional trust check in create_delegation_contract to pass.
        """
        mock_bus = MagicMock()
        mock_policy = MagicMock()
        mock_policy.validate_identity = MagicMock(return_value=[])
        bridge = DeepAgentsBridge(event_bus=mock_bus, runtime_policy=mock_policy)
        # Create coordinator that includes the child in its peer targets
        coordinator = AgentIdentity(
            agent_id="test_coordinator",
            persona="Test Coordinator",
            description="Test coordinator",
            system_prompt="Coordinator",
            agent_class="coordinator",
            delegation_scope="local",
            allowed_peer_targets=("sub-specialist-01",),
            allowed_tools=("nmap", "subfinder", "httpx"),
            workflow_id="wf-test",
            program_id="prog-test",
        )

        contract = asyncio.run(
            bridge.create_subagent_contract(
                parent=coordinator,
                child_agent_id="sub-specialist-01",
                child_class="specialist",
                objective="Scan ports on target",
                phase="recon",
                allowed_tools=["nmap"],
            )
        )
        from apps.backend.src.core.praison_contracts import DelegationContract
        assert isinstance(contract, DelegationContract)
        assert contract.delegator_id == "test_coordinator"
        assert contract.delegate_id == "sub-specialist-01"
        # Event bus should have been called
        assert mock_bus.emit.called

    def test_bridge_emit_result_events(self) -> None:
        """emit_result_events emits events to EventBus."""
        mock_bus = MagicMock()
        bridge = self._make_bridge(mock_bus=mock_bus)
        result = DeepAgentResult(
            agent_id="a1",
            events=[
                {"event_type": "deep_agent_started", "detail": {}},
                {"event_type": "deep_agent_completed", "detail": {}},
            ],
        )
        ctx = _make_execution_context()
        bridge.emit_result_events(result, ctx)
        assert mock_bus.emit.call_count == 2

    def test_bridge_singleton(self) -> None:
        """get_deepagents_bridge returns the same instance on repeated calls."""
        import apps.backend.src.core.praison_deepagents_bridge as bridge_mod
        original = bridge_mod._bridge
        try:
            bridge_mod._bridge = None
            # Patch get_event_bus and get_runtime_policy to avoid side effects
            with patch(
                "apps.backend.src.core.praison_deepagents_bridge.get_event_bus",
                return_value=MagicMock(),
            ), patch(
                "apps.backend.src.core.praison_deepagents_bridge.get_runtime_policy",
                return_value=MagicMock(),
            ):
                b1 = get_deepagents_bridge()
                b2 = get_deepagents_bridge()
                assert b1 is b2
        finally:
            bridge_mod._bridge = original

    def test_bridge_validates_identity(self) -> None:
        """Invalid identity returns error result when policy rejects it."""
        mock_bus = MagicMock()
        mock_policy = MagicMock()
        mock_policy.validate_identity = MagicMock(
            return_value=["invalid agent_class: 'bogus'"]
        )
        bridge = DeepAgentsBridge(event_bus=mock_bus, runtime_policy=mock_policy)
        identity = _make_identity()
        ctx = _make_execution_context()

        result = asyncio.run(
            bridge.execute_specialist(
                identity=identity,
                specialist_type="evidence_analyst",
                task="Analyze",
                context=ctx,
            )
        )
        assert result.success is False
        assert "validation failed" in result.error.lower()


# ============================================================================
# 13. TestNoBypassPaths (4 tests)
# ============================================================================


class TestNoBypassPaths:
    """Security: prove no bypass paths for tools, models, sandbox, backends."""

    def test_deep_agent_uses_k1_model_factory(self) -> None:
        """Verify live execution paths use K1ChatModel via get_model_factory."""
        # Both _execute_native (fallback) and _execute_via_real_deepagents (real pkg)
        # must use get_model_factory for governed LLM calls.
        import inspect
        native_source = inspect.getsource(DeepAgent._execute_native)
        assert "get_model_factory" in native_source, (
            "DeepAgent._execute_native must use get_model_factory for live LLM calls"
        )
        real_source = inspect.getsource(DeepAgent._execute_via_real_deepagents)
        assert "get_model_factory" in real_source, (
            "DeepAgent._execute_via_real_deepagents must use get_model_factory"
        )

    def test_governed_tools_only(self) -> None:
        """Config uses only governed tool_ids from identity, not arbitrary tools."""
        identity = _make_identity(allowed_tools=("nmap", "subfinder"))
        agent = create_deep_agent(identity, execution_mode="graph_only")
        # tool_ids must be exactly the identity's allowed_tools
        assert agent.config.tool_ids == frozenset(identity.allowed_tools)

    def test_sandbox_blocks_host_shell_production(self) -> None:
        """Live sandbox execution is blocked without K1_SANDBOX_ALLOW_INPROCESS."""
        with patch.dict(os.environ, {"K1_SANDBOX_ALLOW_INPROCESS": "false"}):
            config = SandboxConfig.safe_default("agent1", execution_mode="live")
            handle = SandboxHandle(config)
            result = asyncio.run(handle.execute("import os; os.system('whoami')"))
            assert result.success is False

    def test_backend_path_traversal_prevented(self) -> None:
        """All backend types reject '../' paths."""
        # EphemeralBackend
        ephemeral = EphemeralBackend(BackendConfig.safe_default("a1", "t1"))
        with pytest.raises(BackendViolation):
            ephemeral.write("../escape.txt", "data")

        # ScratchBackend
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"K1_ARTIFACTS_ROOT": tmpdir}):
                scratch = create_backend("a1", "t1", "scratch", production_mode=False)
                with pytest.raises(BackendViolation):
                    scratch.write("../escape.txt", "data")

        # DurableBackend (via dev mode)
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"K1_ARTIFACTS_ROOT": tmpdir}):
                durable = create_backend("a1", "t1", "durable", production_mode=False)
                with pytest.raises(BackendViolation):
                    durable.write("../escape.txt", "data")


# ============================================================================
# 14. TestRegressionIntegration (5 tests)
# ============================================================================


class TestRegressionIntegration:
    """Regression: DeepAgents imports do not break existing platform modules."""

    def test_deepagents_imports_dont_break_existing(self) -> None:
        """Import all deepagents modules, then import praison_state, praison_node_executors."""
        # Import all deepagents modules first
        import apps.backend.src.core.praison_adapters.deepagents_adapter  # noqa: F401
        import apps.backend.src.core.praison_deepagents_bridge  # noqa: F401
        import apps.backend.src.core.praison_deepagents_backends  # noqa: F401
        import apps.backend.src.core.praison_sandbox_manager  # noqa: F401
        import apps.backend.src.core.telemetry.deepagents_stream_adapter  # noqa: F401

        # Then verify existing modules still import cleanly
        import apps.backend.src.core.praison_state  # noqa: F401
        import apps.backend.src.core.praison_node_executors  # noqa: F401

    def test_langchain_modules_still_work(self) -> None:
        """langchain_model_factory and langchain_schemas import clean after deepagents."""
        import apps.backend.src.core.langchain_model_factory  # noqa: F401
        import apps.backend.src.core.langchain_schemas  # noqa: F401

    def test_langgraph_runtime_still_imports(self) -> None:
        """praison_mission_runtime imports clean after deepagents."""
        import apps.backend.src.core.praison_mission_runtime  # noqa: F401

    def test_existing_adapter_init_still_works(self) -> None:
        """FrameworkNotInstalledError is still importable from praison_adapters.__init__."""
        from apps.backend.src.core.praison_adapters import FrameworkNotInstalledError as FNI
        assert issubclass(FNI, ImportError)
        err = FNI(framework="test", package="test-pkg", install_hint="pip install test-pkg")
        assert "test" in str(err)
        assert "test-pkg" in str(err)

    def test_all_deepagents_modules_importable(self) -> None:
        """All 5 deepagents modules import without error."""
        modules = [
            "apps.backend.src.core.praison_adapters.deepagents_adapter",
            "apps.backend.src.core.praison_deepagents_bridge",
            "apps.backend.src.core.praison_deepagents_backends",
            "apps.backend.src.core.praison_sandbox_manager",
            "apps.backend.src.core.telemetry.deepagents_stream_adapter",
        ]
        import importlib
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"Failed to import {mod_name}"


# ===========================================================================
# 15. Package Alignment — deepagents dual-path tests
# ===========================================================================

class TestDeepAgentsPackageAlignment:
    """Tests for the deepagents package alignment (dual-path architecture)."""

    # -- Availability detection ------------------------------------------------

    def test_availability_flag_is_bool(self) -> None:
        """_DEEPAGENTS_AVAILABLE is a bool."""
        assert isinstance(_DEEPAGENTS_AVAILABLE, bool)

    def test_is_deepagents_available_matches_flag(self) -> None:
        """is_deepagents_available() returns the same as _DEEPAGENTS_AVAILABLE."""
        assert is_deepagents_available() == _DEEPAGENTS_AVAILABLE

    def test_is_deepagents_backend_available_matches_flag(self) -> None:
        """is_deepagents_backend_available() returns _DEEPAGENTS_BACKEND_AVAILABLE."""
        assert is_deepagents_backend_available() == _DEEPAGENTS_BACKEND_AVAILABLE

    def test_availability_false_on_python310(self) -> None:
        """On Python 3.10 (current env), deepagents is not installed."""
        # This test documents the current state; when running on Python 3.11+
        # with deepagents installed, the flag will be True.
        import sys
        if sys.version_info < (3, 11):
            assert _DEEPAGENTS_AVAILABLE is False
            assert _DEEPAGENTS_BACKEND_AVAILABLE is False

    # -- build_k1_subagent_spec ------------------------------------------------

    def test_build_subagent_spec_from_identity(self) -> None:
        """build_k1_subagent_spec produces a SubAgent-compatible dict."""
        identity = _make_identity(
            agent_id="recon_agent",
            persona="Recon Specialist",
            description="Network reconnaissance specialist",
        )
        spec = build_k1_subagent_spec(identity)
        assert spec["name"] == "recon_agent"
        assert spec["description"] == "Network reconnaissance specialist"
        assert spec["system_prompt"] == identity.system_prompt
        assert spec["tools"] == []
        assert spec["model"] is None
        assert spec["middleware"] == []

    def test_build_subagent_spec_with_tools_and_model(self) -> None:
        """build_k1_subagent_spec accepts custom tools and model."""
        identity = _make_identity(agent_id="exploit_agent")
        mock_tools = [MagicMock(), MagicMock()]
        mock_model = MagicMock()
        spec = build_k1_subagent_spec(
            identity, tools=mock_tools, model=mock_model, middleware=[MagicMock()]
        )
        assert len(spec["tools"]) == 2
        assert spec["model"] is mock_model
        assert len(spec["middleware"]) == 1

    def test_build_subagent_spec_falls_back_to_persona(self) -> None:
        """When description is empty, uses persona instead."""
        identity = _make_identity(
            agent_id="test_agent",
            persona="TestPersona",
            description="",
        )
        spec = build_k1_subagent_spec(identity)
        assert spec["description"] == "TestPersona"

    # -- K1BackendProtocolAdapter ----------------------------------------------

    def test_adapter_wraps_ephemeral_backend(self) -> None:
        """K1BackendProtocolAdapter wraps EphemeralBackend correctly."""
        config = BackendConfig.safe_default("agent_1", "thread_1")
        backend = EphemeralBackend(config)
        adapter = create_protocol_adapter(backend)
        assert isinstance(adapter, K1BackendProtocolAdapter)
        assert adapter.wrapped_backend is backend

    def test_adapter_write_and_read(self) -> None:
        """Adapter write/read round-trip through EphemeralBackend."""
        config = BackendConfig.safe_default("agent_2", "thread_2")
        backend = EphemeralBackend(config)
        adapter = create_protocol_adapter(backend)

        # Write via adapter
        result = adapter.write("/workspace/test.txt", "hello world")
        assert result.error is None

        # Read via adapter
        content = adapter.read("/workspace/test.txt")
        assert "hello world" in content
        assert "1\t" in content  # line number format

    def test_adapter_edit(self) -> None:
        """Adapter edit replaces content in ephemeral backend."""
        config = BackendConfig.safe_default("agent_3", "thread_3")
        backend = EphemeralBackend(config)
        backend.write("test.txt", "hello world")

        adapter = create_protocol_adapter(backend)
        result = adapter.edit("/test.txt", "hello", "goodbye")
        assert result.error is None
        assert result.occurrences == 1

        content = backend.read("test.txt")
        assert content == "goodbye world"

    def test_adapter_ls_info(self) -> None:
        """Adapter ls_info lists files from ephemeral backend."""
        config = BackendConfig.safe_default("agent_4", "thread_4")
        backend = EphemeralBackend(config)
        backend.write("a.txt", "aaa")
        backend.write("b.txt", "bbb")

        adapter = create_protocol_adapter(backend)
        infos = adapter.ls_info("/")
        paths = [i["path"] for i in infos]
        assert len(paths) >= 2

    def test_adapter_grep_raw(self) -> None:
        """Adapter grep_raw searches file content."""
        config = BackendConfig.safe_default("agent_5", "thread_5")
        backend = EphemeralBackend(config)
        backend.write("code.py", "def main():\n    print('hello')\n    return 42\n")

        adapter = create_protocol_adapter(backend)
        matches = adapter.grep_raw("hello")
        assert isinstance(matches, list)
        assert len(matches) == 1
        assert matches[0]["line"] == 2
        assert "hello" in matches[0]["text"]

    def test_adapter_glob_info(self) -> None:
        """Adapter glob_info filters by pattern."""
        config = BackendConfig.safe_default("agent_6", "thread_6")
        backend = EphemeralBackend(config)
        backend.write("src/main.py", "code")
        backend.write("src/test.js", "test")
        backend.write("docs/readme.md", "readme")

        adapter = create_protocol_adapter(backend)
        py_files = adapter.glob_info("src/*.py")
        assert len(py_files) == 1
        assert "main.py" in py_files[0]["path"]

    def test_adapter_upload_download(self) -> None:
        """Adapter upload_files/download_files round-trip."""
        config = BackendConfig.safe_default("agent_7", "thread_7")
        backend = EphemeralBackend(config)
        adapter = create_protocol_adapter(backend)

        upload_results = adapter.upload_files([("/data.bin", b"binary content")])
        assert len(upload_results) == 1
        assert upload_results[0]["error"] is None

        download_results = adapter.download_files(["/data.bin"])
        assert len(download_results) == 1
        assert download_results[0]["error"] is None
        assert download_results[0]["content"] == b"binary content"

    def test_adapter_download_missing_file(self) -> None:
        """Adapter download_files returns error for missing files."""
        config = BackendConfig.safe_default("agent_8", "thread_8")
        backend = EphemeralBackend(config)
        adapter = create_protocol_adapter(backend)

        results = adapter.download_files(["/missing.txt"])
        assert results[0]["error"] == "file_not_found"
        assert results[0]["content"] is None

    def test_adapter_inherits_real_protocol_when_available(self) -> None:
        """When deepagents is installed, adapter is an instance of BackendProtocol."""
        if _DEEPAGENTS_BACKEND_AVAILABLE:
            config = BackendConfig.safe_default("agent_9", "thread_9")
            backend = EphemeralBackend(config)
            adapter = create_protocol_adapter(backend)
            from deepagents.backends.protocol import BackendProtocol
            assert isinstance(adapter, BackendProtocol)

    # -- DeepAgent execution path routing --------------------------------------

    def test_deep_agent_simulation_unaffected_by_availability(self) -> None:
        """Simulation modes always use fixture path regardless of deepagents availability."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="graph_only", specialist_type="evidence_analyst")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(agent.execute("test task"))
        finally:
            loop.close()
        assert result.success is True
        assert "[SIMULATION]" in result.output.get("text", "")

    def test_deep_agent_tool_mock_unaffected(self) -> None:
        """tool_mock mode always uses simulation path."""
        identity = _make_identity()
        agent = create_deep_agent(identity, execution_mode="tool_mock", specialist_type="triage_specialist")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(agent.execute("analyze"))
        finally:
            loop.close()
        assert result.success is True
        assert result.error == ""

    # -- Bridge dual-path awareness -------------------------------------------

    def test_bridge_build_execution_summary(self) -> None:
        """build_execution_summary includes backend field."""
        bridge = DeepAgentsBridge(event_bus=MagicMock(), runtime_policy=MagicMock(validate_identity=lambda x: []))
        result = DeepAgentResult(
            agent_id="test",
            specialist_type="evidence_analyst",
            success=True,
            iterations_used=3,
            tokens_used=1500,
            latency_ms=250.0,
            artifacts_produced=[{"artifact_id": "a1"}],
        )
        summary = bridge.build_execution_summary(result)
        assert summary["agent_id"] == "test"
        assert summary["success"] is True
        assert summary["artifacts_count"] == 1
        assert summary["backend"] in ("deepagents", "kai_native")

    def test_bridge_execution_summary_backend_matches_availability(self) -> None:
        """Execution summary backend field matches actual package availability."""
        bridge = DeepAgentsBridge()
        result = DeepAgentResult(agent_id="x")
        summary = bridge.build_execution_summary(result)
        expected = "deepagents" if _DEEPAGENTS_AVAILABLE else "kai_native"
        assert summary["backend"] == expected
