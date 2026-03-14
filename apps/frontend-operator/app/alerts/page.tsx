"use client";

import { useAlerts } from "@/hooks/useAlerts";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";

import { AlertsTable } from "@/components/soc/AlertsTable";
import { TrackedCampaignSelector } from "@/components/soc/TrackedCampaignSelector";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";

export default function AlertsPage() {
  const tracked = useTrackedCampaignIds();
  const data = useAlerts(tracked.trackedCampaignIds);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Alerting and Notifications"
        description="Central alert panel derived from approvals, blocked/failed execution state, and export validation diagnostics."
      />

      <TrackedCampaignSelector
        trackedCampaignIds={tracked.trackedCampaignIds}
        onAdd={tracked.addCampaignId}
        onRemove={tracked.removeCampaignId}
      />

      {data.findingsQueueQuery.isLoading ? <LoadingState label="Loading alerts..." /> : null}
      {data.findingsQueueQuery.isError ? <ErrorState error={data.findingsQueueQuery.error} title="Alert source failed" /> : null}

      <AlertsTable alerts={data.alerts} />

      {data.tracked.errors.length > 0 ? (
        <div className="space-y-2">
          {data.tracked.errors.map((entry) => (
            <ErrorState
              key={`${entry.scope}:${entry.campaignId}`}
              error={entry.error}
              title={`Alert diagnostics failed (${entry.campaignId})`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
