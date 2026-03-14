import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Td, Th } from "@/components/ui/table";
import { formatTimestamp } from "@/lib/utils/formatting";

type AlertRow = {
  id: string;
  alert_type: string | null;
  severity: string | null;
  urgency: string | null;
  status: string | null;
  summary: string | null;
  reasoning_summary: string | null;
  analyst_queue_item_id: string | null;
  prediction_record_id: string | null;
  recommendation_record_id: string | null;
  occurrence_count: number | null;
  last_seen_at: string | null;
};

export function AlertTable({
  rows,
  onAcknowledge,
  onResolve,
  onCreateCase,
  actionsDisabled = false
}: {
  rows: AlertRow[];
  onAcknowledge?: (alertId: string) => void;
  onResolve?: (alertId: string) => void;
  onCreateCase?: (alertId: string) => void;
  actionsDisabled?: boolean;
}) {
  if (rows.length === 0) {
    return <EmptyState title="No alerts" description="No alerts match the current filters." />;
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Alert</Th>
          <Th>Severity</Th>
          <Th>Status</Th>
          <Th>Urgency</Th>
          <Th>Linked Records</Th>
          <Th>Occurrences</Th>
          <Th>Last Seen</Th>
          <Th>Actions</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>
              <p className="font-medium">{row.alert_type ?? "Unknown alert type"}</p>
              <p className="max-w-[360px] text-xs text-muted">{row.summary ?? "No alert summary provided."}</p>
              {row.reasoning_summary ? (
                <p className="max-w-[360px] text-xs text-muted">{row.reasoning_summary}</p>
              ) : null}
            </Td>
            <Td>
              <SeverityBadge severity={row.severity ?? "UNKNOWN"} />
            </Td>
            <Td>
              <StatusBadge status={row.status ?? "UNKNOWN"} />
            </Td>
            <Td>
              <StatusBadge status={row.urgency ?? "UNKNOWN"} className="text-[10px]" />
            </Td>
            <Td className="font-mono text-xs">
              <p>{row.analyst_queue_item_id ? `queue:${row.analyst_queue_item_id}` : "queue:n/a"}</p>
              <p>{row.prediction_record_id ? `pred:${row.prediction_record_id}` : "pred:n/a"}</p>
              <p>{row.recommendation_record_id ? `rec:${row.recommendation_record_id}` : "rec:n/a"}</p>
            </Td>
            <Td>{row.occurrence_count ?? 0}</Td>
            <Td className="text-xs text-muted">{formatTimestamp(row.last_seen_at)}</Td>
            <Td>
              <div className="flex flex-wrap gap-1">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={actionsDisabled || row.status === "RESOLVED"}
                  onClick={() => onAcknowledge?.(row.id)}
                  type="button"
                >
                  Ack
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={actionsDisabled || row.status === "RESOLVED"}
                  onClick={() => onResolve?.(row.id)}
                  type="button"
                >
                  Resolve
                </Button>
                <Button
                  size="sm"
                  disabled={actionsDisabled}
                  onClick={() => onCreateCase?.(row.id)}
                  type="button"
                >
                  Create Case
                </Button>
              </div>
            </Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
