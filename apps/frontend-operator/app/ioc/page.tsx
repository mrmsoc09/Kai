"use client";

import { useIoc } from "@/hooks/useIoc";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";

import { BackendSupportPending } from "@/components/soc/BackendSupportPending";
import { IocTable } from "@/components/soc/IocTable";
import { TrackedCampaignSelector } from "@/components/soc/TrackedCampaignSelector";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";

export default function IocPage() {
  const tracked = useTrackedCampaignIds();
  const data = useIoc(tracked.trackedCampaignIds);

  return (
    <div className="operator-grid">
      <PageHeader
        title="IOC Monitoring"
        description="Indicator-centric view derived from canonical findings, observations, and audit payloads."
      />

      <TrackedCampaignSelector
        trackedCampaignIds={tracked.trackedCampaignIds}
        onAdd={tracked.addCampaignId}
        onRemove={tracked.removeCampaignId}
      />

      <BackendSupportPending
        title="IOC extraction is deterministic and conservative"
        description="Indicators are extracted with strict regex matching from canonical text payloads. No fuzzy or AI IOC inference is applied."
      />

      {data.findingsQueueQuery.isLoading ? <LoadingState label="Loading IOC monitoring..." /> : null}
      {data.findingsQueueQuery.isError ? (
        <ErrorState error={data.findingsQueueQuery.error} title="IOC source failed" />
      ) : null}
      {data.tracked.errors.length > 0 ? (
        <div className="space-y-2">
          {data.tracked.errors.map((entry) => (
            <ErrorState
              key={`${entry.scope}:${entry.campaignId}`}
              error={entry.error}
              title={`Campaign diagnostics failed (${entry.campaignId})`}
            />
          ))}
        </div>
      ) : null}

      {data.iocs.length > 0 ? (
        <IocTable rows={data.iocs} />
      ) : (
        <EmptyState
          title="No indicators extracted"
          description="No IOC patterns were found in the currently available canonical data."
        />
      )}
    </div>
  );
}
