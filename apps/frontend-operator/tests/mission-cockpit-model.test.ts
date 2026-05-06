import { describe, expect, it } from "vitest";

import type { CampaignDiagnosticsResponse, CampaignStatusResponse } from "@/lib/types";
import { deriveMissionCockpitModel } from "@/lib/utils/cockpit";

function buildCampaign(overrides?: Partial<CampaignStatusResponse>): CampaignStatusResponse {
  return {
    campaign: {
      id: "11111111-1111-4111-8111-111111111111",
      status: "RUNNING",
      program_id: "program-1",
      created_at: "2026-05-06T00:00:00Z",
      updated_at: "2026-05-06T01:00:00Z"
    },
    branches: [],
    phase_jobs: [
      {
        id: "phase-1",
        phase_name: "workflow_recon",
        phase_order: 1,
        status: "COMPLETED",
        depends_on_job_id: null,
        approval_required: false,
        worker_task_id: "worker-1"
      },
      {
        id: "phase-2",
        phase_name: "workflow_web_validation",
        phase_order: 2,
        status: "WAITING_APPROVAL",
        depends_on_job_id: "phase-1",
        approval_required: true,
        worker_task_id: null
      }
    ],
    ...overrides
  };
}

function buildDiagnostics(overrides?: Partial<CampaignDiagnosticsResponse>): CampaignDiagnosticsResponse {
  return {
    campaign: {
      id: "11111111-1111-4111-8111-111111111111",
      status: "RUNNING",
      created_at: "2026-05-06T00:00:00Z",
      updated_at: "2026-05-06T01:00:00Z",
      blocked_reason: null,
      last_error: null
    },
    counts: {
      branches: 1,
      phase_jobs: 2,
      tool_executions: 3,
      approval_gates: 1,
      artifacts: 5,
      observations: 2,
      submission_drafts: 0
    },
    status_breakdown: {
      phase_jobs: {
        COMPLETED: 1,
        WAITING_APPROVAL: 1
      },
      tool_executions: {
        COMPLETED: 1,
        RUNNING: 1,
        FAILED: 1
      },
      approval_gates: {
        PENDING: 1
      }
    },
    phase_links: [],
    recent_audit_events: [
      {
        id: "event-1",
        event_type: "agent.recommendation.generated",
        actor: "agent.recon",
        happened_at: "2026-05-06T01:00:00Z",
        message: "Recommendation emitted",
        payload: {}
      }
    ],
    ...overrides
  };
}

describe("deriveMissionCockpitModel", () => {
  it("derives manual pressure and autonomous risk from diagnostics", () => {
    const model = deriveMissionCockpitModel({
      missionId: "11111111-1111-4111-8111-111111111111",
      campaign: buildCampaign(),
      diagnostics: buildDiagnostics(),
      findingsCount: 3,
      approvalCount: 1
    });

    expect(model.pendingApprovals).toBe(1);
    expect(model.findingsNeedingReview).toBe(3);
    expect(model.failedToolExecutions).toBe(1);
    expect(model.autonomyStatus).toBe("FAILED");
    expect(model.manualStatus).toBe("WAITING_APPROVAL");
    expect(model.actions.some((action) => action.id === "manual:approvals")).toBe(true);
    expect(model.actions.some((action) => action.id === "manual:findings")).toBe(true);
    expect(model.guidanceSteps.length).toBeGreaterThan(0);
    expect(model.aiSignals.length).toBeGreaterThan(0);
  });

  it("returns steady-state action when no immediate blockers exist", () => {
    const campaign = buildCampaign({
      campaign: {
        id: "11111111-1111-4111-8111-111111111111",
        status: "COMPLETED",
        program_id: "program-1",
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T02:00:00Z"
      },
      phase_jobs: [
        {
          id: "phase-1",
          phase_name: "workflow_recon",
          phase_order: 1,
          status: "COMPLETED",
          depends_on_job_id: null,
          approval_required: false,
          worker_task_id: "worker-1"
        }
      ]
    });

    const diagnostics = buildDiagnostics({
      campaign: {
        id: "11111111-1111-4111-8111-111111111111",
        status: "COMPLETED",
        created_at: "2026-05-06T00:00:00Z",
        updated_at: "2026-05-06T02:00:00Z",
        blocked_reason: null,
        last_error: null
      },
      counts: {
        branches: 1,
        phase_jobs: 1,
        tool_executions: 1,
        approval_gates: 0,
        artifacts: 2,
        observations: 1,
        submission_drafts: 0
      },
      status_breakdown: {
        phase_jobs: { COMPLETED: 1 },
        tool_executions: { COMPLETED: 1 },
        approval_gates: {}
      },
      recent_audit_events: []
    });

    const model = deriveMissionCockpitModel({
      missionId: "11111111-1111-4111-8111-111111111111",
      campaign,
      diagnostics,
      findingsCount: 0,
      approvalCount: 0
    });

    expect(model.manualStatus).toBe("COMPLETED");
    expect(model.failedToolExecutions).toBe(0);
    expect(model.actions.some((action) => action.id === "autonomous:steady")).toBe(true);
    expect(model.guidanceSteps[0]?.id).toBe("default:monitor");
  });
});
