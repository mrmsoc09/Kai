import type { FindingDiagnosticsResponse } from "@/lib/types";

import { KeyValueGrid } from "@/components/data-display/KeyValueGrid";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { StatusBadge } from "@/components/status/StatusBadge";

export function FindingSummaryPanel({ finding }: { finding: FindingDiagnosticsResponse }) {
  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border bg-elevated p-3">
        <p className="text-sm font-semibold text-foreground">{finding.finding.title}</p>
        <p className="font-mono text-xs text-muted">{finding.finding.asset}</p>
        <p className="text-xs text-muted">{finding.finding.program}</p>
      </div>
      <KeyValueGrid
        items={[
          { key: "Finding ID", value: <span className="font-mono text-xs">{finding.finding.id}</span> },
          { key: "Status", value: <StatusBadge status={finding.finding.status} /> },
          { key: "Severity", value: <SeverityBadge severity={finding.finding.severity} /> },
          { key: "Evidence", value: finding.counts.evidence },
          { key: "Artifacts", value: finding.counts.artifacts },
          { key: "Drafts", value: finding.counts.submission_drafts }
        ]}
      />
    </div>
  );
}
