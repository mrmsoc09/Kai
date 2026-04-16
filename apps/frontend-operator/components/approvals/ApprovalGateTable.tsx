import { IntentionDisplayCard } from "@/components/cockpit/IntentionDisplayCard";
import type { InferredApprovalGate } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { ApprovalStateBadge } from "@/components/status/ApprovalStateBadge";
import { Button } from "@/components/ui/button";
import { Td, Th } from "@/components/ui/table";

export function ApprovalGateTable({
  rows,
  selectedGateId,
  onSelect,
  onAction
}: {
  rows: InferredApprovalGate[];
  selectedGateId?: string | null;
  onSelect?: (gate: InferredApprovalGate) => void;
  onAction: (gateId: string, status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED") => void;
}) {
  return (
    <DataTable>
      <thead>
        <tr>
          <Th>Request</Th>
          <Th>Mission / Phase</Th>
          <Th>Governance Context</Th>
          <Th>Intention / Safety</Th>
          <Th>Status / Reviewer</Th>
          <Th>Timestamps</Th>
          <Th className="w-56">Actions</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const isSelected = row.gate_id === selectedGateId;
          return (
            <tr key={`${row.gate_id}:${row.happened_at}`} className={isSelected ? "bg-active/5" : undefined}>
              <Td>
                {onSelect ? (
                  <button
                    type="button"
                    className="text-left"
                    onClick={() => onSelect(row)}
                  >
                    <p className="text-sm font-medium text-active hover:underline">{row.request_title}</p>
                    <p className="text-xs text-muted">action: {row.requested_action}</p>
                    <p className="font-mono text-xs text-muted">{row.gate_id}</p>
                  </button>
                ) : (
                  <>
                    <p className="text-sm font-medium text-foreground">{row.request_title}</p>
                    <p className="text-xs text-muted">action: {row.requested_action}</p>
                    <p className="font-mono text-xs text-muted">{row.gate_id}</p>
                  </>
                )}
              </Td>
              <Td>
                <p className="font-mono text-xs text-foreground">{row.campaign_id}</p>
                <p className="text-xs text-muted">phase: {row.phase_name ?? row.phase_job_id ?? "n/a"}</p>
                <p className="text-xs text-muted">agent: {row.requesting_agent}</p>
              </Td>
              <Td className="text-xs">
                <p>scope: {row.scope_target}</p>
                <p>risk: {row.risk_band}</p>
                <p>evidence: {row.evidence_attached}</p>
                <p>justification: {row.justification}</p>
                <p>impact: {row.expected_impact}</p>
              </Td>
              <Td>
                <IntentionDisplayCard
                  intention={row.intention}
                  justification={row.justification}
                  expectedImpact={row.expected_impact}
                  safetyConstraints={row.safety_constraints}
                />
              </Td>
              <Td className="space-y-2 text-xs">
                <ApprovalStateBadge status={row.status} />
                <p>reviewer notes: {row.reviewer_notes}</p>
                <p>event: {row.source_event_type}</p>
              </Td>
              <Td className="space-y-1 text-xs">
                <p>requested: {row.requested_at ?? "n/a"}</p>
                <p>decided: {row.decided_at ?? "n/a"}</p>
                <p>updated: {row.happened_at ?? "n/a"}</p>
              </Td>
              <Td>
                <div className="flex flex-wrap gap-1">
                  <Button
                    size="sm"
                    disabled={row.intention.trim().length === 0}
                    title={row.intention.trim().length === 0 ? "Cannot approve: intention is missing" : undefined}
                    onClick={() => onAction(row.gate_id, "APPROVED")}
                  >
                    Approve
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => onAction(row.gate_id, "REJECTED")}>
                    Reject
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => onAction(row.gate_id, "DEFERRED")}>
                    Defer
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => onAction(row.gate_id, "CANCELED")}>
                    Cancel
                  </Button>
                  {onSelect ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onSelect(row)}
                      className={isSelected ? "border-active/50 text-active" : undefined}
                    >
                      {isSelected ? "Selected" : "Detail"}
                    </Button>
                  ) : null}
                </div>
              </Td>
            </tr>
          );
        })}
      </tbody>
    </DataTable>
  );
}
