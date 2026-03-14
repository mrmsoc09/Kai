import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

type ProgramTableRow = {
  programId: string;
  name: string | null;
  platform: string | null;
  status: string | null;
  monitoredTargets: number;
  activeSchedules: number;
  candidateFindings: number;
  yieldScore: number | null;
  opportunityScore: number | null;
};

export function ProgramTable({ rows }: { rows: ProgramTableRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No bug bounty programs"
        description="Import or create program opportunities to begin monitored operations."
      />
    );
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Program</Th>
          <Th>Status</Th>
          <Th>Platform</Th>
          <Th>Targets</Th>
          <Th>Active Schedules</Th>
          <Th>Candidates</Th>
          <Th>Yield</Th>
          <Th>Opportunity</Th>
          <Th>Program ID</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.programId}>
            <Td>{row.name ?? "Unnamed Program"}</Td>
            <Td>
              <StatusBadge status={row.status ?? "UNKNOWN"} />
            </Td>
            <Td>{row.platform ?? "manual"}</Td>
            <Td>{row.monitoredTargets}</Td>
            <Td>{row.activeSchedules}</Td>
            <Td>{row.candidateFindings}</Td>
            <Td>
              <ScoreBadge value={row.yieldScore} label="yield" />
            </Td>
            <Td>
              <ScoreBadge value={row.opportunityScore} label="opportunity" />
            </Td>
            <Td className="font-mono text-xs">{row.programId}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
