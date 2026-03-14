import type { AuditEvent } from "@/lib/types";

import { AuditEventList } from "@/components/data-display/AuditEventList";

export function AuditFeed({ events }: { events: AuditEvent[] }) {
  return <AuditEventList events={events} />;
}
