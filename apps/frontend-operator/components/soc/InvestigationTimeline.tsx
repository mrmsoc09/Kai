import type { SocTimelineItem } from "@/lib/types";

import { JsonViewer } from "@/components/data-display/JsonViewer";
import { EmptyState } from "@/components/data-display/EmptyState";
import { StatusBadge } from "@/components/status/StatusBadge";

export function InvestigationTimeline({ items }: { items: SocTimelineItem[] }) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No timeline events"
        description="Select a campaign or finding to build an investigation timeline from audit events."
      />
    );
  }

  return (
    <ol className="space-y-3">
      {items.map((item) => (
        <li key={item.id} className="rounded-md border border-border bg-panel p-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-mono text-muted">{item.happenedAt ?? "n/a"}</span>
            <StatusBadge status={item.eventType} className="normal-case tracking-normal" />
            {item.actor ? <span className="text-muted">actor: {item.actor}</span> : null}
            {item.campaignId ? <span className="font-mono text-muted">campaign: {item.campaignId}</span> : null}
            {item.findingId ? <span className="font-mono text-muted">finding: {item.findingId}</span> : null}
          </div>
          {item.message ? <p className="mt-2 text-sm text-foreground">{item.message}</p> : null}
          {Object.keys(item.payload ?? {}).length > 0 ? (
            <div className="mt-2">
              <JsonViewer value={item.payload} />
            </div>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
