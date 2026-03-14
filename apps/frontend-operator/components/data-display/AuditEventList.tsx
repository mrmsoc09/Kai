import type { AuditEvent } from "@/lib/types";

import { EmptyState } from "@/components/data-display/EmptyState";
import { JsonViewer } from "@/components/data-display/JsonViewer";

export function AuditEventList({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No audit events"
        description="No recent audit events were returned by the backend."
      />
    );
  }
  return (
    <div className="space-y-2">
      {events.map((event) => (
        <div key={event.id} className="rounded-md border border-border bg-panel p-2">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold text-foreground">{event.event_type}</span>
            <span className="text-muted">{event.happened_at ?? "n/a"}</span>
            {event.actor ? <span className="text-muted">actor: {event.actor}</span> : null}
          </div>
          {event.message ? <p className="mt-1 text-xs text-foreground">{event.message}</p> : null}
          {Object.keys(event.payload ?? {}).length > 0 ? <div className="mt-2"><JsonViewer value={event.payload} /></div> : null}
        </div>
      ))}
    </div>
  );
}
