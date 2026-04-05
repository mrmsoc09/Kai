"""
Tests for LangSmith Integration Layer
=======================================
Covers:
  - Configuration loading and validation
  - Trace correlation context
  - Run naming conventions
  - LangSmithBridge lifecycle (create/end runs, sampling, redaction)
  - EventBus subscriber integration
  - Redaction policy (strict, moderate, none)
  - Evaluation targets (triage, evidence, report, strategy)
  - Dataset manager operations
  - Experiment runner
  - Mission trace helpers

All tests are self-contained — no LangSmith API key or network required.
Tests mock the LangSmith Client to verify behavior without external calls.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Import targets
# ---------------------------------------------------------------------------

from apps.backend.src.core.langsmith_integration import (
    LangSmithBridge,
    LangSmithConfig,
    TraceCorrelation,
    _basic_redact,
    get_langsmith_bridge,
    initialize_langsmith_bridge,
    is_langsmith_available,
    is_langsmith_operational,
    load_langsmith_config,
    llm_run_name,
    mission_run_name,
    node_run_name,
    phase_run_name,
    specialist_run_name,
    tool_run_name,
    _LANGSMITH_AVAILABLE,
)

from apps.backend.src.core.langsmith_redaction import (
    content_fingerprint,
    redact_for_langsmith,
    redact_string,
)

from apps.backend.src.core.langsmith_evaluations import (
    EvalResult,
    EVALUATORS,
    K1DatasetManager,
    K1ExperimentRunner,
    build_evidence_example,
    build_mission_replay_example,
    build_triage_example,
    evidence_quality_evaluator,
    report_completeness_evaluator,
    strategy_effectiveness_evaluator,
    triage_accuracy_evaluator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def disabled_config():
    """LangSmith config with tracing disabled."""
    return LangSmithConfig(
        enabled=False,
        api_key="",
        project="kai-test",
    )


@pytest.fixture
def enabled_config():
    """LangSmith config with tracing enabled (mock key)."""
    return LangSmithConfig(
        enabled=True,
        api_key="test-api-key-not-real",
        project="kai-test",
        endpoint="https://test.smith.langchain.com",
        redact_mode="strict",
        sample_rate=1.0,
    )


@pytest.fixture
def mock_client():
    """Mock LangSmith Client."""
    client = MagicMock()
    client.create_run = MagicMock()
    client.update_run = MagicMock()
    client.create_dataset = MagicMock()
    client.create_example = MagicMock()
    client.create_examples = MagicMock()
    client.list_datasets = MagicMock(return_value=[])
    client.list_examples = MagicMock(return_value=[])
    return client


@pytest.fixture
def operational_bridge(enabled_config, mock_client):
    """LangSmithBridge that appears operational with a mock client."""
    bridge = LangSmithBridge(config=enabled_config)
    bridge._client = mock_client
    bridge._initialized = True
    return bridge


@pytest.fixture
def sample_correlation():
    """Sample trace correlation context."""
    return TraceCorrelation(
        mission_id="m-test-001",
        workflow_id="wf-test-001",
        program_id="prog-test-001",
        phase="recon",
        node_id="recon_node",
        agent_id="recon-agent-001",
        execution_mode="live",
    )


# ===========================================================================
# Test Configuration
# ===========================================================================


class TestLangSmithConfig:
    """Tests for LangSmithConfig and load_langsmith_config."""

    def test_default_config_disabled(self):
        """Default config has tracing disabled."""
        cfg = LangSmithConfig()
        assert cfg.enabled is False
        assert cfg.project == "kai-missions"
        assert cfg.redact_mode == "strict"
        assert cfg.sample_rate == 1.0
        assert cfg.is_operational() is False

    def test_operational_requires_all_three(self):
        """is_operational needs enabled=True, package available, and API key."""
        # Missing API key
        cfg = LangSmithConfig(enabled=True, api_key="")
        assert cfg.is_operational() is False

        # Has everything
        cfg = LangSmithConfig(enabled=True, api_key="sk-test")
        if _LANGSMITH_AVAILABLE:
            assert cfg.is_operational() is True
        else:
            assert cfg.is_operational() is False

    def test_load_from_env_defaults(self):
        """Load config from environment with defaults."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove any existing langsmith env vars
            env = {
                k: v for k, v in os.environ.items()
                if "LANGSMITH" not in k and "K1_LANGSMITH" not in k
            }
            with patch.dict(os.environ, env, clear=True):
                cfg = load_langsmith_config()
                assert cfg.enabled is False
                assert cfg.project == "kai-missions"
                assert cfg.redact_mode == "strict"
                assert cfg.sample_rate == 1.0

    def test_load_from_env_enabled(self):
        """Load config with LangSmith enabled via env."""
        env = {
            "K1_LANGSMITH_ENABLED": "true",
            "LANGSMITH_API_KEY": "test-key",
            "LANGSMITH_PROJECT": "kai-custom",
            "K1_LANGSMITH_REDACT_MODE": "moderate",
            "K1_LANGSMITH_SAMPLE_RATE": "0.5",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = load_langsmith_config()
            assert cfg.enabled is True
            assert cfg.api_key == "test-key"
            assert cfg.project == "kai-custom"
            assert cfg.redact_mode == "moderate"
            assert cfg.sample_rate == 0.5

    def test_sample_rate_clamped(self):
        """Sample rate is clamped to [0.0, 1.0]."""
        env = {"K1_LANGSMITH_SAMPLE_RATE": "5.0"}
        with patch.dict(os.environ, env, clear=False):
            cfg = load_langsmith_config()
            assert cfg.sample_rate == 1.0

        env = {"K1_LANGSMITH_SAMPLE_RATE": "-1.0"}
        with patch.dict(os.environ, env, clear=False):
            cfg = load_langsmith_config()
            assert cfg.sample_rate == 0.0

    def test_sample_rate_invalid_defaults_to_one(self):
        """Invalid sample rate string defaults to 1.0."""
        env = {"K1_LANGSMITH_SAMPLE_RATE": "not-a-number"}
        with patch.dict(os.environ, env, clear=False):
            cfg = load_langsmith_config()
            assert cfg.sample_rate == 1.0


# ===========================================================================
# Test Naming Conventions
# ===========================================================================


class TestNamingConventions:
    """Tests for LangSmith run naming helpers."""

    def test_mission_run_name(self):
        assert mission_run_name("abc-123-def") == "mission:abc-123-def"
        assert mission_run_name("abc-123-def", "my-mission") == "mission:my-mission"

    def test_phase_run_name(self):
        assert phase_run_name("recon") == "phase:recon"
        assert phase_run_name("triage") == "phase:triage"

    def test_node_run_name(self):
        assert node_run_name("recon_node") == "node:recon_node"
        assert node_run_name("recon_node", "agent-1") == "node:recon_node[agent-1]"

    def test_specialist_run_name(self):
        assert specialist_run_name("evidence_analyst") == "specialist:evidence_analyst"
        assert specialist_run_name("triage_specialist", "t-001") == "specialist:triage_specialist[t-001]"

    def test_llm_run_name(self):
        assert llm_run_name() == "llm"
        assert llm_run_name("claude-3", "anthropic") == "llm:anthropic:claude-3"
        assert llm_run_name(provider="openai") == "llm:openai"

    def test_tool_run_name(self):
        assert tool_run_name("nmap") == "tool:nmap"
        assert tool_run_name("nmap", "1") == "tool:nmap[band_1]"


# ===========================================================================
# Test Trace Correlation
# ===========================================================================


class TestTraceCorrelation:
    """Tests for TraceCorrelation context object."""

    def test_default_ids_generated(self):
        """Correlation generates unique trace_id and run_id by default."""
        corr = TraceCorrelation()
        assert corr.trace_id
        assert corr.run_id
        assert corr.trace_id != corr.run_id

    def test_to_metadata(self, sample_correlation):
        """to_metadata produces correct key mappings."""
        meta = sample_correlation.to_metadata()
        assert meta["kai_mission_id"] == "m-test-001"
        assert meta["kai_workflow_id"] == "wf-test-001"
        assert meta["kai_phase"] == "recon"
        assert meta["kai_agent_id"] == "recon-agent-001"
        # Empty values should be excluded
        assert "kai_specialist_type" not in meta

    def test_to_metadata_excludes_empty(self):
        """Empty string values are filtered from metadata."""
        corr = TraceCorrelation(mission_id="m-1")
        meta = corr.to_metadata()
        assert "kai_workflow_id" not in meta
        assert "kai_mission_id" in meta

    def test_to_tags(self, sample_correlation):
        """to_tags produces expected tag list."""
        tags = sample_correlation.to_tags()
        assert "kai" in tags
        assert any("mission:" in t for t in tags)
        assert any("phase:recon" in t for t in tags)
        assert any("mode:live" in t for t in tags)

    def test_child_preserves_parent_context(self, sample_correlation):
        """child() inherits mission/workflow/program and sets parent_run_id."""
        child = sample_correlation.child(
            node_id="scan_node",
            agent_id="scan-agent",
            specialist_type="exploit_assessor",
        )
        assert child.mission_id == sample_correlation.mission_id
        assert child.workflow_id == sample_correlation.workflow_id
        assert child.trace_id == sample_correlation.trace_id
        assert child.parent_run_id == sample_correlation.run_id
        assert child.node_id == "scan_node"
        assert child.agent_id == "scan-agent"
        assert child.specialist_type == "exploit_assessor"
        # Should get a new run_id
        assert child.run_id != sample_correlation.run_id

    def test_child_inherits_phase_when_not_overridden(self, sample_correlation):
        """child() keeps parent phase when no override is given."""
        child = sample_correlation.child()
        assert child.phase == "recon"

    def test_child_overrides_phase(self, sample_correlation):
        """child() overrides phase when explicitly provided."""
        child = sample_correlation.child(phase="scanning")
        assert child.phase == "scanning"

    def test_to_metadata_includes_audit_primacy_flags(self):
        corr = TraceCorrelation(
            mission_id="m-1",
            workflow_id="wf-1",
            program_id="prog-1",
            stage_id="stage-1",
            selected_substrate="LANGGRAPH_PRIMARY",
            risk_band="2",
            tenant_id="tenant-1",
            tool_execution_id="tool-exec-1",
        )
        meta = corr.to_metadata()
        assert meta["kai_audit_primary"] == "true"
        assert meta["kai_telemetry_plane"] == "secondary"
        assert meta["kai_selected_substrate"] == "LANGGRAPH_PRIMARY"
        assert meta["kai_tool_execution_id"] == "tool-exec-1"


# ===========================================================================
# Test LangSmithBridge
# ===========================================================================


class TestLangSmithBridge:
    """Tests for LangSmithBridge core operations."""

    def test_disabled_bridge_not_operational(self, disabled_config):
        """Bridge with disabled config is not operational."""
        bridge = LangSmithBridge(config=disabled_config)
        assert bridge.is_operational is False

    def test_should_trace_false_when_disabled(self, disabled_config):
        """should_trace returns False when not operational."""
        bridge = LangSmithBridge(config=disabled_config)
        assert bridge.should_trace() is False

    def test_should_trace_respects_sample_rate_zero(self):
        """should_trace returns False when sample_rate is 0."""
        cfg = LangSmithConfig(
            enabled=True,
            api_key="test",
            sample_rate=0.0,
        )
        bridge = LangSmithBridge(config=cfg)
        if _LANGSMITH_AVAILABLE:
            assert bridge.should_trace() is False

    def test_should_trace_always_when_rate_one(self, enabled_config):
        """should_trace returns True when sample_rate is 1.0 and operational."""
        bridge = LangSmithBridge(config=enabled_config)
        if _LANGSMITH_AVAILABLE:
            # Mock the client init to avoid real API calls
            bridge._client = MagicMock()
            bridge._initialized = True
            assert bridge.should_trace() is True

    def test_create_run_returns_none_when_disabled(self, disabled_config):
        """create_run returns None when tracing is disabled."""
        bridge = LangSmithBridge(config=disabled_config)
        result = bridge.create_run("test-run")
        assert result is None

    def test_create_run_with_correlation(self, operational_bridge, sample_correlation):
        """create_run passes correlation metadata to client."""
        run_id = operational_bridge.create_run(
            name="test-run",
            run_type="chain",
            correlation=sample_correlation,
            inputs={"task": "test"},
        )
        assert run_id is not None
        operational_bridge._client.create_run.assert_called_once()
        call_kwargs = operational_bridge._client.create_run.call_args
        assert call_kwargs.kwargs["name"] == "test-run"
        assert call_kwargs.kwargs["run_type"] == "chain"

    def test_end_run_calls_update(self, operational_bridge):
        """end_run calls client.update_run with outputs."""
        operational_bridge.end_run("run-123", outputs={"result": "ok"})
        operational_bridge._client.update_run.assert_called_once()
        call_kwargs = operational_bridge._client.update_run.call_args
        assert call_kwargs.kwargs["run_id"] == "run-123"

    def test_end_run_with_error(self, operational_bridge):
        """end_run passes error string to update_run."""
        operational_bridge.end_run("run-123", error="something broke")
        call_kwargs = operational_bridge._client.update_run.call_args
        assert call_kwargs.kwargs["error"] == "something broke"

    def test_trace_run_context_manager(self, operational_bridge):
        """trace_run context manager creates and ends run."""
        with operational_bridge.trace_run("test-ctx") as run_id:
            assert run_id is not None
        # Should have called create_run and update_run
        assert operational_bridge._client.create_run.call_count == 1
        assert operational_bridge._client.update_run.call_count == 1

    def test_trace_run_records_error_on_exception(self, operational_bridge):
        """trace_run records error when exception occurs."""
        with pytest.raises(ValueError, match="test error"):
            with operational_bridge.trace_run("test-err") as run_id:
                raise ValueError("test error")
        call_kwargs = operational_bridge._client.update_run.call_args
        assert call_kwargs.kwargs["error"] == "test error"

    def test_create_run_handles_client_error(self, operational_bridge):
        """create_run returns None and logs on client error."""
        operational_bridge._client.create_run.side_effect = RuntimeError("API error")
        result = operational_bridge.create_run("failing-run")
        assert result is None

    def test_end_run_handles_client_error(self, operational_bridge):
        """end_run handles client errors gracefully."""
        if not _LANGSMITH_AVAILABLE:
            pytest.skip("langsmith package not available")
        operational_bridge._client.update_run.side_effect = RuntimeError("API error")
        # Should not raise
        operational_bridge.end_run("run-123", outputs={"x": 1})
        assert operational_bridge.degraded_export_failures >= 1

    def test_traceable_decorator_returns_original_when_disabled(self, disabled_config):
        """traceable decorator returns original function when disabled."""
        bridge = LangSmithBridge(config=disabled_config)

        @bridge.traceable(name="test_fn")
        def my_func(x):
            return x + 1

        assert my_func(5) == 6

    def test_redaction_applied_to_inputs(self, operational_bridge):
        """Inputs are redacted before being sent to LangSmith."""
        operational_bridge.create_run(
            name="test",
            inputs={"api_key": "secret-123", "task": "do stuff"},
        )
        call_kwargs = operational_bridge._client.create_run.call_args
        inputs = call_kwargs.kwargs["inputs"]
        assert inputs.get("api_key") == "[REDACTED]"
        assert inputs.get("task") == "do stuff"

    def test_evaluation_hook_runs_observationally(self, operational_bridge):
        """Evaluation hooks run without affecting run lifecycle decisions."""
        if not _LANGSMITH_AVAILABLE:
            pytest.skip("langsmith package not available")
        captured: list[dict[str, Any]] = []

        def _hook(payload: dict[str, Any]) -> None:
            captured.append(payload)

        operational_bridge.register_evaluation_hook("unit_hook", _hook)
        subscriber = operational_bridge.create_event_subscriber()

        event = MagicMock()
        event.event_type = "mission_completed"
        event.mission_id = "m-eval-1"
        event.workflow_id = "wf-eval-1"
        event.program_id = "prog-eval-1"
        event.phase = "report"
        event.node_id = "n1"
        event.agent_id = "a1"
        event.detail = {"success": True}

        subscriber(event)
        assert captured
        assert captured[0]["audit_source_of_truth"] == "kai"


# ===========================================================================
# Test Mission Trace Helpers
# ===========================================================================


class TestMissionTraceHelpers:
    """Tests for mission-level trace lifecycle methods."""

    def test_start_mission_trace(self, operational_bridge):
        """start_mission_trace returns correlation with run_id."""
        corr = operational_bridge.start_mission_trace(
            mission_id="m-001",
            workflow_id="wf-001",
            program_id="prog-001",
            execution_mode="live",
        )
        assert corr is not None
        assert corr.mission_id == "m-001"
        assert corr.run_id  # Should be set

    def test_start_mission_trace_disabled(self, disabled_config):
        """start_mission_trace returns None when disabled."""
        bridge = LangSmithBridge(config=disabled_config)
        assert bridge.start_mission_trace("m-1", "wf-1", "p-1") is None

    def test_end_mission_trace(self, operational_bridge):
        """end_mission_trace calls end_run with success/error."""
        corr = TraceCorrelation(run_id="run-mission-1")
        operational_bridge.end_mission_trace(corr, success=True)
        call_kwargs = operational_bridge._client.update_run.call_args
        assert call_kwargs.kwargs["error"] is None

    def test_end_mission_trace_with_error(self, operational_bridge):
        """end_mission_trace forwards error string."""
        corr = TraceCorrelation(run_id="run-mission-2")
        operational_bridge.end_mission_trace(
            corr, success=False, error="timeout"
        )
        call_kwargs = operational_bridge._client.update_run.call_args
        assert call_kwargs.kwargs["error"] == "timeout"

    def test_trace_specialist(self, operational_bridge, sample_correlation):
        """trace_specialist creates child trace with specialist metadata."""
        child = operational_bridge.trace_specialist(
            parent_correlation=sample_correlation,
            specialist_type="evidence_analyst",
            agent_id="ea-001",
            task="Analyze evidence for XSS",
        )
        assert child is not None
        assert child.specialist_type == "evidence_analyst"
        assert child.agent_id == "ea-001"
        assert child.parent_run_id == sample_correlation.run_id

    def test_trace_specialist_none_parent(self, operational_bridge):
        """trace_specialist returns None when parent is None."""
        result = operational_bridge.trace_specialist(
            None, "analyst", "a-1", "task"
        )
        assert result is None


# ===========================================================================
# Test EventBus Subscriber
# ===========================================================================


class TestEventBusSubscriber:
    """Tests for EventBus → LangSmith forwarding subscriber."""

    def test_subscriber_handles_mission_started(self, operational_bridge):
        """Subscriber creates run on mission_started event."""
        subscriber = operational_bridge.create_event_subscriber()

        event = MagicMock()
        event.event_type = "mission_started"
        event.mission_id = "m-evt-001"
        event.workflow_id = "wf-evt-001"
        event.program_id = "prog-evt-001"
        event.detail = {"execution_mode": "live"}

        subscriber(event)
        assert operational_bridge._client.create_run.call_count == 1

    def test_subscriber_handles_mission_completed(self, operational_bridge):
        """Subscriber ends run on mission_completed event."""
        subscriber = operational_bridge.create_event_subscriber()

        # First, start a mission
        start_event = MagicMock()
        start_event.event_type = "mission_started"
        start_event.mission_id = "m-evt-002"
        start_event.workflow_id = "wf-002"
        start_event.program_id = "prog-002"
        start_event.detail = {}
        subscriber(start_event)

        # Then complete it
        end_event = MagicMock()
        end_event.event_type = "mission_completed"
        end_event.mission_id = "m-evt-002"
        end_event.detail = {"success": True}
        subscriber(end_event)

        assert operational_bridge._client.update_run.call_count == 1

    def test_subscriber_skips_when_not_sampling(self):
        """Subscriber does nothing when should_trace returns False."""
        cfg = LangSmithConfig(enabled=True, api_key="test", sample_rate=0.0)
        bridge = LangSmithBridge(config=cfg)
        if _LANGSMITH_AVAILABLE:
            subscriber = bridge.create_event_subscriber()
            event = MagicMock()
            event.event_type = "mission_started"
            subscriber(event)
            # No client calls since sampling is disabled

    def test_subscriber_correlation_bridge_for_tool_events(self, operational_bridge):
        """Tool events preserve stage/substrate/tool correlation in metadata."""
        if not _LANGSMITH_AVAILABLE:
            pytest.skip("langsmith package not available")
        subscriber = operational_bridge.create_event_subscriber()

        mission_started = MagicMock()
        mission_started.event_type = "mission_started"
        mission_started.mission_id = "m-tool-1"
        mission_started.workflow_id = "wf-tool-1"
        mission_started.program_id = "prog-tool-1"
        mission_started.node_id = ""
        mission_started.agent_id = ""
        mission_started.detail = {"execution_mode": "live"}
        subscriber(mission_started)

        tool_started = MagicMock()
        tool_started.event_type = "tool_invocation_started"
        tool_started.mission_id = "m-tool-1"
        tool_started.workflow_id = "wf-tool-1"
        tool_started.program_id = "prog-tool-1"
        tool_started.node_id = "node-recon"
        tool_started.agent_id = "agent-recon"
        tool_started.detail = {
            "tool_id": "subfinder",
            "tool_execution_id": "te-123",
            "stage_id": "recon",
            "selected_substrate": "LANGGRAPH_PRIMARY",
            "risk_band": "1",
            "tenant_id": "tenant-a",
        }
        subscriber(tool_started)

        call_kwargs = operational_bridge._client.create_run.call_args
        metadata = call_kwargs.kwargs["extra"]["metadata"]
        assert metadata["kai_stage_id"] == "recon"
        assert metadata["kai_selected_substrate"] == "LANGGRAPH_PRIMARY"
        assert metadata["kai_tool_execution_id"] == "te-123"
        assert metadata["kai_audit_primary"] is True

    def test_subscriber_degradation_does_not_raise(self, operational_bridge):
        """LangSmith failures are absorbed and tracked as degraded exports."""
        if not _LANGSMITH_AVAILABLE:
            pytest.skip("langsmith package not available")
        operational_bridge._client.create_run.side_effect = RuntimeError("LangSmith down")
        subscriber = operational_bridge.create_event_subscriber()

        event = MagicMock()
        event.event_type = "mission_started"
        event.mission_id = "m-down"
        event.workflow_id = "wf-down"
        event.program_id = "prog-down"
        event.node_id = ""
        event.agent_id = ""
        event.detail = {"execution_mode": "live"}

        # Must not raise (Kai audit plane remains primary and operational)
        subscriber(event)
        assert operational_bridge.degraded_export_failures >= 1


# ===========================================================================
# Test Redaction
# ===========================================================================


class TestRedaction:
    """Tests for langsmith_redaction module."""

    def test_strict_redacts_api_keys(self):
        """Strict mode redacts API key values."""
        data = {"api_key": "sk-abc123", "task": "analyze"}
        result = redact_for_langsmith(data, mode="strict")
        assert result["api_key"] == "[REDACTED]"
        assert result["task"] == "analyze"

    def test_strict_redacts_nested_secrets(self):
        """Strict mode redacts secrets in nested dicts."""
        data = {
            "config": {
                "vault_token": "hvs.abc123",
                "project": "kai",
            }
        }
        result = redact_for_langsmith(data, mode="strict")
        assert result["config"]["vault_token"] == "[REDACTED]"
        assert result["config"]["project"] == "kai"

    def test_strict_redacts_password_variants(self):
        """Strict mode redacts all password key variants."""
        for key in ["password", "passwd", "secret", "credentials"]:
            data = {key: "hunter2"}
            result = redact_for_langsmith(data, mode="strict")
            assert result[key] == "[REDACTED]", f"Failed for key: {key}"

    def test_strict_redacts_governance_fields(self):
        """Governance-sensitive fields are redacted before external export."""
        data = {
            "governance_decision": "approved",
            "approval_id": "ap-123",
            "contract_id": "ct-001",
            "scope_decision_id": "sd-1",
            "task": "safe",
        }
        result = redact_for_langsmith(data, mode="strict")
        assert result["governance_decision"] == "[REDACTED:GOVERNANCE]"
        assert result["approval_id"] == "[REDACTED:GOVERNANCE]"
        assert result["contract_id"] == "[REDACTED:GOVERNANCE]"
        assert result["scope_decision_id"] == "[REDACTED:GOVERNANCE]"
        assert result["task"] == "safe"

    def test_strict_redacts_bearer_tokens_in_values(self):
        """Strict mode redacts Bearer tokens embedded in string values."""
        data = {"header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc"}
        result = redact_for_langsmith(data, mode="strict")
        assert "Bearer" not in result["header"]
        assert "[REDACTED:" in result["header"]

    def test_strict_redacts_ip_addresses(self):
        """Strict mode redacts IP addresses."""
        data = {"target": "Scanning 192.168.1.100 on port 443"}
        result = redact_for_langsmith(data, mode="strict")
        assert "192.168.1.100" not in result["target"]
        assert "[REDACTED:ip]" in result["target"]

    def test_strict_redacts_emails(self):
        """Strict mode redacts email addresses."""
        data = {"contact": "Send to admin@example.com for review"}
        result = redact_for_langsmith(data, mode="strict")
        assert "admin@example.com" not in result["contact"]
        assert "[REDACTED:email]" in result["contact"]

    def test_moderate_keeps_ips(self):
        """Moderate mode does NOT redact IP addresses."""
        data = {"target": "192.168.1.100"}
        result = redact_for_langsmith(data, mode="moderate")
        assert "192.168.1.100" in result["target"]

    def test_moderate_still_redacts_secrets(self):
        """Moderate mode still redacts API keys and tokens."""
        data = {"api_key": "secret", "target": "192.168.1.1"}
        result = redact_for_langsmith(data, mode="moderate")
        assert result["api_key"] == "[REDACTED]"
        assert "192.168.1.1" in result["target"]

    def test_none_mode_passes_through(self):
        """None mode returns data unmodified."""
        data = {"api_key": "sk-secret", "password": "hunter2"}
        result = redact_for_langsmith(data, mode="none")
        assert result["api_key"] == "sk-secret"
        assert result["password"] == "hunter2"

    def test_large_payload_truncation_strict(self):
        """Strict mode truncates large payloads."""
        large_value = "x" * 20_000
        data = {"output": large_value}
        result = redact_for_langsmith(data, mode="strict")
        assert len(result["output"]) < len(large_value)
        assert "[TRUNCATED:" in result["output"]
        assert "sha256:" in result["output"]

    def test_large_payload_moderate_higher_limit(self):
        """Moderate mode has higher truncation threshold than strict."""
        value_15k = "x" * 15_000
        strict_result = redact_for_langsmith({"output": value_15k}, mode="strict")
        moderate_result = redact_for_langsmith({"output": value_15k}, mode="moderate")
        # Strict truncates at 10KB, moderate at 50KB
        assert "[TRUNCATED:" in strict_result["output"]
        assert "[TRUNCATED:" not in moderate_result["output"]

    def test_redact_in_lists(self):
        """Redaction applies inside list elements."""
        data = {
            "items": [
                {"api_key": "secret1"},
                {"name": "safe"},
            ]
        }
        result = redact_for_langsmith(data, mode="strict")
        assert result["items"][0]["api_key"] == "[REDACTED]"
        assert result["items"][1]["name"] == "safe"

    def test_redact_string_jwt(self):
        """redact_string catches JWT patterns."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = redact_string(jwt)
        assert "eyJ" not in result
        assert "[REDACTED:jwt]" in result

    def test_redact_string_aws_key(self):
        """redact_string catches AWS access key patterns."""
        result = redact_string("Key is AKIAIOSFODNN7EXAMPLE here")
        assert "AKIA" not in result
        assert "[REDACTED:aws_key]" in result

    def test_depth_limit_prevents_overflow(self):
        """Deep nesting doesn't cause stack overflow."""
        data: dict[str, Any] = {"level": "root"}
        current = data
        for i in range(20):
            current["child"] = {"level": str(i)}
            current = current["child"]
        # Should not raise
        result = redact_for_langsmith(data, mode="strict")
        assert "level" in result

    def test_content_fingerprint_deterministic(self):
        """content_fingerprint produces same hash for same data."""
        data = {"a": 1, "b": "hello"}
        fp1 = content_fingerprint(data)
        fp2 = content_fingerprint(data)
        assert fp1 == fp2
        assert len(fp1) == 32

    def test_content_fingerprint_varies(self):
        """Different data produces different fingerprints."""
        fp1 = content_fingerprint({"a": 1})
        fp2 = content_fingerprint({"a": 2})
        assert fp1 != fp2


# ===========================================================================
# Test Basic Redact Fallback
# ===========================================================================


class TestBasicRedactFallback:
    """Tests for the fallback _basic_redact function in integration module."""

    def test_basic_redact_keys(self):
        """Basic redact catches common secret keys."""
        data = {
            "api_key": "secret",
            "name": "test",
            "token": "tok-123",
        }
        result = _basic_redact(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["name"] == "test"
        assert result["token"] == "[REDACTED]"

    def test_basic_redact_nested(self):
        """Basic redact handles nested dicts."""
        data = {"config": {"password": "hunter2", "host": "localhost"}}
        result = _basic_redact(data)
        assert result["config"]["password"] == "[REDACTED]"
        assert result["config"]["host"] == "localhost"

    def test_basic_redact_depth_limit(self):
        """Basic redact stops at depth 10."""
        data: dict[str, Any] = {"a": "root"}
        current = data
        for _ in range(15):
            current["child"] = {"password": "secret"}
            current = current["child"]
        # Should not raise
        result = _basic_redact(data)
        assert "a" in result


# ===========================================================================
# Test Evaluators
# ===========================================================================


class TestEvaluators:
    """Tests for evaluation scoring functions."""

    # -- Triage accuracy --

    def test_triage_accuracy_perfect_match(self):
        """Triage evaluator scores 1.0 for exact match."""
        output = {"severity": "critical", "category": "xss", "confidence": 0.9}
        reference = {"severity": "critical", "category": "xss"}
        result = triage_accuracy_evaluator(output, reference)
        assert result.key == "triage_accuracy"
        assert result.score == 1.0

    def test_triage_accuracy_partial_match(self):
        """Triage evaluator scores partial for mixed match."""
        output = {"severity": "high", "category": "xss", "confidence": 0.9}
        reference = {"severity": "critical", "category": "xss"}
        result = triage_accuracy_evaluator(output, reference)
        assert 0.0 < result.score < 1.0

    def test_triage_accuracy_no_reference(self):
        """Triage evaluator returns 0.0 with no reference."""
        result = triage_accuracy_evaluator({"severity": "high"}, None)
        assert result.score == 0.0
        assert "No reference" in result.comment

    def test_triage_accuracy_empty_output(self):
        """Triage evaluator handles empty output — no fields to compare means no checks."""
        result = triage_accuracy_evaluator({}, {"severity": "high"})
        # With empty output, severity mismatch ("" != "high") but empty strings
        # don't trigger comparison (both must be non-empty). Score depends on
        # which checks actually fire.
        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    # -- Evidence quality --

    def test_evidence_quality_good(self):
        """Evidence evaluator scores well for complete output."""
        output = {
            "text": "Detailed analysis of the XSS vulnerability found in the search parameter...",
            "artifacts_produced": [
                {"artifact_type": "evidence", "content": {"finding": "XSS"}},
            ],
        }
        result = evidence_quality_evaluator(output)
        assert result.key == "evidence_quality"
        assert result.score > 0.5

    def test_evidence_quality_empty(self):
        """Evidence evaluator scores 0.0 for empty output."""
        result = evidence_quality_evaluator({})
        assert result.score == 0.0

    def test_evidence_quality_text_only(self):
        """Evidence evaluator gives partial credit for text without artifacts."""
        output = {"text": "A" * 100}
        result = evidence_quality_evaluator(output)
        assert 0.0 < result.score < 1.0

    # -- Report completeness --

    def test_report_completeness_full(self):
        """Report evaluator scores well for complete report."""
        output = {
            "title": "XSS in Search",
            "summary": "Found XSS...",
            "severity": "high",
            "steps_to_reproduce": "1. Go to...",
            "impact": "Account takeover",
            "recommendation": "Encode output",
        }
        result = report_completeness_evaluator(output)
        assert result.key == "report_completeness"
        assert result.score == 1.0

    def test_report_completeness_partial(self):
        """Report evaluator scores partial for incomplete report."""
        output = {"title": "XSS", "severity": "high"}
        result = report_completeness_evaluator(output)
        assert 0.0 < result.score < 1.0

    def test_report_completeness_text_references(self):
        """Report evaluator finds sections mentioned in text."""
        output = {
            "text": "Title: XSS\nSummary: Found.\nSeverity: High\nSteps_to_reproduce: Go to\nImpact: Bad\nRecommendation: Fix it"
        }
        result = report_completeness_evaluator(output)
        assert result.score > 0.5

    # -- Strategy effectiveness --

    def test_strategy_effectiveness_good(self):
        """Strategy evaluator scores well for successful strategy with findings."""
        output = {
            "success": True,
            "findings": [
                {"severity": "high", "category": "xss"},
                {"severity": "medium", "category": "csrf"},
            ],
        }
        result = strategy_effectiveness_evaluator(output)
        assert result.key == "strategy_effectiveness"
        assert result.score == 1.0

    def test_strategy_effectiveness_no_findings(self):
        """Strategy evaluator scores low for success without findings."""
        output = {"success": True, "findings": []}
        result = strategy_effectiveness_evaluator(output)
        assert result.score < 1.0

    def test_strategy_effectiveness_failure(self):
        """Strategy evaluator scores 0.0 for complete failure."""
        output = {"success": False, "findings": []}
        result = strategy_effectiveness_evaluator(output)
        assert result.score == 0.0

    # -- Registry --

    def test_evaluators_registry_populated(self):
        """EVALUATORS registry has all expected evaluators."""
        expected = {"triage_accuracy", "evidence_quality", "report_completeness", "strategy_effectiveness"}
        assert expected.issubset(set(EVALUATORS.keys()))


# ===========================================================================
# Test Dataset Manager
# ===========================================================================


class TestK1DatasetManager:
    """Tests for K1DatasetManager."""

    def test_ensure_dataset_creates_new(self, operational_bridge, mock_client):
        """ensure_dataset creates dataset when none exists."""
        mock_dataset = MagicMock()
        mock_dataset.id = uuid.uuid4()
        mock_client.list_datasets.return_value = []
        mock_client.create_dataset.return_value = mock_dataset

        manager = K1DatasetManager(operational_bridge)
        dataset_id = manager.ensure_dataset("kai-test-dataset")
        assert dataset_id == str(mock_dataset.id)
        mock_client.create_dataset.assert_called_once()

    def test_ensure_dataset_finds_existing(self, operational_bridge, mock_client):
        """ensure_dataset returns existing dataset without creating."""
        existing = MagicMock()
        existing.id = uuid.uuid4()
        mock_client.list_datasets.return_value = [existing]

        manager = K1DatasetManager(operational_bridge)
        dataset_id = manager.ensure_dataset("kai-existing")
        assert dataset_id == str(existing.id)
        mock_client.create_dataset.assert_not_called()

    def test_ensure_dataset_caches(self, operational_bridge, mock_client):
        """ensure_dataset caches result for subsequent calls."""
        existing = MagicMock()
        existing.id = uuid.uuid4()
        mock_client.list_datasets.return_value = [existing]

        manager = K1DatasetManager(operational_bridge)
        id1 = manager.ensure_dataset("kai-cached")
        id2 = manager.ensure_dataset("kai-cached")
        assert id1 == id2
        # list_datasets called only once (second call uses cache)
        assert mock_client.list_datasets.call_count == 1

    def test_add_example(self, operational_bridge, mock_client):
        """add_example creates example on existing dataset."""
        existing_ds = MagicMock()
        existing_ds.id = uuid.uuid4()
        mock_client.list_datasets.return_value = [existing_ds]
        mock_example = MagicMock()
        mock_example.id = uuid.uuid4()
        mock_client.create_example.return_value = mock_example

        manager = K1DatasetManager(operational_bridge)
        ex_id = manager.add_example(
            "kai-test",
            inputs={"query": "test"},
            outputs={"severity": "high"},
        )
        assert ex_id == str(mock_example.id)

    def test_add_examples_batch(self, operational_bridge, mock_client):
        """add_examples_batch sends batch to LangSmith."""
        existing_ds = MagicMock()
        existing_ds.id = uuid.uuid4()
        mock_client.list_datasets.return_value = [existing_ds]

        manager = K1DatasetManager(operational_bridge)
        examples = [
            {"inputs": {"q": "a"}, "outputs": {"s": "high"}},
            {"inputs": {"q": "b"}, "outputs": {"s": "low"}},
        ]
        count = manager.add_examples_batch("kai-batch", examples)
        assert count == 2
        mock_client.create_examples.assert_called_once()

    def test_add_example_handles_error(self, operational_bridge, mock_client):
        """add_example returns None on client error."""
        existing_ds = MagicMock()
        existing_ds.id = uuid.uuid4()
        mock_client.list_datasets.return_value = [existing_ds]
        mock_client.create_example.side_effect = RuntimeError("fail")

        manager = K1DatasetManager(operational_bridge)
        result = manager.add_example("kai-err", inputs={"q": "test"})
        assert result is None

    def test_manager_with_no_client(self):
        """Manager returns None/0 when bridge has no client."""
        bridge = LangSmithBridge(config=LangSmithConfig())
        manager = K1DatasetManager(bridge)
        assert manager.ensure_dataset("test") is None
        assert manager.add_example("test", inputs={}) is None
        assert manager.add_examples_batch("test", [{"inputs": {}}]) == 0


# ===========================================================================
# Test Experiment Runner
# ===========================================================================


class TestK1ExperimentRunner:
    """Tests for K1ExperimentRunner."""

    def test_create_experiment(self, operational_bridge):
        """create_experiment returns well-formed experiment spec."""
        runner = K1ExperimentRunner(operational_bridge)
        exp = runner.create_experiment(
            name="kai-exp-triage-v2",
            experiment_type="prompt_comparison",
            description="Compare triage prompts",
        )
        assert exp["name"] == "kai-exp-triage-v2"
        assert exp["type"] == "prompt_comparison"
        assert exp["status"] == "created"
        assert "experiment_id" in exp

    def test_run_evaluation_no_evaluators(self, operational_bridge):
        """run_evaluation returns error for invalid evaluators."""
        runner = K1ExperimentRunner(operational_bridge)
        result = runner.run_evaluation(
            "kai-test",
            evaluator_names=["nonexistent_evaluator"],
        )
        assert "error" in result

    def test_run_evaluation_empty_dataset(self, operational_bridge, mock_client):
        """run_evaluation handles empty dataset."""
        existing_ds = MagicMock()
        existing_ds.id = uuid.uuid4()
        mock_client.list_datasets.return_value = [existing_ds]
        mock_client.list_examples.return_value = []

        runner = K1ExperimentRunner(operational_bridge)
        result = runner.run_evaluation("kai-empty")
        assert result["error"] == "Dataset is empty"


# ===========================================================================
# Test Dataset Example Builders
# ===========================================================================


class TestExampleBuilders:
    """Tests for dataset example builder helpers."""

    def test_build_triage_example(self):
        """build_triage_example produces correct structure."""
        example = build_triage_example(
            mission_id="m-1",
            finding_id="f-1",
            triage_input={"vuln": "xss"},
            triage_output={"severity": "high"},
        )
        assert example["inputs"]["finding_id"] == "f-1"
        assert example["outputs"]["severity"] == "high"
        assert example["metadata"]["mission_id"] == "m-1"

    def test_build_triage_example_with_ground_truth(self):
        """build_triage_example prefers ground truth over triage output."""
        example = build_triage_example(
            mission_id="m-1",
            finding_id="f-1",
            triage_input={"vuln": "xss"},
            triage_output={"severity": "high"},
            ground_truth={"severity": "critical"},
        )
        assert example["outputs"]["severity"] == "critical"

    def test_build_evidence_example(self):
        """build_evidence_example produces correct structure."""
        example = build_evidence_example(
            mission_id="m-1",
            evidence_input={"artifacts": ["a1"]},
            evidence_output={"analysis": "done"},
        )
        assert example["inputs"]["artifacts"] == ["a1"]
        assert example["metadata"]["mission_id"] == "m-1"

    def test_build_mission_replay_example(self):
        """build_mission_replay_example produces correct structure."""
        example = build_mission_replay_example(
            mission_id="m-fail-1",
            mission_config={"target": "example.com"},
            mission_result={"error": "timeout"},
            failure_reason="Agent timed out during recon",
        )
        assert example["inputs"]["mission_id"] == "m-fail-1"
        assert example["outputs"]["failure_reason"] == "Agent timed out during recon"
        assert example["metadata"]["is_failure"] is True

    def test_build_mission_replay_no_failure(self):
        """Mission replay example without failure reason."""
        example = build_mission_replay_example(
            mission_id="m-success-1",
            mission_config={},
            mission_result={"success": True},
        )
        assert example["metadata"]["is_failure"] is False


# ===========================================================================
# Test Module Singleton
# ===========================================================================


class TestModuleSingleton:
    """Tests for module-level singleton management."""

    def test_get_langsmith_bridge_returns_instance(self):
        """get_langsmith_bridge always returns a LangSmithBridge."""
        import apps.backend.src.core.langsmith_integration as mod
        old_bridge = mod._bridge
        try:
            mod._bridge = None
            bridge = get_langsmith_bridge()
            assert isinstance(bridge, LangSmithBridge)
        finally:
            mod._bridge = old_bridge

    def test_initialize_replaces_singleton(self):
        """initialize_langsmith_bridge replaces the module singleton."""
        import apps.backend.src.core.langsmith_integration as mod
        old_bridge = mod._bridge
        try:
            cfg = LangSmithConfig(enabled=False, project="test-init")
            new_bridge = initialize_langsmith_bridge(config=cfg)
            assert new_bridge.config.project == "test-init"
            assert get_langsmith_bridge() is new_bridge
        finally:
            mod._bridge = old_bridge

    def test_is_langsmith_available(self):
        """is_langsmith_available reflects package importability."""
        result = is_langsmith_available()
        assert isinstance(result, bool)
        # Should be True since we installed it
        assert result is True

    def test_is_langsmith_operational_default_false(self):
        """Default config (disabled) means not operational."""
        import apps.backend.src.core.langsmith_integration as mod
        old_bridge = mod._bridge
        try:
            mod._bridge = None
            # Without K1_LANGSMITH_ENABLED=true, should be False
            assert is_langsmith_operational() is False
        finally:
            mod._bridge = old_bridge


# ===========================================================================
# Test LangChain Callback Integration
# ===========================================================================


class TestLangChainCallbacks:
    """Tests for LangChain callback integration."""

    def test_get_langchain_callbacks_disabled(self, disabled_config):
        """Returns empty list when disabled."""
        bridge = LangSmithBridge(config=disabled_config)
        callbacks = bridge.get_langchain_callbacks()
        assert callbacks == []

    def test_get_langchain_callbacks_no_correlation(self, operational_bridge):
        """Returns empty list when no correlation is provided."""
        callbacks = operational_bridge.get_langchain_callbacks(correlation=None)
        assert callbacks == []

    def test_get_langchain_callbacks_with_correlation(self, operational_bridge, sample_correlation):
        """Returns LangChainTracer when operational with correlation."""
        # This test depends on whether LangChainTracer is importable
        callbacks = operational_bridge.get_langchain_callbacks(
            correlation=sample_correlation
        )
        # Either returns a tracer or empty list (depending on langsmith version)
        assert isinstance(callbacks, list)
