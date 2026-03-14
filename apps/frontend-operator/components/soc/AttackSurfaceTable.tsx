import type { SocAssetRow } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Td, Th } from "@/components/ui/table";

export function AttackSurfaceTable({ rows }: { rows: SocAssetRow[] }) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Asset</Th>
          <Th>Program</Th>
          <Th>Campaign</Th>
          <Th>Findings</Th>
          <Th>Evidence</Th>
          <Th>Readiness</Th>
          <Th>Technologies</Th>
          <Th>Source</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            <Td className="font-mono text-xs">{row.asset}</Td>
            <Td>{row.program}</Td>
            <Td className="font-mono text-xs">{row.campaignId}</Td>
            <Td>{row.findings}</Td>
            <Td>{row.evidenceCount}</Td>
            <Td>
              <div className="flex flex-wrap gap-1">
                {row.readinessStates.map((state) => (
                  <StatusBadge key={`${row.key}:${state}`} status={state} />
                ))}
              </div>
            </Td>
            <Td>
              {row.technologies.length > 0 ? (
                <div className="flex flex-wrap gap-1 text-xs">
                  {row.technologies.map((tech) => (
                    <span key={`${row.key}:${tech}`} className="rounded border border-intelligence/40 bg-intelligence/15 px-1.5 py-0.5 text-intelligence">
                      {tech}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="text-xs text-muted">No technology hints</span>
              )}
            </Td>
            <Td className="text-xs text-muted">{row.source.replaceAll("_", " ")}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
