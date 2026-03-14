import type { DiagnosticsSummaryResponse } from "@/lib/types";

import { MetricsGrid } from "@/components/diagnostics/MetricsGrid";

const bucketOrder = [
  "campaigns",
  "branches",
  "phase_jobs",
  "approval_gates",
  "tool_executions",
  "findings",
  "submission_drafts"
] as const;

export function DiagnosticsSummaryCards({ summary }: { summary: DiagnosticsSummaryResponse }) {
  return (
    <MetricsGrid
      metrics={bucketOrder.map((key) => ({
        title: key.replaceAll("_", " "),
        total: summary[key].total,
        breakdown: summary[key].by_status
      }))}
    />
  );
}
