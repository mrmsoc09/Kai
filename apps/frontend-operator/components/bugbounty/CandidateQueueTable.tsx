import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Td, Th } from "@/components/ui/table";
import type { CandidateQueueStatus } from "@/lib/types";

type CandidateQueueRow = {
  id: string;
  vulnerability_type: string | null;
  affected_asset: string | null;
  affected_endpoint: string | null;
  confidence_score: number | null;
  reportability_score: number | null;
  duplicate_risk_score?: number | null;
  evidence_completeness_score?: number | null;
  evidence_readiness_state?: string | null;
  missing_evidence_fields?: string[];
  status: string | null;
  severity_hint: string | null;
  artifact_ref: string | null;
  recommended_workflow?: string | null;
  recommended_action?: string | null;
  ready_for_report?: boolean;
};

export function CandidateQueueTable({
  rows,
  onStatusChange,
  onGenerateDraft,
  actionsDisabled = false,
  showActions = true
}: {
  rows: CandidateQueueRow[];
  onStatusChange?: (queueItemId: string, status: CandidateQueueStatus) => void;
  onGenerateDraft?: (queueItemId: string) => void;
  actionsDisabled?: boolean;
  showActions?: boolean;
}) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No candidate findings"
        description="No candidate records are available for the selected filters."
      />
    );
  }

  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Finding Candidate</Th>
          <Th>Status</Th>
          <Th>Severity</Th>
          <Th>Confidence</Th>
          <Th>Reportability</Th>
          <Th>Duplicate Risk</Th>
          <Th>Evidence</Th>
          <Th>Ready</Th>
          <Th>Recommendation</Th>
          <Th>Artifacts</Th>
          {showActions ? <Th>Actions</Th> : null}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <Td>
              <p className="font-medium">{row.vulnerability_type ?? "Unknown vulnerability type"}</p>
              <p className="text-xs text-muted">{row.affected_asset ?? "Unknown asset"}</p>
              {row.affected_endpoint ? <p className="font-mono text-xs text-muted">{row.affected_endpoint}</p> : null}
            </Td>
            <Td>
              <StatusBadge status={row.status ?? "UNKNOWN"} />
            </Td>
            <Td>
              <SeverityBadge severity={row.severity_hint} />
            </Td>
            <Td>
              <ScoreBadge value={row.confidence_score} label="confidence" />
            </Td>
            <Td>
              <ScoreBadge value={row.reportability_score} label="reportability" />
            </Td>
            <Td>
              <ScoreBadge value={row.duplicate_risk_score} label="duplicate" />
            </Td>
            <Td>
              <div className="space-y-1">
                <ScoreBadge value={row.evidence_completeness_score} label="evidence" />
                <StatusBadge status={row.evidence_readiness_state} className="text-[10px]" />
                {row.missing_evidence_fields && row.missing_evidence_fields.length > 0 ? (
                  <p className="max-w-[180px] text-[10px] text-review">
                    missing: {row.missing_evidence_fields.join(", ")}
                  </p>
                ) : null}
              </div>
            </Td>
            <Td>
              <StatusBadge status={row.ready_for_report ? "READY_FOR_SUBMISSION" : "NEEDS_REVIEW"} />
            </Td>
            <Td className="max-w-[280px] text-xs text-muted">
              {row.recommended_workflow || row.recommended_action ? (
                <>
                  <p>{row.recommended_workflow ?? "workflow: none"}</p>
                  <p>{row.recommended_action ?? "action: none"}</p>
                </>
              ) : (
                <p className="text-xs text-muted">No recommendation yet</p>
              )}
            </Td>
            <Td className="font-mono text-xs">{row.artifact_ref ?? "n/a"}</Td>
            {showActions ? (
              <Td>
                <div className="flex flex-wrap gap-1">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => onStatusChange?.(row.id, "triaged")}
                    disabled={actionsDisabled}
                    type="button"
                  >
                    Triaged
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => onStatusChange?.(row.id, "needs_manual_validation")}
                    disabled={actionsDisabled}
                    type="button"
                  >
                    Needs Manual
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => onStatusChange?.(row.id, "ready_for_report")}
                    disabled={actionsDisabled}
                    type="button"
                  >
                    Ready Report
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => onGenerateDraft?.(row.id)}
                    disabled={actionsDisabled}
                    type="button"
                  >
                    Draft
                  </Button>
                </div>
              </Td>
            ) : null}
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
