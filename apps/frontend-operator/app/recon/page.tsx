"use client";

import { useReconActivity } from "@/hooks/useReconActivity";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";

import { TrackedCampaignSelector } from "@/components/soc/TrackedCampaignSelector";
import { ReconActivityTable } from "@/components/soc/ReconActivityTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { AuditEventList } from "@/components/data-display/AuditEventList";
import { BranchGraphPanel } from "@/components/phases/BranchGraphPanel";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ReconPage() {
  const tracked = useTrackedCampaignIds();
  const data = useReconActivity(tracked.trackedCampaignIds);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Reconnaissance Activity"
        description="Phase and tool execution activity across tracked campaigns with recon-focused visibility."
      />

      <TrackedCampaignSelector
        trackedCampaignIds={tracked.trackedCampaignIds}
        onAdd={tracked.addCampaignId}
        onRemove={tracked.removeCampaignId}
      />

      {data.isLoading ? <LoadingState label="Loading recon activity..." /> : null}
      {data.trackedErrors.length > 0 ? (
        <div className="space-y-2">
          {data.trackedErrors.map((entry) => (
            <ErrorState
              key={`${entry.scope}:${entry.campaignId}`}
              error={entry.error}
              title={`Recon source failed (${entry.campaignId})`}
            />
          ))}
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Recon Phase Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {data.reconPhaseRows.length > 0 ? (
            <ReconActivityTable rows={data.reconPhaseRows} />
          ) : (
            <EmptyState
              title="No recon phase activity"
              description="Track campaigns to inspect recon-discovery, validation, and analysis phases."
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Branch / Phase Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <BranchGraphPanel jobs={data.trackedCampaigns.flatMap((campaign) => campaign.phase_jobs)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Recon-Related Audit Events</CardTitle>
        </CardHeader>
        <CardContent>
          {data.reconAuditEvents.length > 0 ? (
            <AuditEventList events={data.reconAuditEvents.slice(0, 50)} />
          ) : (
            <EmptyState
              title="No recon audit events"
              description="No relevant recon events are visible for the currently tracked campaigns."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
