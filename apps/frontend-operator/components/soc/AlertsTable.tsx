import type { SocAlert } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { Td, Th } from "@/components/ui/table";

export function AlertsTable({ alerts }: { alerts: SocAlert[] }) {
  if (alerts.length === 0) {
    return (
      <EmptyState
        title="No active alerts"
        description="No high-priority alerts were derived from canonical campaign and finding state."
      />
    );
  }
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Severity</Th>
          <Th>Category</Th>
          <Th>Title</Th>
          <Th>Description</Th>
          <Th>Campaign</Th>
          <Th>Finding</Th>
          <Th>Time</Th>
        </tr>
      </thead>
      <tbody>
        {alerts.map((alert) => (
          <tr key={alert.id}>
            <Td>
              <SeverityBadge severity={alert.severity} />
            </Td>
            <Td>{alert.category}</Td>
            <Td>{alert.title}</Td>
            <Td className="text-sm">{alert.description}</Td>
            <Td className="font-mono text-xs">{alert.campaignId ?? "-"}</Td>
            <Td className="font-mono text-xs">{alert.findingId ?? "-"}</Td>
            <Td className="text-xs text-muted">{alert.happenedAt ?? "-"}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
