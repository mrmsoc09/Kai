import React from "react";
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AlertsPage from "@/app/alerts/page";
import AnalyticsPage from "@/app/analytics/page";
import AttackSurfacePage from "@/app/attack-surface/page";
import EvidencePage from "@/app/evidence/page";
import IocPage from "@/app/ioc/page";
import OverviewPage from "@/app/overview/page";
import PlaybooksPage from "@/app/playbooks/page";
import ReconPage from "@/app/recon/page";
import SystemPage from "@/app/system/page";
import ThreatIntelPage from "@/app/threat-intel/page";
import TimelinePage from "@/app/timeline/page";
import TriagePage from "@/app/triage/page";
import { renderWithQueryClient } from "@/tests/test-utils";

const mocks = vi.hoisted(() => ({
  useTrackedCampaignIds: vi.fn(),
  useBountyDashboard: vi.fn(),
  useAttackSurface: vi.fn(),
  useReconActivity: vi.fn(),
  useCandidateQueue: vi.fn(),
  useThreatIntel: vi.fn(),
  useIoc: vi.fn(),
  useTimeline: vi.fn(),
  useAnalytics: vi.fn(),
  usePlaybooks: vi.fn(),
  useAlertCenter: vi.fn(),
  useBountyOperations: vi.fn(),
  useCampaigns: vi.fn(),
  useApprovalQueue: vi.fn(),
  useFindingsQueue: vi.fn(),
  useTrackedCampaignData: vi.fn()
}));

vi.mock("@/hooks/useTrackedCampaignIds", () => ({ useTrackedCampaignIds: mocks.useTrackedCampaignIds }));
vi.mock("@/hooks/useBountyDashboard", () => ({ useBountyDashboard: mocks.useBountyDashboard }));
vi.mock("@/hooks/useAttackSurface", () => ({ useAttackSurface: mocks.useAttackSurface }));
vi.mock("@/hooks/useReconActivity", () => ({ useReconActivity: mocks.useReconActivity }));
vi.mock("@/hooks/useCandidateQueue", () => ({ useCandidateQueue: mocks.useCandidateQueue }));
vi.mock("@/hooks/useThreatIntel", () => ({ useThreatIntel: mocks.useThreatIntel }));
vi.mock("@/hooks/useIoc", () => ({ useIoc: mocks.useIoc }));
vi.mock("@/hooks/useTimeline", () => ({ useTimeline: mocks.useTimeline }));
vi.mock("@/hooks/useAnalytics", () => ({ useAnalytics: mocks.useAnalytics }));
vi.mock("@/hooks/usePlaybooks", () => ({ usePlaybooks: mocks.usePlaybooks }));
vi.mock("@/hooks/useAlertCenter", () => ({ useAlertCenter: mocks.useAlertCenter }));
vi.mock("@/hooks/useBountyOperations", () => ({ useBountyOperations: mocks.useBountyOperations }));
vi.mock("@/hooks/useCampaigns", () => ({ useCampaigns: mocks.useCampaigns }));
vi.mock("@/hooks/useApprovalQueue", () => ({ useApprovalQueue: mocks.useApprovalQueue }));
vi.mock("@/hooks/useFindingsQueue", () => ({ useFindingsQueue: mocks.useFindingsQueue }));
vi.mock("@/hooks/useTrackedCampaignData", () => ({ useTrackedCampaignData: mocks.useTrackedCampaignData }));

