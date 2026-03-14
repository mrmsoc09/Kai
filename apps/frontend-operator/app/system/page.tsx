"use client";

import { useState } from "react";

import { useBountyOperations } from "@/hooks/useBountyOperations";

import { OperationsHealthPanel } from "@/components/bugbounty/OperationsHealthPanel";
import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { EmptyState } from "@/components/data-display/EmptyState";
import { JsonViewer } from "@/components/data-display/JsonViewer";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SystemPage() {
  const [programId, setProgramId] = useState("");
  const data = useBountyOperations(programId.trim() || undefined);

  return (
    <div className="operator-grid">
      <PageHeader
        title="System Diagnostics"
        description="Scheduler, readiness, adaptive action, and tool-health operations view for bug bounty monitoring."
      />

      <ProgramFilterCard value={programId} onChange={setProgramId} />

      {data.schedulerStatusQuery.isLoading ||
      data.schedulesQuery.isLoading ||
      data.readinessRecordsQuery.isLoading ||
      data.adaptiveActionsQuery.isLoading ||
      data.toolsHealthQuery.isLoading ||
      data.healthQuery.isLoading ||
      data.readinessQuery.isLoading ? (
        <LoadingState label="Loading system diagnostics..." />
      ) : null}

      {data.schedulerStatusQuery.isError ? (
        <ErrorState error={data.schedulerStatusQuery.error} title="Scheduler summary failed" />
      ) : null}
      {data.schedulesQuery.isError ? <ErrorState error={data.schedulesQuery.error} title="Schedule list failed" /> : null}
      {data.readinessRecordsQuery.isError ? (
        <ErrorState error={data.readinessRecordsQuery.error} title="Readiness records failed" />
      ) : null}
      {data.adaptiveActionsQuery.isError ? (
        <ErrorState error={data.adaptiveActionsQuery.error} title="Adaptive actions failed" />
      ) : null}
      {data.toolsHealthQuery.isError ? (
        <ErrorState error={data.toolsHealthQuery.error} title="Tool health failed" />
      ) : null}
      {data.healthQuery.isError ? <ErrorState error={data.healthQuery.error} title="Liveness failed" /> : null}
      {data.readinessQuery.isError ? <ErrorState error={data.readinessQuery.error} title="Readiness failed" /> : null}

      <OperationsHealthPanel
        schedulerStatus={data.schedulerStatusQuery.data}
        toolsHealth={data.toolsHealthQuery.data}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Readiness Records</CardTitle>
          </CardHeader>
          <CardContent>
            {(data.readinessRecordsQuery.data?.length ?? 0) > 0 ? (
              <JsonViewer value={(data.readinessRecordsQuery.data ?? []).slice(0, 20)} />
            ) : (
              <EmptyState
                title="No readiness records"
                description="No readiness evaluations are available for the selected program filter."
              />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent Adaptive Actions</CardTitle>
          </CardHeader>
          <CardContent>
            {(data.adaptiveActionsQuery.data?.length ?? 0) > 0 ? (
              <JsonViewer value={(data.adaptiveActionsQuery.data ?? []).slice(0, 20)} />
            ) : (
              <EmptyState
                title="No adaptive actions"
                description="No adaptive scheduling actions have been recorded for this filter."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
