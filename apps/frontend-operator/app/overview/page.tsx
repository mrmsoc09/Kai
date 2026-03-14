"use client";

import { useMemo } from "react";

import { useOverview } from "@/hooks/useOverview";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";

import { AlertsTable } from "@/components/soc/AlertsTable";
import { OverviewSummaryCards } from "@/components/soc/OverviewSummaryCards";
import { TrackedCampaignSelector } from "@/components/soc/TrackedCampaignSelector";
import { DiagnosticsSummaryCards } from "@/components/diagnostics/DiagnosticsSummaryCards";
import { HealthPanel } from "@/components/diagnostics/HealthPanel";
import { AuditEventList } from "@/components/data-display/AuditEventList";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function OverviewPage() {
  const tracked = useTrackedCampaignIds();
  const data = useOverview(tracked.trackedCampaignIds);

  const summaryMetrics = useMemo(() => {
    const activeCampaigns = data.trackedCampaigns.filter((item) =>
      ["RUNNING", "READY"].includes(item.campaign.status)
    ).length;
    const findingsAwaitingReview = (data.findingsQueueQuery.data?.items ?? []).filter((item) =>
      ["NEEDS_REVIEW", "READY_FOR_REVIEW"].includes(item.readiness_status.toUpperCase())
    ).length;
    const pendingApprovals = data.trackedDiagnostics.reduce(
      (sum, item) => sum + (item.status_breakdown.approval_gates?.PENDING ?? 0),
      0
    );
    const exportWarnings = data.alerts.filter((alert) => alert.category === "EXPORT").length;
    const runningTools = data.trackedDiagnostics.reduce(
      (sum, item) => sum + (item.status_breakdown.tool_executions?.RUNNING ?? 0),
      0
    );
    return [
      {
        title: "Active Campaigns",
        value: activeCampaigns,
        status: activeCampaigns > 0 ? "RUNNING" : "READY",
        helper: `${data.trackedCampaigns.length} tracked`
      },
      {
        title: "Findings Awaiting Review",
        value: findingsAwaitingReview,
        status: findingsAwaitingReview > 0 ? "NEEDS_REVIEW" : "COMPLETED"
      },
      {
        title: "Pending Approvals",
        value: pendingApprovals,
        status: pendingApprovals > 0 ? "WAITING_APPROVAL" : "COMPLETED"
      },
      {
        title: "Export Validation Warnings",
        value: exportWarnings,
        status: exportWarnings > 0 ? "BLOCKED" : "READY_FOR_SUBMISSION"
      },
      {
        title: "Running Tool Executions",
        value: runningTools,
        status: runningTools > 0 ? "RUNNING" : "READY"
      }
    ];
  }, [data.alerts, data.findingsQueueQuery.data?.items, data.trackedCampaigns, data.trackedDiagnostics]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Global Security Overview"
        description="Operator command surface for campaign activity, review pressure, approvals, exports, and health."
      />

      <TrackedCampaignSelector
        trackedCampaignIds={tracked.trackedCampaignIds}
        onAdd={tracked.addCampaignId}
        onRemove={tracked.removeCampaignId}
      />

      <OverviewSummaryCards metrics={summaryMetrics} />

      <div className="grid gap-4 lg:grid-cols-2">
        {data.healthQuery.isLoading ? <LoadingState label="Loading liveness..." /> : null}
        {data.healthQuery.isError ? <ErrorState error={data.healthQuery.error} title="Liveness failed" /> : null}
        {data.healthQuery.data ? <HealthPanel title="Liveness" health={data.healthQuery.data} /> : null}

        {data.readinessQuery.isLoading ? <LoadingState label="Loading readiness..." /> : null}
        {data.readinessQuery.isError ? (
          <ErrorState error={data.readinessQuery.error} title="Readiness failed" />
        ) : null}
        {data.readinessQuery.data ? <HealthPanel title="Readiness" health={data.readinessQuery.data} /> : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Canonical Metrics Snapshot</CardTitle>
        </CardHeader>
        <CardContent>
          {data.summaryQuery.isLoading ? <LoadingState label="Loading diagnostics summary..." /> : null}
          {data.summaryQuery.isError ? <ErrorState error={data.summaryQuery.error} title="Summary failed" /> : null}
          {data.summaryQuery.data ? <DiagnosticsSummaryCards summary={data.summaryQuery.data} /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Alerts and Warnings</CardTitle>
        </CardHeader>
        <CardContent>
          <AlertsTable alerts={data.alerts} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recentAuditEvents.length > 0 ? (
            <AuditEventList events={data.recentAuditEvents} />
          ) : (
            <EmptyState
              title="No recent audit events"
              description="Track campaigns to populate activity visibility in overview."
            />
          )}
        </CardContent>
      </Card>

      {data.trackedErrors.length > 0 ? (
        <div className="space-y-2">
          {data.trackedErrors.map((entry) => (
            <ErrorState
              key={`${entry.scope}:${entry.campaignId}`}
              error={entry.error}
              title={`${entry.scope} load failed (${entry.campaignId})`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
