import Link from "next/link";

import type { CampaignListItem } from "@/lib/types";

import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-display/DataTable";
import { Th, Td } from "@/components/ui/table";
import { formatTimestamp } from "@/lib/utils/formatting";

export function CampaignTable({
  rows,
  onSchedule
}: {
  rows: CampaignListItem[];
  onSchedule: (campaignId: string) => void;
}) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Campaign ID</Th>
          <Th>Status</Th>
          <Th>Program ID</Th>
          <Th>Branches</Th>
          <Th>Phase Jobs</Th>
          <Th>Updated</Th>
          <Th className="w-52">Actions</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td className="font-mono text-xs">{row.id}</Td>
            <Td>
              <StatusBadge status={row.status} />
            </Td>
            <Td className="font-mono text-xs">{row.program_id}</Td>
            <Td>{row.branch_count ?? "-"}</Td>
            <Td>{row.phase_job_count ?? "-"}</Td>
            <Td>{formatTimestamp(row.updated_at ?? row.created_at)}</Td>
            <Td>
              <div className="flex gap-2">
                <Link
                  href={`/mission-control/${row.id}`}
                  className="inline-flex h-8 items-center justify-center rounded-md border border-border px-3 text-xs font-medium text-foreground hover:bg-elevated"
                >
                  Mission Control
                </Link>
                <Button size="sm" variant="secondary" onClick={() => onSchedule(row.id)}>
                  Re-schedule
                </Button>
              </div>
            </Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
