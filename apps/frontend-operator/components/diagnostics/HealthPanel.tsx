import type { HealthResponse } from "@/lib/types";

import { JsonViewer } from "@/components/data-display/JsonViewer";
import { HealthIndicator } from "@/components/status/HealthIndicator";

export function HealthPanel({ title, health }: { title: string; health: HealthResponse }) {
  return (
    <div className="space-y-2 rounded-md border border-border bg-panel p-3">
      <h4 className="text-sm font-semibold text-foreground">{title}</h4>
      <HealthIndicator status={health.status} />
      <JsonViewer value={health} />
    </div>
  );
}
