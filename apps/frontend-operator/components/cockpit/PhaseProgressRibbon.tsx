import type { CampaignStatusResponse } from "@/lib/types";

import { PhaseStatusBadge } from "@/components/status/PhaseStatusBadge";

function percentComplete(jobs: CampaignStatusResponse["phase_jobs"]): number {
  if (jobs.length === 0) {
    return 0;
  }
  const completed = jobs.filter((job) => job.status === "COMPLETED").length;
  return Math.round((completed / jobs.length) * 100);
}

export function PhaseProgressRibbon({ jobs }: { jobs: CampaignStatusResponse["phase_jobs"] }) {
  const ordered = [...jobs].sort((a, b) => a.phase_order - b.phase_order);
  const completion = percentComplete(ordered);
  return (
    <div className="space-y-3 rounded-lg border border-border bg-panel p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">Phase Progress</p>
        <p className="text-xs text-muted">{completion}% complete</p>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-elevated">
        <div className="h-full bg-active transition-all" style={{ width: `${completion}%` }} />
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {ordered.map((job) => (
          <div key={job.id} className="rounded-md border border-border bg-elevated p-2">
            <p className="text-xs font-medium text-foreground">{job.phase_name}</p>
            <p className="font-mono text-[11px] text-muted">{job.id}</p>
            <div className="mt-2">
              <PhaseStatusBadge status={job.status} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
