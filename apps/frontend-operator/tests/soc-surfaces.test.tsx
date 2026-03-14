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
  useOverview: vi.fn(),
  useAttackSurface: vi.fn(),
  useReconActivity: vi.fn(),
  useFindingsQueue: vi.fn(),
  useThreatIntel: vi.fn(),
  useIoc: vi.fn(),
  useTimeline: vi.fn(),
  useAnalytics: vi.fn(),
  usePlaybooks: vi.fn(),
  useAlerts: vi.fn(),
  useSystemDiagnostics: vi.fn()
}));

vi.mock("@/hooks/useTrackedCampaignIds", () => ({ useTrackedCampaignIds: mocks.useTrackedCampaignIds }));
vi.mock("@/hooks/useOverview", () => ({ useOverview: mocks.useOverview }));
vi.mock("@/hooks/useAttackSurface", () => ({ useAttackSurface: mocks.useAttackSurface }));
vi.mock("@/hooks/useReconActivity", () => ({ useReconActivity: mocks.useReconActivity }));
vi.mock("@/hooks/useFindingsQueue", () => ({ useFindingsQueue: mocks.useFindingsQueue }));
vi.mock("@/hooks/useThreatIntel", () => ({ useThreatIntel: mocks.useThreatIntel }));
vi.mock("@/hooks/useIoc", () => ({ useIoc: mocks.useIoc }));
vi.mock("@/hooks/useTimeline", () => ({ useTimeline: mocks.useTimeline }));
vi.mock("@/hooks/useAnalytics", () => ({ useAnalytics: mocks.useAnalytics }));
vi.mock("@/hooks/usePlaybooks", () => ({ usePlaybooks: mocks.usePlaybooks }));
vi.mock("@/hooks/useAlerts", () => ({ useAlerts: mocks.useAlerts }));
vi.mock("@/hooks/useSystemDiagnostics", () => ({ useSystemDiagnostics: mocks.useSystemDiagnostics }));

describe("SOC dashboard surfaces", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mocks.useTrackedCampaignIds.mockReturnValue({
      trackedCampaignIds: [],
      addCampaignId: vi.fn(),
      removeCampaignId: vi.fn()
    });

    mocks.useOverview.mockReturnValue({
      trackedCampaigns: [],
      trackedDiagnostics: [],
      trackedErrors: [],
      summaryQuery: { isLoading: false, isError: false, data: null },
      healthQuery: { isLoading: false, isError: false, data: { status: "ok" } },
      readinessQuery: { isLoading: false, isError: false, data: { status: "ok" } },
      findingsQueueQuery: { isLoading: false, isError: false, data: { items: [] } },
      alerts: [],
      recentAuditEvents: []
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

    mocks.useFindingsQueue.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { count: 0, items: [] }
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

    mocks.useAlerts.mockReturnValue({
      tracked: { errors: [] },
      findingsQueueQuery: { isLoading: false, isError: false, data: { items: [] } },
      alerts: []
    });

    mocks.useSystemDiagnostics.mockReturnValue({
      summaryQuery: { isLoading: false, isError: false, data: null },
      healthQuery: { isLoading: false, isError: false, data: null },
      readinessQuery: { isLoading: false, isError: false, data: null },
      campaignDiagnosticsQuery: { isLoading: false, isError: false, data: null },
      findingDiagnosticsQuery: { isLoading: false, isError: false, data: null }
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

    expect(screen.getByText("Global Security Overview")).toBeInTheDocument();
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
    expect(screen.getByText("System Diagnostics")).toBeInTheDocument();
  });

  it("renders loading and error states for key SOC pages", () => {
    mocks.useOverview.mockReturnValue({
      trackedCampaigns: [],
      trackedDiagnostics: [],
      trackedErrors: [],
      summaryQuery: { isLoading: true, isError: false, data: null },
      healthQuery: { isLoading: false, isError: true, error: new Error("health error"), data: null },
      readinessQuery: { isLoading: false, isError: false, data: null },
      findingsQueueQuery: { isLoading: false, isError: false, data: { items: [] } },
      alerts: [],
      recentAuditEvents: []
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
    expect(screen.getByText("Loading diagnostics summary...")).toBeInTheDocument();
    expect(screen.getByText("Liveness failed")).toBeInTheDocument();
    expect(screen.getByText("Attack surface load failed")).toBeInTheDocument();
  });
});
