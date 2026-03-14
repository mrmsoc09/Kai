import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { Timestamp } from "@/components/data-display/Timestamp";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

type MonitoredTargetRow = {
  targetId: string;
  programId: string;
  target: string;
  targetType: string;
  monitoringStatus: string;
  monitoringEnabled: boolean;
  safeModeRequired: boolean;
  priorityTier: number;
  readinessStatus: string;
  targetYieldScore: number | null;
  nextAction: string | null;
  lastRunAt: string | null;
  nextRunAt: string | null;
  recentDeltaCount: number;
};

export function MonitoredTargetTable({ rows }: { rows: MonitoredTargetRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No monitored targets"
        description="No targets are available for the selected program filter."
      />
    );
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Target</Th>
          <Th>Type</Th>
          <Th>Status</Th>
          <Th>Readiness</Th>
          <Th>Priority</Th>
          <Th>Yield</Th>
          <Th>Next Action</Th>
          <Th>Recent Deltas</Th>
          <Th>Last Run</Th>
          <Th>Next Run</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.targetId}>
            <Td>
              <div>
                <p className="font-medium">{row.target}</p>
                <p className="font-mono text-xs text-muted">{row.targetId}</p>
              </div>
            </Td>
            <Td>{row.targetType}</Td>
            <Td>
              <div className="space-y-1">
                <StatusBadge status={row.monitoringStatus} />
                <p className="text-xs text-muted">
                  enabled={row.monitoringEnabled ? "true" : "false"} safe_mode={row.safeModeRequired ? "true" : "false"}
                </p>
              </div>
            </Td>
            <Td>
              <StatusBadge status={row.readinessStatus} />
            </Td>
            <Td>{row.priorityTier}</Td>
            <Td>
              <ScoreBadge value={row.targetYieldScore} label="yield" />
            </Td>
            <Td>{row.nextAction ?? "none"}</Td>
            <Td>{row.recentDeltaCount}</Td>
            <Td>
              <Timestamp value={row.lastRunAt} />
            </Td>
            <Td>
              <Timestamp value={row.nextRunAt} />
            </Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
