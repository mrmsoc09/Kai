import React from "react";
import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AlertsPage from "@/app/alerts/page";
import CaseDetailPage from "@/app/cases/[caseId]/page";
import CasesPage from "@/app/cases/page";
import { renderWithQueryClient } from "@/tests/test-utils";

const mocks = vi.hoisted(() => ({
  useAlertCenter: vi.fn(),
  useCaseQueue: vi.fn(),
  useCaseDetail: vi.fn(),
  useParams: vi.fn()
}));

vi.mock("@/hooks/useAlertCenter", () => ({ useAlertCenter: mocks.useAlertCenter }));
vi.mock("@/hooks/useCaseQueue", () => ({ useCaseQueue: mocks.useCaseQueue }));
vi.mock("@/hooks/useCaseDetail", () => ({ useCaseDetail: mocks.useCaseDetail }));
vi.mock("next/navigation", async () => {
  const actual = await vi.importActual<typeof import("next/navigation")>("next/navigation");
  return {
    ...actual,
    useParams: () => mocks.useParams()
  };
});

describe("phase 9 alert and case pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useParams.mockReturnValue({ caseId: "case-1" });
    mocks.useAlertCenter.mockReturnValue({
      rows: [],
      alertsQuery: { isLoading: false, isError: false, data: [] },
      summaryQuery: { isLoading: false, isError: false, data: null },
      syncMutation: { mutate: vi.fn(), isPending: false, isError: false },
      acknowledgeMutation: { mutate: vi.fn(), isPending: false, isError: false },
      resolveMutation: { mutate: vi.fn(), isPending: false, isError: false },
      createCaseMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });
    mocks.useCaseQueue.mockReturnValue({
      casesQuery: { isLoading: false, isError: false, data: [] },
      updateCaseMutation: { mutate: vi.fn(), isPending: false, isError: false },
      assignCaseMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });
    mocks.useCaseDetail.mockReturnValue({
      caseQuery: { isLoading: false, isError: false, data: null },
      updateCaseMutation: { mutate: vi.fn(), isPending: false, isError: false },
      assignMutation: { mutate: vi.fn(), isPending: false, isError: false },
      addNoteMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });
  });

  it("renders alert and case route headers", () => {
    renderWithQueryClient(<AlertsPage />);
    renderWithQueryClient(<CasesPage />);
    renderWithQueryClient(<CaseDetailPage />);
    expect(screen.getByText("Alerting and Notifications")).toBeInTheDocument();
    expect(screen.getByText("Analyst Cases")).toBeInTheDocument();
    expect(screen.getByText("Case Detail")).toBeInTheDocument();
  });

  it("wires alert sync action", () => {
    const syncMutate = vi.fn();
    mocks.useAlertCenter.mockReturnValue({
      rows: [],
      alertsQuery: { isLoading: false, isError: false, data: [] },
      summaryQuery: { isLoading: false, isError: false, data: null },
      syncMutation: { mutate: syncMutate, isPending: false, isError: false },
      acknowledgeMutation: { mutate: vi.fn(), isPending: false, isError: false },
      resolveMutation: { mutate: vi.fn(), isPending: false, isError: false },
      createCaseMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });

    renderWithQueryClient(<AlertsPage />);
    fireEvent.click(screen.getByText("Sync Alerts"));
    expect(syncMutate).toHaveBeenCalled();
  });

  it("shows alert program UUID validation and search filtering", () => {
    mocks.useAlertCenter.mockReturnValue({
      rows: [
        {
          id: "alert-1",
          alert_type: "HIGH_PRIORITY_OPPORTUNITY",
          severity: "HIGH",
          urgency: "HIGH",
          status: "OPEN",
          summary: "critical api exposure",
          reasoning_summary: "high-confidence signal",
          analyst_queue_item_id: null,
          prediction_record_id: null,
          recommendation_record_id: null,
          occurrence_count: 1,
          last_seen_at: "2026-03-14T00:00:00Z"
        },
        {
          id: "alert-2",
          alert_type: "READINESS_FAILURE",
          severity: "LOW",
          urgency: "LOW",
          status: "OPEN",
          summary: "scheduler cooldown block",
          reasoning_summary: null,
          analyst_queue_item_id: null,
          prediction_record_id: null,
          recommendation_record_id: null,
          occurrence_count: 1,
          last_seen_at: "2026-03-14T00:00:00Z"
        }
      ],
      alertsQuery: { isLoading: false, isError: false, data: [{}, {}] },
      summaryQuery: {
        isLoading: false,
        isError: false,
        data: {
          unresolved_alert_count: 2,
          high_severity_alert_count: 1,
          open_case_count: 0,
          ready_for_report_case_count: 0,
          stale_unowned_case_count: 0
        }
      },
      syncMutation: { mutate: vi.fn(), isPending: false, isError: false },
      acknowledgeMutation: { mutate: vi.fn(), isPending: false, isError: false },
      resolveMutation: { mutate: vi.fn(), isPending: false, isError: false },
      createCaseMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });

    renderWithQueryClient(<AlertsPage />);
    fireEvent.change(screen.getByPlaceholderText("program UUID (optional)"), {
      target: { value: "not-a-uuid" }
    });
    fireEvent.click(screen.getByText("Apply Program Filter"));
    expect(screen.getByText("Program filter must be a valid UUID.")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("search alert type, summary, linked IDs"), {
      target: { value: "critical api" }
    });
    expect(screen.getByText("critical api exposure")).toBeInTheDocument();
    expect(screen.queryByText("scheduler cooldown block")).not.toBeInTheDocument();
  });

  it("renders case actions and detail controls", () => {
    const updateMutate = vi.fn();
    const assignMutate = vi.fn();
    const noteMutate = vi.fn();
    mocks.useCaseQueue.mockReturnValue({
      casesQuery: {
        isLoading: false,
        isError: false,
        data: [
          {
            id: "case-1",
            title: "Case title",
            summary: "Case summary",
            priority: "HIGH",
            status: "new",
            owner: null,
            last_transition_at: "2026-03-14T00:00:00Z"
          }
        ]
      },
      updateCaseMutation: { mutate: updateMutate, isPending: false, isError: false },
      assignCaseMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });
    mocks.useCaseDetail.mockReturnValue({
      caseQuery: {
        isLoading: false,
        isError: false,
        data: {
          id: "case-1",
          program_id: "program-1",
          scope_target_id: null,
          workflow_run_id: null,
          alert_id: null,
          analyst_queue_item_id: null,
          prediction_record_id: null,
          recommendation_record_id: null,
          submission_draft_id: null,
          title: "Case title",
          summary: "Case summary",
          reasoning_summary: null,
          priority: "HIGH",
          status: "new",
          owner: null,
          last_actor: null,
          assigned_at: null,
          last_transition_at: null,
          closed_at: null,
          closure_reason: null,
          evidence_refs_json: [],
          triage_notes_json: [],
          details_json: {},
          created_at: "2026-03-14T00:00:00Z",
          updated_at: "2026-03-14T00:00:00Z"
        }
      },
      updateCaseMutation: { mutate: updateMutate, isPending: false, isError: false },
      assignMutation: { mutate: assignMutate, isPending: false, isError: false },
      addNoteMutation: { mutate: noteMutate, isPending: false, isError: false }
    });

    renderWithQueryClient(<CasesPage />);
    fireEvent.click(screen.getByText("Ack"));
    expect(updateMutate).toHaveBeenCalled();

    renderWithQueryClient(<CaseDetailPage />);
    fireEvent.change(screen.getByPlaceholderText("assign owner identity"), {
      target: { value: "analyst-7" }
    });
    fireEvent.click(screen.getByText("Assign"));
    expect(assignMutate).toHaveBeenCalledWith("analyst-7");
  });

  it("renders explicit case detail empty state when no case record is returned", () => {
    renderWithQueryClient(<CaseDetailPage />);
    expect(screen.getByText("Case not found")).toBeInTheDocument();
  });
});
