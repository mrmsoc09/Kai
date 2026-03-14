import type { FindingDiagnosticsResponse } from "@/lib/types";

import { EmptyState } from "@/components/data-display/EmptyState";

export function EvidenceList({ finding }: { finding: FindingDiagnosticsResponse }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-foreground">
        Evidence count: <span className="font-semibold">{finding.counts.evidence}</span>
      </p>
      <p className="text-sm text-foreground">
        Artifact count: <span className="font-semibold">{finding.counts.artifacts}</span>
      </p>
      {finding.recent_observations.length === 0 ? (
        <EmptyState title="No observations" description="No recent observations are available." />
      ) : (
        <ul className="space-y-1 rounded-md border border-border bg-panel p-2 text-xs text-foreground">
          {finding.recent_observations.map((observation) => (
            <li key={observation.id}>
              <span className="font-mono">{observation.id}</span> - {observation.category ?? "n/a"} -{" "}
              {observation.title ?? observation.summary ?? "no summary"}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
