import Link from "next/link";

import type { FindingQueueItem } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

export function EvidenceRepositoryTable({
  rows,
  syntheticLabel = "Derived from diagnostics aggregates"
}: {
  rows: FindingQueueItem[];
  syntheticLabel?: string;
}) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Finding</Th>
          <Th>Campaign</Th>
          <Th>Asset</Th>
          <Th>Evidence Count</Th>
          <Th>Draft Readiness</Th>
          <Th>Evidence Source</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.finding_id}>
            <Td>
              <Link href={`/findings/${row.finding_id}`} className="font-medium text-finding hover:underline">
                {row.title}
              </Link>
              <p className="font-mono text-xs text-muted">{row.finding_id}</p>
            </Td>
            <Td className="font-mono text-xs">{row.campaign_id}</Td>
            <Td className="font-mono text-xs">{row.asset}</Td>
            <Td>{row.evidence_count}</Td>
            <Td>
              <StatusBadge status={row.readiness_status} />
            </Td>
            <Td className="text-xs text-muted">{syntheticLabel}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
