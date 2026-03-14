import type { SocPlaybookRow } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

export function PlaybookCatalog({ rows }: { rows: SocPlaybookRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No playbooks derived"
        description="Track campaigns to derive phase playbooks from canonical execution data."
      />
    );
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Playbook / Phase</Th>
          <Th>Campaigns</Th>
          <Th>Pending</Th>
          <Th>Running</Th>
          <Th>Blocked</Th>
          <Th>Completed</Th>
          <Th>Backend Support</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            <Td>{row.phaseName}</Td>
            <Td>{row.campaigns}</Td>
            <Td>{row.pending}</Td>
            <Td>{row.running}</Td>
            <Td>{row.blocked}</Td>
            <Td>{row.completed}</Td>
            <Td>
              <StatusBadge status={row.support === "backed" ? "READY" : "BLOCKED"} />
            </Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
