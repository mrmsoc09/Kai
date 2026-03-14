import type { FindingQueueItem } from "@/lib/types";

import { FindingsQueueTable } from "@/components/findings/FindingsQueueTable";
import { EmptyState } from "@/components/data-display/EmptyState";

export function FindingsTriagePanel({
  rows,
  title = "Triage Queue"
}: {
  rows: FindingQueueItem[];
  title?: string;
}) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No findings in triage"
        description="No findings matched the current triage filters."
      />
    );
  }
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted">{title}</p>
      <FindingsQueueTable rows={rows} />
    </div>
  );
}
