import React from "react";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApprovalsPage from "@/app/approvals/page";
import CampaignsPage from "@/app/campaigns/page";
import FindingDetailPage from "@/app/findings/[findingId]/page";
import { renderWithQueryClient } from "@/tests/test-utils";

const {
  campaignApiMock,
  findingsApiMock,
  exportsApiMock,
  hooksMock
} = vi.hoisted(() => ({
  campaignApiMock: {
    startCampaign: vi.fn(),
    scheduleCampaign: vi.fn(),
    correlateCampaign: vi.fn(),
    decideApprovalGate: vi.fn()
  },
  findingsApiMock: {
    reviewFinding: vi.fn(),
    prepareSubmission: vi.fn()
  },
  exportsApiMock: {
    previewExport: vi.fn(),
    stageExport: vi.fn()
  },
  hooksMock: {
    useCampaigns: vi.fn(),
    useDiagnosticsSummary: vi.fn(),
    useFinding: vi.fn(),
    useApprovalQueue: vi.fn()
  }
}));

vi.mock("@/lib/api/campaigns", () => campaignApiMock);
vi.mock("@/lib/api/findings", () => findingsApiMock);
vi.mock("@/lib/api/exports", () => exportsApiMock);
vi.mock("@/hooks/useCampaigns", () => ({ useCampaigns: hooksMock.useCampaigns }));
vi.mock("@/hooks/useDiagnosticsSummary", () => ({
  useDiagnosticsSummary: hooksMock.useDiagnosticsSummary
}));
vi.mock("@/hooks/useFinding", () => ({ useFinding: hooksMock.useFinding }));
vi.mock("@/hooks/useApprovalQueue", () => ({ useApprovalQueue: hooksMock.useApprovalQueue }));

