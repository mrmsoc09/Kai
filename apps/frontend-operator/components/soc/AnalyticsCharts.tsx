import type { DiagnosticsSummaryResponse } from "@/lib/types";

function ChartBar({ label, value, max }: { label: string; value: number; max: number }) {
  const ratio = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{label}</span>
        <span>{value}</span>
      </div>
      <div className="h-2 rounded bg-elevated">
        <div className="h-2 rounded bg-active" style={{ width: `${Math.max(2, ratio)}%` }} />
      </div>
    </div>
  );
}

export function AnalyticsCharts({ summary }: { summary: DiagnosticsSummaryResponse }) {
  const rows = [
    { label: "Campaigns", value: summary.campaigns.total },
    { label: "Branches", value: summary.branches.total },
    { label: "Phase Jobs", value: summary.phase_jobs.total },
    { label: "Tool Executions", value: summary.tool_executions.total },
    { label: "Approval Gates", value: summary.approval_gates.total },
    { label: "Findings", value: summary.findings.total },
    { label: "Submission Drafts", value: summary.submission_drafts.total }
  ];
  const max = Math.max(...rows.map((row) => row.value), 1);

  return (
    <div className="rounded-md border border-border bg-panel p-3">
      <h3 className="text-sm font-semibold text-foreground">Entity Volume Snapshot</h3>
      <div className="mt-3 space-y-2">
        {rows.map((row) => (
          <ChartBar key={row.label} label={row.label} value={row.value} max={max} />
        ))}
      </div>
    </div>
  );
}
