import Link from "next/link";

import type { FindingQueueItem } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { EvidenceStateBadge } from "@/components/status/EvidenceStateBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

export function FindingsQueueTable({ rows }: { rows: FindingQueueItem[] }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Finding</Th>
          <Th>Status</Th>
          <Th>Readiness</Th>
          <Th>Program / Asset</Th>
          <Th>Evidence</Th>
          <Th>Campaign</Th>
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
            <Td>
              <StatusBadge status={row.finding_status} />
            </Td>
            <Td>
              <EvidenceStateBadge state={row.readiness_status} />
            </Td>
            <Td>
              <p>{row.program}</p>
              <p className="font-mono text-xs text-muted">{row.asset}</p>
            </Td>
            <Td>{row.evidence_count}</Td>
            <Td className="font-mono text-xs">{row.campaign_id}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
