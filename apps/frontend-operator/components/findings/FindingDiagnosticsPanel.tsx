import type { FindingDiagnosticsResponse } from "@/lib/types";

import { KeyValueGrid } from "@/components/data-display/KeyValueGrid";

export function FindingDiagnosticsPanel({ finding }: { finding: FindingDiagnosticsResponse }) {
  return (
    <KeyValueGrid
      items={[
        { key: "Observations", value: finding.counts.observations },
        { key: "Audit Events", value: finding.counts.audit_events },
        { key: "Submission Drafts", value: finding.counts.submission_drafts },
        { key: "Evidence", value: finding.counts.evidence }
      ]}
    />
  );
}
