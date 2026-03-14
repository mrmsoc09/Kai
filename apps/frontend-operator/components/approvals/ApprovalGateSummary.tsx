import type { InferredApprovalGate } from "@/components/approvals/ApprovalGateTable";

import { KeyValueGrid } from "@/components/data-display/KeyValueGrid";

export function ApprovalGateSummary({ gates }: { gates: InferredApprovalGate[] }) {
  const pending = gates.filter((gate) => gate.status === "PENDING" || gate.status === "DEFERRED").length;
  const terminal = gates.length - pending;
  return (
    <KeyValueGrid
      items={[
        { key: "Total Gates", value: gates.length },
        { key: "Pending/Deferred", value: pending },
        { key: "Terminal", value: terminal }
      ]}
    />
  );
}
