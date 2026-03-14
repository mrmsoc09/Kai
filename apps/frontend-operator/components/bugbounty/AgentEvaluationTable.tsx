import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";
import { formatTimestamp } from "@/lib/utils/formatting";
import type { AgentEvaluationRecord } from "@/lib/types";

export function AgentEvaluationTable({ rows }: { rows: AgentEvaluationRecord[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No agent evaluations"
        description="Run an evaluation to benchmark confidence and success rates for specialized agents."
      />
    );
  }
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Executed</Th>
          <Th>Agent</Th>
          <Th>Benchmark</Th>
          <Th>Status</Th>
          <Th>Success</Th>
          <Th>Fixtures</Th>
          <Th>Latency</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>{formatTimestamp(row.executed_at)}</Td>
            <Td>{row.agent_id}</Td>
            <Td>{row.benchmark_name}</Td>
            <Td>
              <StatusBadge status={row.status === "PASSED" ? "COMPLETED" : row.status} />
            </Td>
            <Td>
              <ScoreBadge value={row.success_rate} label="success" />
            </Td>
            <Td>
              {row.passed_count}/{row.fixture_count}
            </Td>
            <Td>{row.avg_latency_ms ?? 0} ms</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
