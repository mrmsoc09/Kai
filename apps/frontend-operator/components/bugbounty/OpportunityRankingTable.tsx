import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { Td, Th } from "@/components/ui/table";

type OpportunityRankingRow = {
  id: string;
  programId: string;
  scopeTargetId: string | null;
  subjectType: string | null;
  subjectKey: string | null;
  selectionScore: number | null;
  priorityRank: number | null;
  confidenceScore: number | null;
  duplicateRiskScore: number | null;
  evidenceCompletenessScore: number | null;
  recommendedWorkflow: string | null;
  recommendedAction: string | null;
  reasoningSummary: string | null;
};

export function OpportunityRankingTable({ rows }: { rows: OpportunityRankingRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No opportunity rankings"
        description="Run Phase 7 prediction to generate opportunity selection output."
      />
    );
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Rank</Th>
          <Th>Subject</Th>
          <Th>Opportunity</Th>
          <Th>Confidence</Th>
          <Th>Dup Risk</Th>
          <Th>Evidence</Th>
          <Th>Recommended Workflow</Th>
          <Th>Follow-up Action</Th>
          <Th>Reasoning</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>{row.priorityRank ?? "-"}</Td>
            <Td>
              <p className="font-medium">{row.subjectType ?? "UNKNOWN"}:{row.subjectKey ?? "unknown-subject"}</p>
              <p className="font-mono text-xs text-muted">program={row.programId}</p>
              {row.scopeTargetId ? <p className="font-mono text-xs text-muted">target={row.scopeTargetId}</p> : null}
            </Td>
            <Td>
              <ScoreBadge value={row.selectionScore} label="opportunity" />
            </Td>
            <Td>
              <ScoreBadge value={row.confidenceScore} label="confidence" />
            </Td>
            <Td>
              <ScoreBadge value={row.duplicateRiskScore} label="duplicate" />
            </Td>
            <Td>
              <ScoreBadge value={row.evidenceCompletenessScore} label="evidence" />
            </Td>
            <Td>{row.recommendedWorkflow ?? "n/a"}</Td>
            <Td>{row.recommendedAction ?? "n/a"}</Td>
            <Td className="max-w-[360px] text-xs text-muted">{row.reasoningSummary ?? "No reasoning summary provided."}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
