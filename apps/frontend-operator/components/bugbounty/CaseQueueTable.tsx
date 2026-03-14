import Link from "next/link";

import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Td, Th } from "@/components/ui/table";
import { formatTimestamp } from "@/lib/utils/formatting";

type CaseRow = {
  id: string;
  title: string | null;
  summary: string | null;
  priority: string | null;
  status: string | null;
  owner: string | null;
  last_transition_at: string | null;
};

export function CaseQueueTable({
  rows,
  onStatusChange,
  actionsDisabled = false
}: {
  rows: CaseRow[];
  onStatusChange?: (caseId: string, status: string) => void;
  actionsDisabled?: boolean;
}) {
  if (rows.length === 0) {
    return <EmptyState title="No cases" description="No case records match the current filters." />;
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Case</Th>
          <Th>Priority</Th>
          <Th>Status</Th>
          <Th>Owner</Th>
          <Th>Last Transition</Th>
          <Th>Actions</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>
              <Link href={`/cases/${row.id}`} className="font-medium text-active hover:underline">
                {row.title ?? "Untitled case"}
              </Link>
              <p className="max-w-[420px] text-xs text-muted">{row.summary ?? "No case summary provided."}</p>
              <p className="font-mono text-[10px] text-muted">{row.id}</p>
            </Td>
            <Td>
              <StatusBadge status={row.priority ?? "UNKNOWN"} />
            </Td>
            <Td>
              <StatusBadge status={row.status ?? "UNKNOWN"} />
            </Td>
            <Td>{row.owner ?? "unassigned"}</Td>
            <Td className="text-xs text-muted">{formatTimestamp(row.last_transition_at)}</Td>
            <Td>
              <div className="flex flex-wrap gap-1">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => onStatusChange?.(row.id, "acknowledged")}
                  disabled={actionsDisabled}
                  type="button"
                >
                  Ack
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => onStatusChange?.(row.id, "triaging")}
                  disabled={actionsDisabled}
                  type="button"
                >
                  Triaging
                </Button>
                <Button
                  size="sm"
                  onClick={() => onStatusChange?.(row.id, "ready_for_report")}
                  disabled={actionsDisabled}
                  type="button"
                >
                  Ready Report
                </Button>
              </div>
            </Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
