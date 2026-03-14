import type { CampaignStatusResponse } from "@/lib/types";

export function BranchGraphPanel({ jobs }: { jobs: CampaignStatusResponse["phase_jobs"] }) {
  const ordered = [...jobs].sort((a, b) => a.phase_order - b.phase_order);
  return (
    <div className="rounded-md border border-border bg-panel p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-muted">Phase Timeline</p>
      <div className="flex flex-wrap items-center gap-2 text-sm text-foreground">
        {ordered.map((job, index) => (
          <div key={job.id} className="flex items-center gap-2">
            <span className="rounded-md border border-intelligence/40 bg-intelligence/15 px-2 py-1 text-xs text-intelligence">
              {job.phase_name}
            </span>
            {index < ordered.length - 1 ? <span className="text-muted">→</span> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
