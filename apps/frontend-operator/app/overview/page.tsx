"use client";

import { useMemo, useState } from "react";

import { useBountyDashboard } from "@/hooks/useBountyDashboard";

import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { OverviewSummaryCards } from "@/components/soc/OverviewSummaryCards";
import { OperationsHealthPanel } from "@/components/bugbounty/OperationsHealthPanel";
import { ReasoningSummaryPanel } from "@/components/bugbounty/ReasoningSummaryPanel";
import { CandidateQueueTable } from "@/components/bugbounty/CandidateQueueTable";
import { HealthPanel } from "@/components/diagnostics/HealthPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function OverviewPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const data = useBountyDashboard(programIdFilter.trim() || undefined);

  const summaryMetrics = useMemo(() => {
    const metrics = data.metrics;
    return [
      {
        title: "Active Programs",
        value: metrics.programs,
        status: metrics.programs > 0 ? "RUNNING" : "READY"
      },
      {
        title: "Active Schedules",
        value: metrics.activeSchedules,
        status: metrics.activeSchedules > 0 ? "RUNNING" : "READY"
      },
      {
        title: "Candidate Findings",
        value: metrics.candidates,
        status: metrics.candidates > 0 ? "NEEDS_REVIEW" : "COMPLETED"
      },
      {
        title: "Ready For Report",
        value: metrics.readyForReport,
        status: metrics.readyForReport > 0 ? "READY_FOR_SUBMISSION" : "READY"
      },
      {
        title: "Readiness Blocks (Recent)",
        value: metrics.blockedReadiness,
        status: metrics.blockedReadiness > 0 ? "BLOCKED" : "COMPLETED"
      },
      {
        title: "Unresolved Alerts",
        value: metrics.unresolvedAlerts,
        status: metrics.unresolvedAlerts > 0 ? "NEEDS_REVIEW" : "COMPLETED"
      },
      {
        title: "Open Cases",
        value: metrics.openCases,
        status: metrics.openCases > 0 ? "WAITING_APPROVAL" : "COMPLETED"
      }
    ];
  }, [data.metrics]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Global Security Overview"
        description="Analyst cockpit overview of programs, monitored schedules, candidate pressure, and operational health."
      />

      <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />

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
          <CardTitle>Scheduler Snapshot</CardTitle>
        </CardHeader>
        <CardContent>
          {data.schedulerStatusQuery.isLoading ? <LoadingState label="Loading scheduler status..." /> : null}
          {data.schedulerStatusQuery.isError ? (
            <ErrorState error={data.schedulerStatusQuery.error} title="Scheduler status failed" />
          ) : null}
          {data.schedulerStatusQuery.data ? (
            <OperationsHealthPanel
              schedulerStatus={data.schedulerStatusQuery.data}
              toolsHealth={data.toolsHealthQuery.data}
            />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Candidate Queue (Top)</CardTitle>
        </CardHeader>
        <CardContent>
          {data.candidatesQuery.isLoading ? <LoadingState label="Loading candidates..." /> : null}
          {data.candidatesQuery.isError ? (
            <ErrorState error={data.candidatesQuery.error} title="Candidate queue failed" />
          ) : null}
          {data.candidatesQuery.data ? (
            <CandidateQueueTable rows={data.candidatesQuery.data.slice(0, 10)} showActions={false} />
          ) : (
            <EmptyState title="No candidates" description="No candidate findings are available." />
          )}
        </CardContent>
      </Card>

      <ReasoningSummaryPanel
        title="Recommendation Reasoning Summaries"
        summaries={(data.recommendationsQuery.data ?? []).slice(0, 8).map((row) => row.reasoning_summary)}
      />

      {data.toolsHealthQuery.isError ? (
        <ErrorState error={data.toolsHealthQuery.error} title="Tool health failed" />
      ) : null}
      {data.readinessRecordsQuery.isError ? (
        <ErrorState error={data.readinessRecordsQuery.error} title="Readiness records failed" />
      ) : null}
      {data.schedulesQuery.isError ? (
        <ErrorState error={data.schedulesQuery.error} title="Schedule list failed" />
      ) : null}
      {data.deltasQuery.isError ? (
        <ErrorState error={data.deltasQuery.error} title="Delta list failed" />
      ) : null}
      {data.programsQuery.isError ? (
        <ErrorState error={data.programsQuery.error} title="Program list failed" />
      ) : null}
      {data.recommendationsQuery.isError ? (
        <ErrorState error={data.recommendationsQuery.error} title="Recommendations failed" />
      ) : null}
      {data.alertSummaryQuery.isError ? (
        <ErrorState error={data.alertSummaryQuery.error} title="Alert/case summary failed" />
      ) : null}

      {(data.schedulesQuery.data?.length ?? 0) === 0 && !data.schedulesQuery.isLoading ? (
        <div className="space-y-2">
          <EmptyState
            title="No schedules configured"
            description="Create bug bounty schedules to populate recurring execution telemetry."
          />
        </div>
      ) : null}
    </div>
  );
}
