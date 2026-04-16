import type { InferredApprovalGate } from "@/lib/types";

import { KeyValueGrid } from "@/components/data-display/KeyValueGrid";

export function ApprovalGateSummary({ gates }: { gates: InferredApprovalGate[] }) {
  const pending = gates.filter((gate) => gate.status === "PENDING" || gate.status === "DEFERRED").length;
  const terminal = gates.length - pending;
  const missingIntention = gates.filter((gate) => gate.intention.trim().length === 0).length;
  return (
    <KeyValueGrid
      items={[
        { key: "Total Gates", value: gates.length },
        { key: "Pending/Deferred", value: pending },
        { key: "Terminal", value: terminal },
        { key: "Missing Intention", value: missingIntention }
      ]}
    />
  );
}
