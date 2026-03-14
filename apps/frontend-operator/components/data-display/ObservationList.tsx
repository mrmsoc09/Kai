import type { FindingDiagnosticsResponse } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { Th, Td } from "@/components/ui/table";

export function ObservationList({ finding }: { finding: FindingDiagnosticsResponse }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Observation</Th>
          <Th>Category</Th>
          <Th>Title</Th>
          <Th>Summary</Th>
        </tr>
      </thead>
      <tbody>
        {finding.recent_observations.map((observation) => (
          <tr key={observation.id}>
            <Td className="font-mono text-xs">{observation.id}</Td>
            <Td>{observation.category ?? "-"}</Td>
            <Td>{observation.title ?? "-"}</Td>
            <Td>{observation.summary ?? "-"}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
