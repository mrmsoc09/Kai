import React from "react";
import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentsPage from "@/app/agents/page";
import BriefingPage from "@/app/briefing/page";
import OpportunitiesPage from "@/app/opportunities/page";
import PredictionsPage from "@/app/predictions/page";
import ProgramsPage from "@/app/programs/page";
import RetrospectivePage from "@/app/retrospective/page";
import TargetsPage from "@/app/targets/page";
import TriagePage from "@/app/triage/page";
import { renderWithQueryClient } from "@/tests/test-utils";

const mocks = vi.hoisted(() => ({
  useBountyPrograms: vi.fn(),
  useMonitoredTargets: vi.fn(),
  useOpportunityRankings: vi.fn(),
  usePredictionSignals: vi.fn(),
  useAgentFramework: vi.fn(),
  useRetrospective: vi.fn(),
  useAnalystBriefing: vi.fn(),
  useCandidateQueue: vi.fn()
}));

vi.mock("@/hooks/useBountyPrograms", () => ({ useBountyPrograms: mocks.useBountyPrograms }));
vi.mock("@/hooks/useMonitoredTargets", () => ({ useMonitoredTargets: mocks.useMonitoredTargets }));
vi.mock("@/hooks/useOpportunityRankings", () => ({ useOpportunityRankings: mocks.useOpportunityRankings }));
vi.mock("@/hooks/usePredictionSignals", () => ({ usePredictionSignals: mocks.usePredictionSignals }));
vi.mock("@/hooks/useAgentFramework", () => ({ useAgentFramework: mocks.useAgentFramework }));
vi.mock("@/hooks/useRetrospective", () => ({ useRetrospective: mocks.useRetrospective }));
vi.mock("@/hooks/useAnalystBriefing", () => ({ useAnalystBriefing: mocks.useAnalystBriefing }));
vi.mock("@/hooks/useCandidateQueue", () => ({ useCandidateQueue: mocks.useCandidateQueue }));

