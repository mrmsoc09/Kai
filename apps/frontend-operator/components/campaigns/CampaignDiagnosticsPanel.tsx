import type { CampaignDiagnosticsResponse } from "@/lib/types";

import { KeyValueGrid } from "@/components/data-display/KeyValueGrid";

export function CampaignDiagnosticsPanel({ diagnostics }: { diagnostics: CampaignDiagnosticsResponse }) {
  return (
    <KeyValueGrid
      items={[
        { key: "Tool Executions", value: diagnostics.counts.tool_executions },
        { key: "Approval Gates", value: diagnostics.counts.approval_gates },
        { key: "Artifacts", value: diagnostics.counts.artifacts },
        { key: "Observations", value: diagnostics.counts.observations },
        { key: "Submission Drafts", value: diagnostics.counts.submission_drafts },
        { key: "Blocked Reason", value: diagnostics.campaign.blocked_reason ?? "n/a" }
      ]}
    />
  );
}
