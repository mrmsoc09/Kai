"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { decideApprovalGate } from "@/lib/api/approvals";
import { useApprovalQueue } from "@/hooks/useApprovalQueue";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";
import { queryKeys } from "@/lib/query-keys";
import { isUuid } from "@/lib/utils";
import { gateIsPending } from "@/lib/approval-gates";
import { APPROVAL_CONSOLE_ACTOR } from "@/lib/operator-identity";
import type { InferredApprovalGate } from "@/lib/types";

import { ApprovalDecisionDialog } from "@/components/approvals/ApprovalDecisionDialog";
import { ApprovalDetailPanel } from "@/components/approvals/ApprovalDetailPanel";
import { ApprovalGateSummary } from "@/components/approvals/ApprovalGateSummary";
import { ApprovalGateTable } from "@/components/approvals/ApprovalGateTable";
import { PendingApprovalPanel } from "@/components/approvals/PendingApprovalPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const { trackedCampaignIds, addCampaignId } = useTrackedCampaignIds();
  const [campaignInput, setCampaignInput] = useState("");
  const [showOnlyPending, setShowOnlyPending] = useState(true);
  const [riskBandFilter, setRiskBandFilter] = useState("ALL");
  const [phaseFilter, setPhaseFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");
  const [selectedGate, setSelectedGate] = useState<InferredApprovalGate | null>(null);

  const { diagnosticsQueries, approvalGates } = useApprovalQueue(trackedCampaignIds);

  // Derive available phases from loaded gates for the phase filter dropdown
  const availablePhases = useMemo(() => {
    const names = new Set<string>();
    for (const gate of approvalGates) {
      const name = gate.phase_name ?? gate.phase_job_id;
      if (name) {
        names.add(name);
      }
    }
    return Array.from(names).sort();
  }, [approvalGates]);

  const visibleGates = useMemo(() => {
    const loweredSearch = searchText.trim().toLowerCase();
    return approvalGates.filter((gate) => {
      if (showOnlyPending && !gateIsPending(gate.status)) {
        return false;
      }
      if (riskBandFilter !== "ALL" && gate.risk_band !== riskBandFilter) {
        return false;
      }
      if (phaseFilter !== "ALL") {
        const phaseName = gate.phase_name ?? gate.phase_job_id ?? "";
        if (phaseName !== phaseFilter) {
          return false;
        }
      }
      if (!loweredSearch) {
        return true;
      }
      const haystack = [
        gate.request_title,
        gate.requested_action,
        gate.requesting_agent,
        gate.phase_name,
        gate.phase_job_id,
        gate.scope_target,
        gate.justification,
        gate.intention,
        gate.gate_id,
        gate.campaign_id
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(loweredSearch);
    });
  }, [approvalGates, riskBandFilter, phaseFilter, searchText, showOnlyPending]);

  const missingIntentionCount = useMemo(
    () => approvalGates.filter((gate) => gate.intention.trim().length === 0).length,
    [approvalGates]
  );

  function makeDecision(
    gateId: string,
    status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED",
    intention?: string,
    notes?: string
  ) {
    approvalMutation.mutate({ gateId, status, decidedBy: APPROVAL_CONSOLE_ACTOR, notes, intention });
  }

  const approvalMutation = useMutation({
    mutationFn: ({
      gateId,
      status,
      decidedBy,
      notes,
      intention
    }: {
      gateId: string;
      status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";
      decidedBy: string;
      notes?: string;
      intention?: string;
    }) =>
      decideApprovalGate(gateId, {
        status,
        decided_by: decidedBy,
        operator_notes: notes,
        decision_payload_json: intention ? { reviewer_intention: intention } : {}
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(result.campaign_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(result.campaign_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
      // Refresh the selected gate display if it was just decided
      setSelectedGate((prev) => {
        if (prev?.gate_id === result.campaign_id) {
          return null;
        }
        return prev;
      });
    }
  });

  function onTrackCampaign(event: FormEvent) {
    event.preventDefault();
    const trimmed = campaignInput.trim();
    if (!isUuid(trimmed)) {
      return;
    }
    addCampaignId(trimmed);
    setCampaignInput("");
  }

  function onSelectGate(gate: InferredApprovalGate) {
    setSelectedGate((prev) => (prev?.gate_id === gate.gate_id ? null : gate));
  }

  const queryErrors = diagnosticsQueries
    .map((query, index) => ({ query, campaignId: trackedCampaignIds[index] ?? "unknown" }))
    .filter((entry) => entry.query.isError)
    .map((entry) => ({ key: entry.campaignId, error: entry.query.error }));

  return (
    <div className="operator-grid">
      <PageHeader
        title="Approval Queue"
        description="Human-in-the-loop governance queue. Every Band 2 action requires explicit operator intent before execution proceeds."
      />

      {/* ── Campaign scope selector ────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Governance Queue Scope</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={onTrackCampaign}>
            <Input
              value={campaignInput}
              onChange={(event) => setCampaignInput(event.target.value)}
              placeholder="campaign UUID"
            />
            <Button variant="secondary" type="submit">
              Track Campaign
            </Button>
          </form>
          <label className="inline-flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={showOnlyPending}
              onChange={(event) => setShowOnlyPending(event.target.checked)}
            />
            Show pending / deferred only
          </label>
          <div className="grid gap-2 md:grid-cols-3">
            <Select value={riskBandFilter} onChange={(event) => setRiskBandFilter(event.target.value)}>
              <option value="ALL">All risk bands</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
              <option value="UNSPECIFIED">UNSPECIFIED</option>
            </Select>
            <Select value={phaseFilter} onChange={(event) => setPhaseFilter(event.target.value)}>
              <option value="ALL">All phases</option>
              {availablePhases.map((phase) => (
                <option key={phase} value={phase}>
                  {phase}
                </option>
              ))}
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search title, intention, agent, scope, mission…"
            />
          </div>
          <p className="text-xs text-muted">
            visible: {visibleGates.length} / total: {approvalGates.length}
          </p>
        </CardContent>
      </Card>

      {/* ── Summary + Pending row ──────────────────────────────────── */}
      <ApprovalGateSummary gates={approvalGates} />

      <Card>
        <CardHeader>
          <CardTitle>Pending / Deferred Gates</CardTitle>
        </CardHeader>
        <CardContent>
          <PendingApprovalPanel gates={approvalGates} />
        </CardContent>
      </Card>

      {/* ── Missing-intention warning ──────────────────────────────── */}
      {missingIntentionCount > 0 ? (
        <Alert className="border-danger/50 bg-danger/10 text-danger">
          {missingIntentionCount} approval request(s) are missing intention metadata.
          These requests cannot be approved until the agent supplies a declared intention.
          The Approve button is disabled for all affected rows.
        </Alert>
      ) : null}

      {/* ── Detail panel (shown when a row is selected) ────────────── */}
      {selectedGate ? (
        <ApprovalDetailPanel
          gate={selectedGate}
          loading={approvalMutation.isPending}
          onClose={() => setSelectedGate(null)}
          onAction={(gateId, status, notes) => {
            const gate = approvalGates.find((g) => g.gate_id === gateId);
            makeDecision(gateId, status, gate?.intention, notes);
          }}
        />
      ) : null}

      {/* ── Governance queue table ─────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Governance Review Queue</CardTitle>
        </CardHeader>
        <CardContent>
          {trackedCampaignIds.length === 0 ? (
            <EmptyState
              title="No tracked campaigns"
              description="Track one or more campaign IDs to populate the approval queue."
            />
          ) : visibleGates.length > 0 ? (
            <ApprovalGateTable
              rows={visibleGates}
              selectedGateId={selectedGate?.gate_id}
              onSelect={onSelectGate}
              onAction={(gateId, status) => {
                const gate = visibleGates.find((g) => g.gate_id === gateId);
                makeDecision(gateId, status, gate?.intention);
              }}
            />
          ) : (
            <EmptyState
              title="No governance items"
              description="No approval requests match current status / risk / phase / search filters."
            />
          )}
        </CardContent>
      </Card>

      {/* ── Manual decision form ───────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Manual Approval Decision</CardTitle>
        </CardHeader>
        <CardContent>
          <ApprovalDecisionDialog
            loading={approvalMutation.isPending}
            onSubmit={({ gateId, status, decidedBy, notes, intention }) =>
              approvalMutation.mutate({ gateId, status, decidedBy, notes, intention })
            }
          />
        </CardContent>
      </Card>

      {/* ── Error states ───────────────────────────────────────────── */}
      {approvalMutation.isError ? (
        <ErrorState error={approvalMutation.error} title="Approval decision failed" />
      ) : null}

      {queryErrors.length > 0 ? (
        <div className="space-y-2">
          {queryErrors.map(({ key, error }) => (
            <ErrorState key={key} error={error} title={`Diagnostics load failed (${key})`} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
