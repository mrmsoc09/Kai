import type { CampaignStatusResponse } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

export function BranchList({ branches }: { branches: CampaignStatusResponse["branches"] }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Branch ID</Th>
          <Th>Branch Key</Th>
          <Th>Status</Th>
          <Th>Depends On Branch</Th>
        </tr>
      </thead>
      <tbody>
        {branches.map((branch) => (
          <tr key={branch.id}>
            <Td className="font-mono text-xs">{branch.id}</Td>
            <Td>{branch.branch_key}</Td>
            <Td>
              <StatusBadge status={branch.status} />
            </Td>
            <Td className="font-mono text-xs">{branch.depends_on_branch_id ?? "-"}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
