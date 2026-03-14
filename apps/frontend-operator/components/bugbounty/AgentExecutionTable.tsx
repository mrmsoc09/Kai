import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";
import { formatTimestamp } from "@/lib/utils/formatting";
import type { AgentExecutionRecord } from "@/lib/types";

export function AgentExecutionTable({ rows }: { rows: AgentExecutionRecord[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No agent executions"
        description="Run an agent to generate execution history and confidence telemetry."
      />
    );
  }
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Started</Th>
          <Th>Agent</Th>
          <Th>Status</Th>
          <Th>Confidence</Th>
          <Th>Model</Th>
          <Th>Duration</Th>
          <Th>Escalation</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>{formatTimestamp(row.started_at)}</Td>
            <Td>
              <p className="font-medium">{row.agent_id}</p>
              <p className="font-mono text-xs text-muted">{row.id}</p>
            </Td>
            <Td>
              <StatusBadge status={row.execution_status} />
            </Td>
            <Td>
              <ScoreBadge value={row.confidence} label="confidence" />
            </Td>
            <Td>
              <p>{row.model_used}</p>
              <p className="text-xs text-muted">{row.routing_policy}</p>
            </Td>
            <Td>{row.duration_ms ?? 0} ms</Td>
            <Td>{row.escalation_taken ? row.escalation_agent_id ?? "yes" : "no"}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
