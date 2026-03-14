import type { CampaignStatusResponse } from "@/lib/types";

import { StatusBadge } from "@/components/status/StatusBadge";

export function PhaseTimeline({ jobs }: { jobs: CampaignStatusResponse["phase_jobs"] }) {
  const ordered = [...jobs].sort((a, b) => a.phase_order - b.phase_order);
  return (
    <div className="space-y-2">
      {ordered.map((job) => (
        <div key={job.id} className="flex items-center justify-between rounded-md border border-border bg-panel p-2">
          <div>
            <p className="text-sm font-medium text-foreground">{job.phase_name}</p>
            <p className="font-mono text-xs text-muted">{job.id}</p>
          </div>
          <StatusBadge status={job.status} />
        </div>
      ))}
    </div>
  );
}
