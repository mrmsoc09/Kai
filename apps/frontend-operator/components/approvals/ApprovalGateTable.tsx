import { DataTable } from "@/components/data-display/DataTable";
import { ApprovalStateBadge } from "@/components/status/ApprovalStateBadge";
import { Button } from "@/components/ui/button";
import { Td, Th } from "@/components/ui/table";

export type InferredApprovalGate = {
  gate_id: string;
  campaign_id: string;
  phase_job_id: string | null;
  status: string;
  source_event_type: string;
  happened_at: string | null;
  message: string | null;
};

export function ApprovalGateTable({
  rows,
  onAction
}: {
  rows: InferredApprovalGate[];
  onAction: (gateId: string, status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED") => void;
}) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Gate ID</Th>
          <Th>Campaign</Th>
          <Th>Phase Job</Th>
          <Th>Status</Th>
          <Th>Event</Th>
          <Th>Timestamp</Th>
          <Th className="w-56">Actions</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.gate_id}:${row.happened_at}`}>
            <Td className="font-mono text-xs">{row.gate_id}</Td>
            <Td className="font-mono text-xs">{row.campaign_id}</Td>
            <Td className="font-mono text-xs">{row.phase_job_id ?? "-"}</Td>
            <Td>
              <ApprovalStateBadge status={row.status} />
            </Td>
            <Td className="text-xs">{row.source_event_type}</Td>
            <Td className="text-xs">{row.happened_at ?? "-"}</Td>
            <Td>
              <div className="flex flex-wrap gap-1">
                <Button size="sm" onClick={() => onAction(row.gate_id, "APPROVED")}>
                  Approve
                </Button>
                <Button size="sm" variant="destructive" onClick={() => onAction(row.gate_id, "REJECTED")}>
                  Reject
                </Button>
                <Button size="sm" variant="secondary" onClick={() => onAction(row.gate_id, "DEFERRED")}>
                  Defer
                </Button>
                <Button size="sm" variant="outline" onClick={() => onAction(row.gate_id, "CANCELED")}>
                  Cancel
                </Button>
              </div>
            </Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
