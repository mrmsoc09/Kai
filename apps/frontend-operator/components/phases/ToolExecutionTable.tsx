import type { CampaignDiagnosticsResponse } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { Td, Th } from "@/components/ui/table";

export function ToolExecutionTable({ diagnostics }: { diagnostics: CampaignDiagnosticsResponse }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Metric</Th>
          <Th>Value</Th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <Td>Tool Executions</Td>
          <Td>{diagnostics.counts.tool_executions}</Td>
        </tr>
        <tr>
          <Td>Artifacts</Td>
          <Td>{diagnostics.counts.artifacts}</Td>
        </tr>
        <tr>
          <Td>Observations</Td>
          <Td>{diagnostics.counts.observations}</Td>
        </tr>
      </tbody>
    </DataTable>
  );
}