describe("SOC dashboard surfaces", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mocks.useTrackedCampaignIds.mockReturnValue({
      trackedCampaignIds: [],
      addCampaignId: vi.fn(),
      removeCampaignId: vi.fn()
    });

    mocks.useBountyDashboard.mockReturnValue({
      metrics: {
        programs: 0,
        activeSchedules: 0,
        candidates: 0,
        readyForReport: 0,
        pendingValidation: 0,
        recentDeltas: 0,
        blockedReadiness: 0,
        blockedRecommendations: 0,
        healthyTools: 0,
        totalTools: 0
      },
      programsQuery: { isLoading: false, isError: false, data: [] },
      schedulesQuery: { isLoading: false, isError: false, data: [] },
      schedulerStatusQuery: { isLoading: false, isError: false, data: null },
      candidatesQuery: { isLoading: false, isError: false, data: [] },
      deltasQuery: { isLoading: false, isError: false, data: [] },
      readinessRecordsQuery: { isLoading: false, isError: false, data: [] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      alertSummaryQuery: { isLoading: false, isError: false, data: null },
      toolsHealthQuery: { isLoading: false, isError: false, data: null },
      healthQuery: { isLoading: false, isError: false, data: { status: "ok" } },
      readinessQuery: { isLoading: false, isError: false, data: { status: "ok" } }
    });

    mocks.useAttackSurface.mockReturnValue({
      findingsQueueQuery: { isLoading: false, isError: false, data: { count: 0, items: [] } },
      findingQueries: [],
      findingDiagnostics: [],
      assetRows: [],
      isLoading: false,
      errors: []
    });

    mocks.useReconActivity.mockReturnValue({
      trackedCampaigns: [],
      trackedDiagnostics: [],
      trackedErrors: [],
      reconPhaseRows: [],
      reconAuditEvents: [],
      isLoading: false
    });

    mocks.useCandidateQueue.mockReturnValue({
      rows: [],
      queueQuery: { isLoading: false, isError: false, data: [] },
      duplicateRiskQuery: { isLoading: false, isError: false, data: [] },
      evidenceQuery: { isLoading: false, isError: false, data: [] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      updateStatusMutation: { isError: false },
      generateDraftMutation: { isError: false }
    });

    mocks.useThreatIntel.mockReturnValue({
      findingsQueueQuery: { isLoading: false, isError: false, data: { items: [] } },
      findingDiagnostics: [],
      findingQueries: [],
      technologyCounts: []
    });

    mocks.useIoc.mockReturnValue({
      tracked: { errors: [] },
      findingsQueueQuery: { isLoading: false, isError: false, data: { items: [] } },
      findingDiagnostics: [],
      iocs: []
    });

    mocks.useTimeline.mockReturnValue({
      campaignDiagnosticsQuery: { isLoading: false, isError: false, data: null },
      findingDiagnosticsQuery: { isLoading: false, isError: false, data: null },
      timeline: []
    });

    mocks.useAnalytics.mockReturnValue({
      tracked: { errors: [] },
      summaryQuery: {
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
      },
      findingsQueueQuery: { isLoading: false, isError: false, data: { items: [] } },
      campaignStatusRows: []
    });

    mocks.usePlaybooks.mockReturnValue({
      tracked: { errors: [] },
      playbooks: []
    });

    mocks.useAlertCenter.mockReturnValue({
      rows: [],
      alertsQuery: { isLoading: false, isError: false, data: [] },
      summaryQuery: { isLoading: false, isError: false, data: null },
      syncMutation: { mutate: vi.fn(), isPending: false, isError: false },
      acknowledgeMutation: { mutate: vi.fn(), isPending: false, isError: false },
      resolveMutation: { mutate: vi.fn(), isPending: false, isError: false },
      createCaseMutation: { mutate: vi.fn(), isPending: false, isError: false }
    });

    mocks.useBountyOperations.mockReturnValue({
      schedulerStatusQuery: { isLoading: false, isError: false, data: null },
      schedulesQuery: { isLoading: false, isError: false, data: [] },
      readinessRecordsQuery: { isLoading: false, isError: false, data: [] },
      adaptiveActionsQuery: { isLoading: false, isError: false, data: [] },
      toolsHealthQuery: { isLoading: false, isError: false, data: null },
      healthQuery: { isLoading: false, isError: false, data: null },
      readinessQuery: { isLoading: false, isError: false, data: null }
    });

    mocks.useCampaigns.mockReturnValue([]);
    mocks.useApprovalQueue.mockReturnValue({ diagnosticsQueries: [], approvalGates: [] });
    mocks.useFindingsQueue.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { count: 0, items: [] }
    });
    mocks.useTrackedCampaignData.mockReturnValue({
      campaigns: [],
      diagnostics: [],
      errors: [],
      isLoading: false,
      campaignQueries: [],
      diagnosticsQueries: []
    });
  });

  it("renders all SOC surface route headers", () => {
    renderWithQueryClient(<OverviewPage />);
    renderWithQueryClient(<AttackSurfacePage />);
    renderWithQueryClient(<ReconPage />);
    renderWithQueryClient(<TriagePage />);
    renderWithQueryClient(<EvidencePage />);
    renderWithQueryClient(<ThreatIntelPage />);
    renderWithQueryClient(<IocPage />);
    renderWithQueryClient(<TimelinePage />);
    renderWithQueryClient(<AnalyticsPage />);
    renderWithQueryClient(<PlaybooksPage />);
    renderWithQueryClient(<AlertsPage />);
    renderWithQueryClient(<SystemPage />);

    expect(screen.getByText("Action Board")).toBeInTheDocument();
    expect(screen.getByText("Attack Surface Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Reconnaissance Activity")).toBeInTheDocument();
    expect(screen.getByText("Findings Triage Center")).toBeInTheDocument();
    expect(screen.getByText("Evidence and Artifact Repository")).toBeInTheDocument();
    expect(screen.getByText("Threat Intelligence Feed")).toBeInTheDocument();
    expect(screen.getByText("IOC Monitoring")).toBeInTheDocument();
    expect(screen.getByText("Investigation Timeline")).toBeInTheDocument();
    expect(screen.getByText("Campaign Performance Analytics")).toBeInTheDocument();
    expect(screen.getByText("Automation and Playbooks")).toBeInTheDocument();
    expect(screen.getByText("Alerting and Notifications")).toBeInTheDocument();
    expect(screen.getByText("System / Logs")).toBeInTheDocument();
  }, 15000);

  it("renders loading and error states for key SOC pages", () => {
    mocks.useBountyDashboard.mockReturnValue({
      metrics: {
        programs: 0,
        activeSchedules: 0,
        candidates: 0,
        readyForReport: 0,
        pendingValidation: 0,
        recentDeltas: 0,
        blockedReadiness: 0,
        blockedRecommendations: 0,
        healthyTools: 0,
        totalTools: 0
      },
      programsQuery: { isLoading: false, isError: false, data: [] },
      schedulesQuery: { isLoading: false, isError: false, data: [] },
      schedulerStatusQuery: { isLoading: true, isError: false, data: null },
      candidatesQuery: { isLoading: false, isError: false, data: [] },
      deltasQuery: { isLoading: false, isError: false, data: [] },
      readinessRecordsQuery: { isLoading: false, isError: false, data: [] },
      recommendationsQuery: { isLoading: false, isError: false, data: [] },
      alertSummaryQuery: { isLoading: false, isError: false, data: null },
      toolsHealthQuery: { isLoading: false, isError: false, data: null },
      healthQuery: { isLoading: false, isError: false, data: null },
      readinessQuery: { isLoading: false, isError: false, data: null }
    });
    mocks.useFindingsQueue.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined
    });
    mocks.useAttackSurface.mockReturnValue({
      findingsQueueQuery: { isLoading: false, isError: false, data: { count: 0, items: [] } },
      findingQueries: [],
      findingDiagnostics: [],
      assetRows: [],
      isLoading: false,
      errors: [new Error("attack surface error")]
    });

    renderWithQueryClient(<OverviewPage />);
    renderWithQueryClient(<AttackSurfacePage />);
    expect(screen.getByText("Loading findings...")).toBeInTheDocument();
    expect(screen.getByText("Attack surface load failed")).toBeInTheDocument();
  });
});
