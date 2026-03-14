import type { SocIocRow } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { Td, Th } from "@/components/ui/table";

function confidenceToSeverity(confidence: string): string {
  return confidence === "derived" ? "LOW" : "INFO";
}

export function IocTable({ rows }: { rows: SocIocRow[] }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Indicator</Th>
          <Th>Type</Th>
          <Th>Confidence</Th>
          <Th>Source</Th>
          <Th>Campaign</Th>
          <Th>Finding</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            <Td className="font-mono text-xs">{row.indicator}</Td>
            <Td>{row.type}</Td>
            <Td>
              <SeverityBadge severity={confidenceToSeverity(row.confidence)} />
            </Td>
            <Td className="text-xs text-muted">{row.source}</Td>
            <Td className="font-mono text-xs">{row.campaignId ?? "-"}</Td>
            <Td className="font-mono text-xs">{row.findingId ?? "-"}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
