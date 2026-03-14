import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";
import type { AgentRegistryRecord } from "@/lib/types";

export function AgentRegistryTable({ rows }: { rows: AgentRegistryRecord[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No agents registered"
        description="Run a registry sync to seed the first-wave specialized agents."
      />
    );
  }
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Agent</Th>
          <Th>Category</Th>
          <Th>Model</Th>
          <Th>Threshold</Th>
          <Th>Escalation</Th>
          <Th>Status</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>
              <p className="font-medium">{row.agent_name}</p>
              <p className="font-mono text-xs text-muted">{row.agent_id}</p>
            </Td>
            <Td>{row.category}</Td>
            <Td>
              <p>{row.model_preference}</p>
              <p className="text-xs text-muted">{row.model_runtime}</p>
            </Td>
            <Td>{row.confidence_threshold.toFixed(2)}</Td>
            <Td>{row.escalation_agent_id ?? "n/a"}</Td>
            <Td>
              <StatusBadge status={row.enabled ? "READY" : "BLOCKED"} />
            </Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
