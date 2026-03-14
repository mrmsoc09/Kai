import type { SocReconPhaseRow } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

export function ReconActivityTable({ rows }: { rows: SocReconPhaseRow[] }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Campaign</Th>
          <Th>Phase Job</Th>
          <Th>Phase</Th>
          <Th>Status</Th>
          <Th>Approval Required</Th>
          <Th>Dependency</Th>
          <Th>Worker Task</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.phaseJobId}>
            <Td className="font-mono text-xs">{row.campaignId}</Td>
            <Td className="font-mono text-xs">{row.phaseJobId}</Td>
            <Td>{row.phaseName}</Td>
            <Td>
              <StatusBadge status={row.status} />
            </Td>
            <Td>{row.approvalRequired ? "yes" : "no"}</Td>
            <Td className="font-mono text-xs">{row.dependsOnJobId ?? "-"}</Td>
            <Td className="font-mono text-xs">{row.workerTaskId ?? "-"}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