describe("operator console pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.__NEXT_PARAMS__ = {};
    localStorage.clear();

    hooksMock.useCampaigns.mockReturnValue([]);
    hooksMock.useDiagnosticsSummary.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        generated_at: "2026-03-11T00:00:00Z",
        campaigns: { total: 0, by_status: {} },
        branches: { total: 0, by_status: {} },
        phase_jobs: { total: 0, by_status: {} },
        approval_gates: { total: 0, by_status: {} },
        tool_executions: { total: 0, by_status: {} },
        findings: { total: 0, by_status: {} },
        submission_drafts: { total: 0, by_status: {} }
      }
    });
    hooksMock.useFinding.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        finding: {
          id: "44444444-4444-4444-8444-444444444444",
          program: "Example Program",
          asset: "api.example.com",
          title: "SQL Injection signal",
          status: "IN_REVIEW",
          severity: "HIGH",
          scope_json: {}
        },
        counts: {
          evidence: 1,
          observations: 1,
          artifacts: 1,
          submission_drafts: 1,
          audit_events: 1
        },
        submission_drafts: [
          {
            id: "55555555-5555-4555-8555-555555555555",
            campaign_id: "11111111-1111-4111-8111-111111111111",
            branch_id: null,
            status: "NEEDS_REVIEW",
            prepared_by: "system",
            approved_by: null,
            approved_at: null
          }
        ],
        recent_observations: [],
        recent_audit_events: []
      }
    });
    hooksMock.useApprovalQueue.mockReturnValue({
      diagnosticsQueries: [],
      approvalGates: [
        {
          gate_id: "33333333-3333-4333-8333-333333333333",
          campaign_id: "11111111-1111-4111-8111-111111111111",
          phase_job_id: "22222222-2222-4222-8222-222222222222",
          phase_name: "workflow_recon",
          status: "PENDING",
          source_event_type: "approval_gate.created",
          happened_at: "2026-03-11T00:10:00Z",
          requested_at: "2026-03-11T00:09:00Z",
          decided_at: null,
          request_title: "Recon escalation approval",
          requested_action: "Run elevated recon step",
          requesting_agent: "recon_agent",
          scope_target: "api.example.com",
          risk_band: "HIGH",
          evidence_attached: "2 linked item(s)",
          intention: "Verify exploitable recon path before progression.",
          justification: "Policy requires operator review for elevated recon.",
          expected_impact: "Improves mission confidence for next phase decisions.",
          safety_constraints: "Scope-restricted and non-destructive only.",
          reviewer_notes: "",
          message: "Approval required"
        }
      ]
    });

    campaignApiMock.startCampaign.mockResolvedValue({
      campaign_id: "11111111-1111-4111-8111-111111111111",
      program_id: "00000000-0000-4000-8000-000000000000",
      branch_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      campaign_status: "READY",
      branch_status: "READY",
      scheduler: {
        campaign_id: "11111111-1111-4111-8111-111111111111",
        considered_jobs: 0,
        queued_jobs: 0,
        blocked_jobs: 0,
        waiting_approval_jobs: 0,
        created_approval_gates: 0,
        dispatched_tool_executions: 0
      },
      idempotent_replay: false,
      phase_jobs: []
    });
    campaignApiMock.scheduleCampaign.mockResolvedValue({});
    campaignApiMock.decideApprovalGate.mockResolvedValue({
      gate_id: "33333333-3333-4333-8333-333333333333",
      campaign_id: "11111111-1111-4111-8111-111111111111",
      status: "APPROVED",
      decided_by: "operator.console.approvals",
      decided_at: "2026-03-11T00:11:00Z",
      scheduler: null
    });
    findingsApiMock.reviewFinding.mockResolvedValue({
      finding_id: "44444444-4444-4444-8444-444444444444",
      finding_status: "HIL_APPROVED",
      submission_draft_id: "55555555-5555-4555-8555-555555555555",
      submission_draft_status: "READY_FOR_SUBMISSION",
      campaign_id: "11111111-1111-4111-8111-111111111111",
      review_timestamp: "2026-03-11T01:00:00Z"
    });
    findingsApiMock.prepareSubmission.mockResolvedValue({
      finding_id: "44444444-4444-4444-8444-444444444444",
      submission_draft_id: "55555555-5555-4555-8555-555555555555",
      submission_draft_status: "READY_FOR_REVIEW",
      package_json: { title: "x" }
    });
    exportsApiMock.previewExport.mockResolvedValue({
      provider: "hackerone",
      finding_id: "44444444-4444-4444-8444-444444444444",
      submission_draft_id: "55555555-5555-4555-8555-555555555555",
      ready: true,
      state: "ready",
      missing_fields: [],
      warnings: [],
      payload: { title: "Draft title" },
      stored: false,
      exported_at: null
    });
    exportsApiMock.stageExport.mockResolvedValue({
      provider: "hackerone",
      finding_id: "44444444-4444-4444-8444-444444444444",
      submission_draft_id: "55555555-5555-4555-8555-555555555555",
      ready: true,
      state: "ready",
      missing_fields: [],
      warnings: [],
      payload: { title: "Draft title" },
      stored: true,
      exported_at: "2026-03-11T01:05:00Z"
    });
  });

  it("renders campaign dashboard route", () => {
    renderWithQueryClient(<CampaignsPage />);
    expect(screen.getByText("Missions")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Start Campaign" })).toBeInTheDocument();
  });

  it("wires finding review action and export preview", async () => {
    globalThis.__NEXT_PARAMS__ = { findingId: "44444444-4444-4444-8444-444444444444" };
    renderWithQueryClient(<FindingDetailPage />);

    fireEvent.click(screen.getByText("Apply Review Action"));
    await waitFor(() => {
      expect(findingsApiMock.reviewFinding).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByText("Preview Export Payload"));
    await waitFor(() => {
      expect(exportsApiMock.previewExport).toHaveBeenCalled();
      expect(screen.getByText("Preview Result")).toBeInTheDocument();
    });
  });

  it("wires approval actions from inferred queue", async () => {
    localStorage.setItem(
      "k1.operator.tracked_campaign_ids",
      JSON.stringify(["11111111-1111-4111-8111-111111111111"])
    );
    renderWithQueryClient(<ApprovalsPage />);
    fireEvent.click(screen.getByText("Approve"));
    await waitFor(() => {
      expect(campaignApiMock.decideApprovalGate).toHaveBeenCalledWith(
        "33333333-3333-4333-8333-333333333333",
        expect.objectContaining({ status: "APPROVED" })
      );
    });
  });
});
