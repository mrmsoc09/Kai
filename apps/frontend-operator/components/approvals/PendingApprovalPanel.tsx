import Link from "next/link";

import type { InferredApprovalGate } from "@/lib/types";

import { EmptyState } from "@/components/data-display/EmptyState";

export function PendingApprovalPanel({
  gates,
  showApprovalLink = false
}: {
  gates: InferredApprovalGate[];
  showApprovalLink?: boolean;
}) {
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
          <p className="font-medium">{gate.request_title}</p>
          <p>Mission: {gate.campaign_id}</p>
          <p>Phase: {gate.phase_name ?? gate.phase_job_id ?? "n/a"}</p>
          <p>
            Intention:{" "}
            {gate.intention ? (
              <span className="text-foreground">{gate.intention}</span>
            ) : (
              <span className="font-semibold text-danger">missing — do not approve</span>
            )}
          </p>
        </div>
      ))}
      {showApprovalLink ? (
        <div className="pt-1 text-xs">
          <Link href="/approvals" className="text-active hover:underline">
            Open Approval Queue →
          </Link>
        </div>
      ) : null}
    </div>
  );
}
