from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import apps.backend.src.routers.campaigns as campaigns_router
from apps.backend.src.core.hil_db import get_db
from apps.backend.src.main import app
from apps.backend.src.models.campaign import ToolExecution
from apps.backend.src.models.enums import (
    CorrelationActionEnum,
    StageRunStatusEnum,
    ToolExecutionStatusEnum,
    WorkflowRunStatusEnum,
)
from apps.backend.src.models.workflow import CorrelationRecord, StageRun, WorkflowFinding, WorkflowRun


def test_workflow_run_retrieval_endpoints(client, monkeypatch):
    now = datetime.now(timezone.utc)
    workflow_run_id = uuid4()
    campaign_id = uuid4()
    stage_run_id = uuid4()
    tool_execution_id = uuid4()

    workflow_run = WorkflowRun(
        id=workflow_run_id,
        campaign_run_id=campaign_id,
        template_name="workflow_quick_vuln_sweep",
        target="example.com",
        safe_mode=True,
        dry_run=False,
        trigger_source="API",
        total_phases=4,
        completed_phases=2,
        status=WorkflowRunStatusEnum.RUNNING,
        artifact_manifest_path="output/workflows/wf-x/manifest.json",
        summary_artifact_path="output/workflows/wf-x/summary.json",
        created_at=now,
        updated_at=now,
    )
    stage_run = StageRun(
        id=stage_run_id,
        workflow_run_id=workflow_run_id,
        campaign_run_id=campaign_id,
        stage_name="vuln_scan",
        stage_order=1,
        phase_count=2,
        completed_count=1,
        status=StageRunStatusEnum.RUNNING,
        created_at=now,
        updated_at=now,
    )
    tool_execution = ToolExecution(
        id=tool_execution_id,
        campaign_id=campaign_id,
        stage_run_id=stage_run_id,
        tool_name="nuclei",
        status=ToolExecutionStatusEnum.COMPLETED,
        input_target="example.com",
        input_payload_json={},
        artifact_path="output/raw/wf-x/vuln_scan/nuclei.json",
        retry_count=0,
        max_retries=0,
        created_at=now,
        updated_at=now,
    )
    workflow_finding = WorkflowFinding(
        id=uuid4(),
        workflow_run_id=workflow_run_id,
        campaign_id=campaign_id,
        stage_run_id=stage_run_id,
        tool_execution_id=tool_execution_id,
        asset_identifier="api.example.com",
        vulnerability_type="sql_injection_candidate",
        details_json={},
        created_at=now,
        updated_at=now,
    )
    correlation = CorrelationRecord(
        id=uuid4(),
        workflow_run_id=workflow_run_id,
        campaign_id=campaign_id,
        correlation_rule="workflow_signal_graph",
        asset_identifier="api.example.com",
        signal_sources_json=["https://api.example.com/v1/users", "port:443"],
        confidence=0.71,
        action=CorrelationActionEnum.CREATED,
        correlated_at=now,
        created_at=now,
        updated_at=now,
    )

    class _FakeWorkflowRunService:
        def __init__(self, _db):
            pass

        async def list_workflow_runs(self, **_kwargs):
            return [workflow_run]

        async def get_workflow_run(self, requested_id):
            return workflow_run if requested_id == workflow_run_id else None

        async def list_stage_runs(self, _workflow_run_id):
            return [stage_run]

        async def list_tool_executions(self, _workflow_run_id):
            return [tool_execution]

        async def list_workflow_findings(self, _workflow_run_id):
            return [workflow_finding]

        async def list_correlation_records(self, _workflow_run_id):
            return [correlation]

    async def _override_db():
        yield object()

    monkeypatch.setattr(campaigns_router, "WorkflowRunService", _FakeWorkflowRunService)
    app.dependency_overrides[get_db] = _override_db
    try:
        runs_response = client.get("/api/v1/campaigns/workflows/runs")
        assert runs_response.status_code == 200
        runs_payload = runs_response.json()
        assert len(runs_payload) == 1
        assert runs_payload[0]["id"] == str(workflow_run_id)

        stages_response = client.get(
            f"/api/v1/campaigns/workflows/runs/{workflow_run_id}/stages"
        )
        assert stages_response.status_code == 200
        assert stages_response.json()[0]["stage_name"] == "vuln_scan"

        tools_response = client.get(
            f"/api/v1/campaigns/workflows/runs/{workflow_run_id}/tool-executions"
        )
        assert tools_response.status_code == 200
        assert tools_response.json()[0]["tool_name"] == "nuclei"

        findings_response = client.get(
            f"/api/v1/campaigns/workflows/runs/{workflow_run_id}/findings"
        )
        assert findings_response.status_code == 200
        assert findings_response.json()[0]["asset_identifier"] == "api.example.com"

        correlations_response = client.get(
            f"/api/v1/campaigns/workflows/runs/{workflow_run_id}/correlations"
        )
        assert correlations_response.status_code == 200
        assert correlations_response.json()[0]["asset_identifier"] == "api.example.com"
    finally:
        app.dependency_overrides.pop(get_db, None)
