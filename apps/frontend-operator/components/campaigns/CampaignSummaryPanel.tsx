import type { CampaignStatusResponse } from "@/lib/types";

import { KeyValueGrid } from "@/components/data-display/KeyValueGrid";
import { StatusBadge } from "@/components/status/StatusBadge";

export function CampaignSummaryPanel({ campaign }: { campaign: CampaignStatusResponse }) {
  return (
    <KeyValueGrid
      items={[
        { key: "Campaign ID", value: <span className="font-mono text-xs">{campaign.campaign.id}</span> },
        { key: "Status", value: <StatusBadge status={campaign.campaign.status} /> },
        { key: "Program ID", value: <span className="font-mono text-xs">{campaign.campaign.program_id}</span> },
        { key: "Branches", value: campaign.branches.length },
        { key: "Phase Jobs", value: campaign.phase_jobs.length },
        { key: "Updated", value: campaign.campaign.updated_at ?? campaign.campaign.created_at ?? "n/a" }
      ]}
    />
  );
}
