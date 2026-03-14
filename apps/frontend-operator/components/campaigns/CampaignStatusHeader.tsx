import type { CampaignStatusResponse } from "@/lib/types";

import { StatusBadge } from "@/components/status/StatusBadge";

export function CampaignStatusHeader({ campaign }: { campaign: CampaignStatusResponse }) {
  return (
    <div className="rounded-md border border-border bg-elevated p-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="font-mono text-xs text-muted">{campaign.campaign.id}</p>
        <StatusBadge status={campaign.campaign.status} />
      </div>
    </div>
  );
}
