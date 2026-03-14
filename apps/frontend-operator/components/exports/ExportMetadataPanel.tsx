import type { SubmissionExportResponse } from "@/lib/types";

import { KeyValueGrid } from "@/components/data-display/KeyValueGrid";
import { ExportReadinessBadge } from "@/components/status/ExportReadinessBadge";

export function ExportMetadataPanel({ result }: { result: SubmissionExportResponse }) {
  return (
    <KeyValueGrid
      items={[
        { key: "Provider", value: result.provider },
        { key: "State", value: <ExportReadinessBadge state={result.state} /> },
        { key: "Ready", value: result.ready ? "yes" : "no" },
        { key: "Stored", value: result.stored ? "yes" : "no" },
        { key: "Exported At", value: result.exported_at ?? "n/a" },
        { key: "Submission Draft", value: result.submission_draft_id }
      ]}
    />
  );
}
