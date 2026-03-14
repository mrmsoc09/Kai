import type { InferredApprovalGate } from "@/components/approvals/ApprovalGateTable";

import { EmptyState } from "@/components/data-display/EmptyState";

export function PendingApprovalPanel({ gates }: { gates: InferredApprovalGate[] }) {
  const pending = gates.filter((gate) => gate.status === "PENDING" || gate.status === "DEFERRED");
  if (pending.length === 0) {
    return (
      <EmptyState
        title="No pending approval gates"
        description="No branch-local approval blocks currently require action."
      />
    );
  }
  return (
    <div className="space-y-2">
      {pending.map((gate) => (
        <div key={gate.gate_id} className="rounded-md border border-review/40 bg-review/10 p-2 text-sm text-review">
          <p className="font-mono text-xs">{gate.gate_id}</p>
          <p>Campaign: {gate.campaign_id}</p>
          <p>Phase Job: {gate.phase_job_id ?? "n/a"}</p>
        </div>
      ))}
    </div>
  );
}
