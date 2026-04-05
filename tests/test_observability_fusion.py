from __future__ import annotations

from unittest.mock import MagicMock

from apps.backend.src.core.langsmith_integration import (
    LangSmithBridge,
    LangSmithConfig,
    TraceCorrelation,
)
from apps.backend.src.core.langsmith_redaction import redact_for_langsmith


def _operational_bridge(monkeypatch) -> tuple[LangSmithBridge, MagicMock]:
    import apps.backend.src.core.langsmith_integration as lsi

    monkeypatch.setattr(lsi, "_LANGSMITH_AVAILABLE", True)
    cfg = LangSmithConfig(enabled=True, api_key="test-key", project="kai-test", sample_rate=1.0)
    bridge = LangSmithBridge(config=cfg)
    client = MagicMock()
    client.create_run = MagicMock()
    client.update_run = MagicMock()
    bridge._client = client
    bridge._initialized = True
    return bridge, client


def test_correlation_metadata_and_audit_primacy(monkeypatch) -> None:
    bridge, client = _operational_bridge(monkeypatch)
    corr = TraceCorrelation(
        mission_id="m-1",
        workflow_id="wf-1",
        program_id="prog-1",
        phase="recon",
        stage_id="recon_stage",
        node_id="node-a",
        agent_id="agent-a",
        selected_substrate="LANGGRAPH_PRIMARY",
        risk_band="1",
        tool_execution_id="te-1",
        tenant_id="tenant-1",
    )

    run_id = bridge.create_run("fusion-test", correlation=corr, inputs={"task": "test"})
    assert run_id is not None
    kwargs = client.create_run.call_args.kwargs
    metadata = kwargs["extra"]["metadata"]
    assert metadata["kai_audit_primary"] == "true"
    assert metadata["telemetry_plane"] == "secondary"
    assert metadata["kai_stage_id"] == "recon_stage"
    assert metadata["kai_selected_substrate"] == "LANGGRAPH_PRIMARY"
    assert metadata["kai_tool_execution_id"] == "te-1"


def test_redaction_enforces_governance_field_protection() -> None:
    payload = {
        "governance_decision": "approved",
        "approval_id": "ap-7",
        "contract_id": "ct-9",
        "scope_decision_id": "sd-2",
        "normal_field": "ok",
    }
    redacted = redact_for_langsmith(payload, mode="strict")
    assert redacted["governance_decision"] == "[REDACTED:GOVERNANCE]"
    assert redacted["approval_id"] == "[REDACTED:GOVERNANCE]"
    assert redacted["contract_id"] == "[REDACTED:GOVERNANCE]"
    assert redacted["scope_decision_id"] == "[REDACTED:GOVERNANCE]"
    assert redacted["normal_field"] == "ok"


def test_degradation_path_preserves_kai_execution(monkeypatch) -> None:
    bridge, client = _operational_bridge(monkeypatch)
    client.create_run.side_effect = RuntimeError("langsmith unavailable")

    # Must not raise; export failure is degraded internally.
    result = bridge.create_run("degrade-test", inputs={"task": "safe"})
    assert result is None
    assert bridge.degraded_export_failures >= 1


def test_subscriber_bridges_tool_correlation(monkeypatch) -> None:
    bridge, client = _operational_bridge(monkeypatch)
    subscriber = bridge.create_event_subscriber()

    mission_started = MagicMock()
    mission_started.event_type = "mission_started"
    mission_started.mission_id = "m-tool"
    mission_started.workflow_id = "wf-tool"
    mission_started.program_id = "prog-tool"
    mission_started.node_id = ""
    mission_started.agent_id = ""
    mission_started.detail = {"execution_mode": "live"}
    subscriber(mission_started)

    tool_started = MagicMock()
    tool_started.event_type = "tool_invocation_started"
    tool_started.mission_id = "m-tool"
    tool_started.workflow_id = "wf-tool"
    tool_started.program_id = "prog-tool"
    tool_started.node_id = "node-recon"
    tool_started.agent_id = "agent-recon"
    tool_started.detail = {
        "tool_id": "subfinder",
        "tool_execution_id": "tool-exec-42",
        "stage_id": "recon",
        "selected_substrate": "LANGGRAPH_PRIMARY",
        "risk_band": "1",
    }
    subscriber(tool_started)

    kwargs = client.create_run.call_args.kwargs
    metadata = kwargs["extra"]["metadata"]
    assert metadata["kai_stage_id"] == "recon"
    assert metadata["kai_selected_substrate"] == "LANGGRAPH_PRIMARY"
    assert metadata["kai_tool_execution_id"] == "tool-exec-42"
    assert metadata["kai_audit_primary"] == "true"


def test_evaluation_hook_foundation_is_observational(monkeypatch) -> None:
    bridge, _client = _operational_bridge(monkeypatch)
    captured: list[dict] = []
    bridge.register_evaluation_hook("capture", lambda payload: captured.append(payload))
    subscriber = bridge.create_event_subscriber()

    event = MagicMock()
    event.event_type = "mission_completed"
    event.mission_id = "m-eval"
    event.workflow_id = "wf-eval"
    event.program_id = "prog-eval"
    event.phase = "report"
    event.node_id = "node-report"
    event.agent_id = "agent-report"
    event.detail = {"success": True, "final_report_id": "r-1"}
    subscriber(event)

    assert captured
    assert captured[0]["audit_source_of_truth"] == "kai"
    assert captured[0]["observability_plane"] == "langsmith_secondary"
