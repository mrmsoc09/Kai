"use client";

import { useState } from "react";

import { useBountyOperations } from "@/hooks/useBountyOperations";
import { useTrackedCampaignData } from "@/hooks/useTrackedCampaignData";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";
import { flattenRecentAuditEvents } from "@/lib/utils/soc";

import { AuditEventList } from "@/components/data-display/AuditEventList";
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
  const trackedMissions = useTrackedCampaignIds();
  const trackedData = useTrackedCampaignData(trackedMissions.trackedCampaignIds);
  const systemLogEvents = flattenRecentAuditEvents({ campaignDiagnostics: trackedData.diagnostics }).slice(0, 60);

  return (
    <div className="operator-grid">
      <PageHeader
        title="System / Logs"
        description="Scheduler, readiness, adaptive actions, tool-health telemetry, and mission audit logs."
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

      <Card>
        <CardHeader>
          <CardTitle>Mission System Logs (Audit Feed)</CardTitle>
        </CardHeader>
        <CardContent>
          {trackedData.isLoading ? <LoadingState label="Loading mission audit logs..." /> : null}
          {trackedData.errors.length > 0 ? (
            <div className="space-y-2">
              {trackedData.errors.map((entry, index) => (
                <ErrorState
                  key={`${entry.scope}:${entry.campaignId}:${index}`}
                  error={entry.error}
                  title={`Mission log source failed (${entry.campaignId})`}
                />
              ))}
            </div>
          ) : null}
          {systemLogEvents.length > 0 ? (
            <AuditEventList events={systemLogEvents} />
          ) : (
            <EmptyState
              title="No mission logs"
              description="Track missions from the Missions page to populate system audit logs."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
