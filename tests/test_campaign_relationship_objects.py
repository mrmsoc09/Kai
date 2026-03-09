from __future__ import annotations

from uuid import uuid4

from apps.backend.src.models.campaign import (
    ApprovalGate,
    CampaignRun,
    ExecutionBranch,
    PhaseJob,
    Program,
    ScopeTarget,
    ToolExecution,
)
from apps.backend.src.models.enums import (
    ApprovalGateStatusEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    IntentionSourceEnum,
    IntentionTypeEnum,
    PhaseJobStatusEnum,
    ToolExecutionStatusEnum,
)
from apps.backend.src.models.intention import IntentionRecord


def test_campaign_branch_phase_job_linkage_objects():
    program = Program(name="Example Program")
    scope_target = ScopeTarget(program=program, target="example.com", target_type="domain")
    campaign = CampaignRun(
        program=program,
        primary_scope_target=scope_target,
        initiated_by="operator@example.com",
        declared_goal="Run recon and vulnerability signal collection",
        status=CampaignStatusEnum.CREATED,
    )
    branch = ExecutionBranch(campaign=campaign, branch_key="root", status=BranchStatusEnum.PENDING)
    phase_job = PhaseJob(
        campaign=campaign,
        branch=branch,
        phase_name="recon",
        status=PhaseJobStatusEnum.CREATED,
    )

    assert branch.campaign is campaign
    assert phase_job.campaign is campaign
    assert phase_job.branch is branch


def test_approval_gate_and_tool_execution_linkage_objects():
    campaign = CampaignRun(
        program=Program(name="Program"),
        initiated_by="operator@example.com",
        declared_goal="Execute branch",
        status=CampaignStatusEnum.CREATED,
    )
    branch = ExecutionBranch(campaign=campaign, branch_key="root", status=BranchStatusEnum.PENDING)
    phase_job = PhaseJob(campaign=campaign, branch=branch, phase_name="scan", status=PhaseJobStatusEnum.CREATED)
    gate = ApprovalGate(
        campaign=campaign,
        branch=branch,
        phase_job=phase_job,
        gate_reason="Potential risk posture increase",
        requested_by="agent/k1",
        status=ApprovalGateStatusEnum.PENDING,
    )
    tool_execution = ToolExecution(
        campaign=campaign,
        branch=branch,
        phase_job=phase_job,
        approval_gate=gate,
        tool_name="nuclei",
        status=ToolExecutionStatusEnum.CREATED,
    )

    assert tool_execution.approval_gate is gate
    assert gate.tool_executions[0] is tool_execution


def test_intention_record_links_to_campaign_branch_phase():
    campaign = CampaignRun(
        program=Program(name="Program"),
        initiated_by="operator@example.com",
        declared_goal="Run campaign",
        status=CampaignStatusEnum.CREATED,
    )
    branch = ExecutionBranch(campaign=campaign, branch_key="root", status=BranchStatusEnum.PENDING)
    phase_job = PhaseJob(
        campaign=campaign,
        branch=branch,
        phase_name="validation",
        status=PhaseJobStatusEnum.CREATED,
    )
    intention = IntentionRecord(
        id=uuid4(),
        campaign_run=campaign,
        branch=branch,
        phase_job=phase_job,
        source=IntentionSourceEnum.AGENT,
        intention_type=IntentionTypeEnum.PHASE_EXECUTION,
        initiated_by="agent/k1",
        declared_goal="Validate signal and produce normalized observation",
    )
    tool_execution = ToolExecution(
        campaign=campaign,
        branch=branch,
        phase_job=phase_job,
        tool_name="custom-validator",
        status=ToolExecutionStatusEnum.CREATED,
        intention_id=intention.id,
    )

    assert intention.campaign_run is campaign
    assert intention.branch is branch
    assert intention.phase_job is phase_job
    assert tool_execution.intention_id == intention.id
