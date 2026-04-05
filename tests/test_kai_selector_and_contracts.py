from __future__ import annotations

from typing import Any

from apps.backend.src.core.kai_execution_selector import (
    ExecutionSubstrate,
    select_execution_substrate,
    selector_artifact_for_stage,
)
from apps.backend.src.core.kai_persona_contracts import validate_persona_contract
from apps.backend.src.core.praison_adapter_contract import BasicPraisonAdapterContract


def test_selector_chooses_custom_for_stateless_low_latency_read_only() -> None:
    decision = select_execution_substrate({
        "is_stateless": True,
        "latency_slo_ms": 200,
        "workflow_complexity": "low",
        "tool_privilege_level": "read",
        "needs_resume": False,
    })
    assert decision["selected_substrate"] == ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value
    assert decision["denied"] is False


def test_selector_denies_unsafe_multi_tenant_backend() -> None:
    decision = select_execution_substrate({
        "tenant_mode": "multi",
        "requested_backend": "host_shell",
    })
    assert decision["selected_substrate"] == ExecutionSubstrate.DENY.value
    assert decision["denied"] is True


def test_selector_applies_performance_reliability_override() -> None:
    decision = select_execution_substrate({
        "requires_specialist_decomposition": True,
        "risk_band": 1,
        "performance_profile": {
            "DEEPAGENTS_SPECIALIST": {
                "failure_rate": 0.35,
                "retry_frequency": 0.25,
                "p95_latency_ms": 900,
            }
        },
    })
    assert decision["selected_substrate"] == ExecutionSubstrate.LANGGRAPH_PRIMARY.value
    assert "selector:perf_reliability_override" in decision["audit_tags"]


def test_selector_artifact_contains_stage_metadata() -> None:
    artifact = selector_artifact_for_stage(
        stage_id="recon",
        node_id="SurfaceMapper",
        selector_inputs={"workflow_complexity": "high"},
    )
    assert artifact["type"] == "execution_selector_policy"
    assert artifact["stage_id"] == "recon"
    assert artifact["node_id"] == "SurfaceMapper"


def test_persona_contract_validation_blocks_schema_errors() -> None:
    validation = validate_persona_contract({"class": "governor"})
    assert validation["blocked"] is True
    assert validation["errors"]


def test_persona_contract_validation_blocks_critical_translation_loss() -> None:
    payload = {
        "persona_id": "gov-1",
        "name": "Governor",
        "class": "governor",
        "objective": "Govern safely",
        "instructions": "Always gate risk",
        "capabilities": {"tools_allowed": [], "tools_denied": ["nmap"], "protocols_allowed": ["mcp"]},
        "policy": {"risk_profile": "governance", "approval_policy": "never", "autonomy_mode": "suggest"},
        "memory": {"scope": "persistent", "persistence": True, "quality_threshold": 0.9},
        "delegation": {"allowed": True, "delegation_scope": "global"},
        "handoff": {"accepts_from": [], "can_handoff_to": []},
        "observability": {"trace_tags": ["gov"], "emit_metrics": False},
        "compatibility": {"framework_targets": ["kai", "crewai", "langstudio"]},
    }
    validation = validate_persona_contract(payload, tenant_mode="multi")
    assert validation["blocked"] is True
    warning_codes = {row["code"] for row in validation["translation_loss_warnings"]}
    assert "LOSS_APPROVAL_SEMANTICS" in warning_codes


class _FakePraisonBackend:
    def __init__(self) -> None:
        self.submitted_payloads: list[dict[str, Any]] = []

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.submitted_payloads.append(payload)
        return {"job_id": "job-123"}

    def status(self, job_id: str) -> dict[str, Any]:
        return {"status": "completed", "progress": 1.0}

    def result(self, job_id: str) -> dict[str, Any]:
        return {"status": "completed", "result": {"ok": True}}


def test_praison_adapter_contract_reconcile_terminal_result() -> None:
    backend = _FakePraisonBackend()
    adapter = BasicPraisonAdapterContract(backend)
    ticket = adapter.submit(
        mission_id="m1",
        workflow_id="wf1",
        program_id="p1",
        payload={"task": "scan"},
        idempotency_key="m1:wf1:p1",
    )
    reconciliation = adapter.reconcile(ticket)
    assert reconciliation["terminal"] is True
    assert reconciliation["status"] == "completed"
    assert reconciliation["result"] == {"ok": True}