describe("phase 8 analyst cockpit pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mocks.useBountyPrograms.mockReturnValue({
      rows: [],
      isLoading: false,
      errors: []
    });
    mocks.useMonitoredTargets.mockReturnValue({
      rows: [],
      isLoading: false,
      errors: []
    });
    mocks.useOpportunityRankings.mockReturnValue({
      rows: [],
      rankingsQuery: { isLoading: false, isError: false, data: [] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      predictionsQuery: { isLoading: false, isError: false, data: [] }
    });
    mocks.usePredictionSignals.mockReturnValue({
      predictionsQuery: { isLoading: false, isError: false, data: [] },
      signalsQuery: { data: [] },
      deltasQuery: { data: [] },
      recommendationsQuery: { data: [] },
      analystSupportQuery: { isLoading: false, isError: false, data: null },
      runMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });
    mocks.useRetrospective.mockReturnValue({
      summaryQuery: { isLoading: false, isError: false, data: null },
      workflowsQuery: { isLoading: false, isError: false, data: [] },
      targetsQuery: { isLoading: false, isError: false, data: [] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      alertsQuery: { isLoading: false, isError: false, data: [] },
      runMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });
    mocks.useAgentFramework.mockReturnValue({
      agentsQuery: { isLoading: false, isError: false, data: [] },
      executionsQuery: { isLoading: false, isError: false, data: [] },
      evaluationsQuery: { isLoading: false, isError: false, data: [] },
      syncMutation: { mutate: vi.fn(), isPending: false, isError: false },
      runMutation: { mutate: vi.fn(), isPending: false, isError: false },
      evaluateMutation: { mutate: vi.fn(), isPending: false, isError: false },
      summary: {
        agents: 0,
        executions: 0,
        succeeded: 0,
        escalated: 0,
        failed: 0,
        passingEvaluations: 0,
        averageSuccessRate: 0
      }
    });
    mocks.useAnalystBriefing.mockReturnValue({
      briefingQuery: { isLoading: false, isError: false, data: null },
      analystSupportQuery: { isLoading: false, isError: false, data: null },
      queueQuery: { isLoading: false, isError: false, data: [] }
    });
    mocks.useCandidateQueue.mockReturnValue({
      rows: [],
      queueQuery: { isLoading: false, isError: false, data: [] },
      updateStatusMutation: { mutate: vi.fn(), isError: false, isPending: false },
      generateDraftMutation: { mutate: vi.fn(), isError: false, isPending: false }
    });
  });

  it("renders analyst cockpit route headers", () => {
    renderWithQueryClient(<ProgramsPage />);
    renderWithQueryClient(<TargetsPage />);
    renderWithQueryClient(<OpportunitiesPage />);
    renderWithQueryClient(<PredictionsPage />);
    renderWithQueryClient(<AgentsPage />);
    renderWithQueryClient(<RetrospectivePage />);
    renderWithQueryClient(<BriefingPage />);

    expect(screen.getByText("Bug Bounty Programs")).toBeInTheDocument();
    expect(screen.getByText("Monitored Targets")).toBeInTheDocument();
    expect(screen.getByText("Opportunity Rankings")).toBeInTheDocument();
    expect(screen.getByText("Predictions and Signal Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Specialized Agents")).toBeInTheDocument();
    expect(screen.getByText("Retrospective Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Analyst Briefing and Report Drafts")).toBeInTheDocument();
  });

  it("wires run prediction action", () => {
    const mutate = vi.fn();
    mocks.usePredictionSignals.mockReturnValue({
      predictionsQuery: { isLoading: false, isError: false, data: [] },
      signalsQuery: { data: [] },
      deltasQuery: { data: [] },
      recommendationsQuery: { data: [] },
      analystSupportQuery: { isLoading: false, isError: false, data: null },
      runMutation: { mutate, isPending: false, isError: false }
    });

    renderWithQueryClient(<PredictionsPage />);
    fireEvent.click(screen.getByText("Run Prediction Cycle"));
    expect(mutate).toHaveBeenCalled();
  });

  it("filters programs and renders sparse-field fallbacks safely", () => {
    mocks.useBountyPrograms.mockReturnValue({
      rows: [
        {
          programId: "program-1",
          name: null,
          platform: null,
          status: null,
          monitoredTargets: 2,
          activeSchedules: 1,
          candidateFindings: 3,
          yieldScore: null,
          opportunityScore: null
        },
        {
          programId: "program-2",
          name: "Acme Program",
          platform: "hackerone",
          status: "active",
          monitoredTargets: 5,
          activeSchedules: 2,
          candidateFindings: 9,
          yieldScore: 0.7,
          opportunityScore: 0.8
        }
      ],
      isLoading: false,
      errors: []
    });

    renderWithQueryClient(<ProgramsPage />);
    expect(screen.getByText("Unnamed Program")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("search name, platform, program id"), {
      target: { value: "Acme" }
    });
    expect(screen.getByText("Acme Program")).toBeInTheDocument();
    expect(screen.queryByText("Unnamed Program")).not.toBeInTheDocument();
  });

  it("filters opportunity rankings by subject type and search", () => {
    mocks.useOpportunityRankings.mockReturnValue({
      rows: [
        {
          id: "rank-1",
          programId: "program-1",
          scopeTargetId: "target-1",
          subjectType: "TARGET",
          subjectKey: "api.example.com",
          selectionScore: 0.8,
          priorityRank: 1,
          confidenceScore: 0.7,
          duplicateRiskScore: 0.1,
          evidenceCompletenessScore: 0.65,
          recommendedWorkflow: "workflow_web_attack_surface",
          recommendedAction: "manual_validation",
          reasoningSummary: "target expansion"
        },
        {
          id: "rank-2",
          programId: "program-1",
          scopeTargetId: null,
          subjectType: "PROGRAM",
          subjectKey: "program-1",
          selectionScore: 0.4,
          priorityRank: 2,
          confidenceScore: 0.4,
          duplicateRiskScore: 0.5,
          evidenceCompletenessScore: 0.3,
          recommendedWorkflow: null,
          recommendedAction: null,
          reasoningSummary: "program baseline"
        }
      ],
      rankingsQuery: { isLoading: false, isError: false, data: [{}, {}] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      predictionsQuery: { isLoading: false, isError: false, data: [] }
    });

    renderWithQueryClient(<OpportunitiesPage />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "TARGET" } });
    fireEvent.change(screen.getByPlaceholderText("search subject, ids, workflow, actions"), {
      target: { value: "api.example.com" }
    });
    expect(screen.getByText("TARGET:api.example.com")).toBeInTheDocument();
    expect(screen.queryByText("PROGRAM:program-1")).not.toBeInTheDocument();
  });

  it("wires retrospective run action", () => {
    const mutate = vi.fn();
    mocks.useRetrospective.mockReturnValue({
      summaryQuery: { isLoading: false, isError: false, data: null },
      workflowsQuery: { isLoading: false, isError: false, data: [] },
      targetsQuery: { isLoading: false, isError: false, data: [] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      alertsQuery: { isLoading: false, isError: false, data: [] },
      runMutation: { mutate, isPending: false, isError: false }
    });

    renderWithQueryClient(<RetrospectivePage />);
    fireEvent.click(screen.getByText("Run Phase 10"));
    expect(mutate).toHaveBeenCalled();
  });

  it("wires phase10.5 agent controls", () => {
    const runMutate = vi.fn();
    const evaluateMutate = vi.fn();
    const syncMutate = vi.fn();
    mocks.useAgentFramework.mockReturnValue({
      agentsQuery: {
        isLoading: false,
        isError: false,
        data: [
          {
            id: "agent-row-1",
            agent_id: "scope_parsing_agent",
            agent_name: "Scope Parsing Agent",
            category: "recon_discovery",
            model_preference: "kai/selfhosted-small",
            model_runtime: "self_hosted",
            confidence_threshold: 0.75,
            escalation_agent_id: "analyst_briefing_agent",
            enabled: true
          }
        ]
      },
      executionsQuery: { isLoading: false, isError: false, data: [] },
      evaluationsQuery: { isLoading: false, isError: false, data: [] },
      syncMutation: { mutate: syncMutate, isPending: false, isError: false },
      runMutation: { mutate: runMutate, isPending: false, isError: false },
      evaluateMutation: { mutate: evaluateMutate, isPending: false, isError: false },
      summary: {
        agents: 1,
        executions: 0,
        succeeded: 0,
        escalated: 0,
        failed: 0,
        passingEvaluations: 0,
        averageSuccessRate: 0.65
      }
    });

    renderWithQueryClient(<AgentsPage />);
    fireEvent.click(screen.getByText("Sync Registry"));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "scope_parsing_agent" } });
    fireEvent.click(screen.getByText("Run Agent"));
    fireEvent.click(screen.getByText("Evaluate"));

    expect(syncMutate).toHaveBeenCalled();
    expect(runMutate).toHaveBeenCalled();
    expect(evaluateMutate).toHaveBeenCalled();
  });

  it("renders prediction supporting-source failures and empty analyst support", () => {
    mocks.usePredictionSignals.mockReturnValue({
      predictionsQuery: { isLoading: false, isError: false, data: [] },
      signalsQuery: { isLoading: false, isError: true, error: new Error("signal source failed"), data: [] },
      deltasQuery: { isLoading: false, isError: true, error: new Error("delta source failed"), data: [] },
      recommendationsQuery: {
        isLoading: false,
        isError: true,
        error: new Error("recommendation source failed"),
        data: []
      },
      analystSupportQuery: { isLoading: false, isError: false, data: null },
      runMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });

    renderWithQueryClient(<PredictionsPage />);
    expect(screen.getByText("Signal intelligence failed")).toBeInTheDocument();
    expect(screen.getByText("Delta source failed")).toBeInTheDocument();
    expect(screen.getByText("Recommendation source failed")).toBeInTheDocument();
    expect(screen.getByText("No analyst support output")).toBeInTheDocument();
  });

  it("renders loading/error state for opportunities", () => {
    mocks.useOpportunityRankings.mockReturnValue({
      rows: [],
      rankingsQuery: { isLoading: true, isError: false, data: null },
      recommendationsQuery: {
        isLoading: false,
        isError: true,
        error: new Error("recommendation source failed"),
        data: null
      },
      predictionsQuery: { isLoading: false, isError: false, data: [] }
    });

    renderWithQueryClient(<OpportunitiesPage />);
    expect(screen.getByText("Loading opportunity rankings...")).toBeInTheDocument();
    expect(screen.getByText("Recommendations source failed")).toBeInTheDocument();
  });

  it("renders retrospective loading/error and empty states", () => {
    mocks.useRetrospective.mockReturnValue({
      summaryQuery: { isLoading: true, isError: true, error: new Error("retro failed"), data: null },
      workflowsQuery: { isLoading: false, isError: false, data: [] },
      targetsQuery: { isLoading: false, isError: false, data: [] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      alertsQuery: { isLoading: false, isError: false, data: [] },
      runMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });

    renderWithQueryClient(<RetrospectivePage />);
    expect(screen.getByText("Loading retrospective intelligence...")).toBeInTheDocument();
    expect(screen.getByText("Retrospective summary failed")).toBeInTheDocument();
    expect(screen.getByText("No workflow value leaders")).toBeInTheDocument();
  });

  it("wires triage actions to candidate queue mutations", () => {
    const updateMutate = vi.fn();
    const draftMutate = vi.fn();
    mocks.useCandidateQueue.mockReturnValue({
      rows: [
        {
          id: "queue-1",
          vulnerability_type: "XSS",
          affected_asset: "app.example.com",
          affected_endpoint: "/search",
          confidence_score: 0.8,
          reportability_score: 0.75,
          duplicate_risk_score: 0.2,
          evidence_completeness_score: 0.7,
          evidence_readiness_state: "READY_FOR_REVIEW",
          status: "new",
          severity_hint: "HIGH",
          artifact_ref: "output/reports/a.json",
          recommended_workflow: "workflow_quick_vuln_sweep",
          recommended_action: "manual_validation"
        }
      ],
      queueQuery: { isLoading: false, isError: false, data: [{}] },
      updateStatusMutation: { mutate: updateMutate, isError: false, isPending: false },
      generateDraftMutation: { mutate: draftMutate, isError: false, isPending: false }
    });

    renderWithQueryClient(<TriagePage />);
    fireEvent.click(screen.getByText("Triaged"));
    fireEvent.click(screen.getByText("Draft"));
    expect(updateMutate).toHaveBeenCalled();
    expect(draftMutate).toHaveBeenCalled();
  });

  it("shows triage UUID validation and disables actions while mutation is pending", () => {
    mocks.useCandidateQueue.mockReturnValue({
      rows: [
        {
          id: "queue-1",
          vulnerability_type: "XSS",
          affected_asset: "app.example.com",
          affected_endpoint: "/search",
          confidence_score: 0.8,
          reportability_score: 0.75,
          duplicate_risk_score: 0.2,
          evidence_completeness_score: 0.7,
          evidence_readiness_state: "READY_FOR_REVIEW",
          status: "new",
          severity_hint: "HIGH",
          artifact_ref: "output/reports/a.json",
          recommended_workflow: "workflow_quick_vuln_sweep",
          recommended_action: "manual_validation",
          missing_evidence_fields: ["impact_details"]
        }
      ],
      queueQuery: { isLoading: false, isError: false, data: [{}] },
      updateStatusMutation: { mutate: vi.fn(), isError: false, isPending: true },
      generateDraftMutation: { mutate: vi.fn(), isError: false, isPending: false }
    });

    renderWithQueryClient(<TriagePage />);
    fireEvent.change(screen.getByPlaceholderText("program UUID (optional)"), {
      target: { value: "not-a-uuid" }
    });
    fireEvent.click(screen.getByText("Apply Program Filter"));
    expect(screen.getByText("Program filter must be a valid UUID.")).toBeInTheDocument();

    expect(screen.getByText("Triaged")).toBeDisabled();
    expect(screen.getByText("Needs Manual")).toBeDisabled();
    expect(screen.getByText("Ready Report")).toBeDisabled();
    expect(screen.getByText("Draft")).toBeDisabled();
    expect(screen.getByText(/missing: impact_details/)).toBeInTheDocument();
  });
});
