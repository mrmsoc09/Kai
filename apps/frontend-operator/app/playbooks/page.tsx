"use client";

import { usePlaybooks } from "@/hooks/usePlaybooks";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";

import { BackendSupportPending } from "@/components/soc/BackendSupportPending";
import { PlaybookCatalog } from "@/components/soc/PlaybookCatalog";
import { TrackedCampaignSelector } from "@/components/soc/TrackedCampaignSelector";
import { ErrorState } from "@/components/data-display/ErrorState";
import { PageHeader } from "@/components/layout/PageHeader";

export default function PlaybooksPage() {
  const tracked = useTrackedCampaignIds();
  const data = usePlaybooks(tracked.trackedCampaignIds);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Automation and Playbooks"
        description="Operator catalog of canonical execution playbooks derived from phase job graphs."
      />

      <TrackedCampaignSelector
        trackedCampaignIds={tracked.trackedCampaignIds}
        onAdd={tracked.addCampaignId}
        onRemove={tracked.removeCampaignId}
      />

      <BackendSupportPending
        title="Playbook execution controls pending"
        description="This page currently exposes canonical playbook catalog and execution state only. Direct playbook run controls require dedicated backend APIs."
      />

      <PlaybookCatalog rows={data.playbooks} />

      {data.tracked.errors.length > 0 ? (
        <div className="space-y-2">
          {data.tracked.errors.map((entry) => (
            <ErrorState
              key={`${entry.scope}:${entry.campaignId}`}
              error={entry.error}
              title={`Playbook source failed (${entry.campaignId})`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
