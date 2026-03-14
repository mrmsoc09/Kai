import type { FindingDiagnosticsResponse, FindingQueueItem } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

export function ThreatIntelPanel({
  findings,
  findingDiagnostics,
  technologyCounts
}: {
  findings: FindingQueueItem[];
  findingDiagnostics: FindingDiagnosticsResponse[];
  technologyCounts: Array<{ technology: string; count: number }>;
}) {
  return (
    <div className="space-y-4">
      <DataTable>
        <thead>
          <tr>
            <Th>Finding</Th>
            <Th>Program / Asset</Th>
            <Th>Status</Th>
            <Th>Readiness</Th>
            <Th>Evidence</Th>
          </tr>
        </thead>
        <tbody>
          {findings.slice(0, 25).map((finding) => (
            <tr key={finding.finding_id}>
              <Td className="text-sm">{finding.title}</Td>
              <Td>
                <p>{finding.program}</p>
                <p className="font-mono text-xs text-muted">{finding.asset}</p>
              </Td>
              <Td>
                <StatusBadge status={finding.finding_status} />
              </Td>
              <Td>
                <StatusBadge status={finding.readiness_status} />
              </Td>
              <Td>{finding.evidence_count}</Td>
            </tr>
          ))}
        </tbody>
      </DataTable>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-border bg-panel p-3">
          <h3 className="text-sm font-semibold text-foreground">Observed Technologies (Derived)</h3>
          {technologyCounts.length === 0 ? (
            <p className="mt-2 text-xs text-muted">No technology hints observed in recent findings.</p>
          ) : (
            <ul className="mt-2 space-y-1 text-sm">
              {technologyCounts.slice(0, 12).map((item) => (
                <li key={item.technology} className="flex items-center justify-between">
                  <span>{item.technology}</span>
                  <span className="rounded border border-intelligence/40 bg-intelligence/15 px-2 py-0.5 text-xs text-intelligence">
                    {item.count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-md border border-border bg-panel p-3">
          <h3 className="text-sm font-semibold text-foreground">Taxonomy Fields</h3>
          {findingDiagnostics.length === 0 ? (
            <EmptyState
              title="No taxonomy data"
              description="No finding diagnostics loaded for taxonomy extraction."
            />
          ) : (
            <p className="mt-2 text-xs text-muted">
              CWE/CVE-specific feed integration is pending. This panel currently reflects canonical finding and
              observation metadata only.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
