import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { Td, Th } from "@/components/ui/table";

type PredictionRow = {
  id: string;
  program_id: string | null;
  scope_target_id: string | null;
  predicted_vulnerability_type: string | null;
  confidence_score: number | null;
  reportability_score: number | null;
  duplicate_risk_score: number | null;
  evidence_completeness_score: number | null;
  opportunity_score: number | null;
  recommended_next_workflow: string | null;
  recommended_follow_up_action: string | null;
  reasoning_summary: string | null;
};

export function PredictionTable({ rows }: { rows: PredictionRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No vulnerability predictions"
        description="Run a prediction cycle or wait for recurring inference jobs to populate this table."
      />
    );
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Prediction</Th>
          <Th>Scores</Th>
          <Th>Next Workflow</Th>
          <Th>Follow-up Action</Th>
          <Th>Reasoning</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>
              <p className="font-medium">{row.predicted_vulnerability_type ?? "Unknown prediction"}</p>
              <p className="font-mono text-xs text-muted">program={row.program_id ?? "unknown"}</p>
              {row.scope_target_id ? <p className="font-mono text-xs text-muted">target={row.scope_target_id}</p> : null}
            </Td>
            <Td>
              <div className="flex flex-wrap gap-1">
                <ScoreBadge value={row.confidence_score} label="confidence" />
                <ScoreBadge value={row.reportability_score} label="reportability" />
                <ScoreBadge value={row.duplicate_risk_score} label="duplicate" />
                <ScoreBadge value={row.evidence_completeness_score} label="evidence" />
                <ScoreBadge value={row.opportunity_score} label="opportunity" />
              </div>
            </Td>
            <Td>{row.recommended_next_workflow ?? "n/a"}</Td>
            <Td>{row.recommended_follow_up_action ?? "n/a"}</Td>
            <Td className="max-w-[360px] text-xs text-muted">{row.reasoning_summary ?? "No reasoning summary provided."}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
