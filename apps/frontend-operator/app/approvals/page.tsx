"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { decideApprovalGate } from "@/lib/api/approvals";
import { useApprovalQueue } from "@/hooks/useApprovalQueue";
import { queryKeys } from "@/lib/query-keys";
import { addTrackedCampaignId, loadTrackedCampaignIds, saveTrackedCampaignIds } from "@/lib/tracked-campaigns";
import { isUuid } from "@/lib/utils";
import { gateIsPending } from "@/lib/approval-gates";

import { ApprovalDecisionDialog } from "@/components/approvals/ApprovalDecisionDialog";
import { ApprovalGateSummary } from "@/components/approvals/ApprovalGateSummary";
import { ApprovalGateTable } from "@/components/approvals/ApprovalGateTable";
import { PendingApprovalPanel } from "@/components/approvals/PendingApprovalPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [trackedCampaignIds, setTrackedCampaignIds] = useState<string[]>([]);
  const [campaignInput, setCampaignInput] = useState("");
  const [showOnlyPending, setShowOnlyPending] = useState(true);

  useEffect(() => {
    setTrackedCampaignIds(loadTrackedCampaignIds());
  }, []);

  useEffect(() => {
    saveTrackedCampaignIds(trackedCampaignIds);
  }, [trackedCampaignIds]);

  const { diagnosticsQueries, approvalGates } = useApprovalQueue(trackedCampaignIds);

  const visibleGates = useMemo(
    () => (showOnlyPending ? approvalGates.filter((gate) => gateIsPending(gate.status)) : approvalGates),
    [approvalGates, showOnlyPending]
  );

  const approvalMutation = useMutation({
    mutationFn: ({
      gateId,
      status,
      decidedBy,
      notes
    }: {
      gateId: string;
      status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";
      decidedBy: string;
      notes?: string;
    }) =>
      decideApprovalGate(gateId, {
        status,
        decided_by: decidedBy,
        operator_notes: notes
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(result.campaign_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(result.campaign_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  function onTrackCampaign(event: FormEvent) {
    event.preventDefault();
    const trimmed = campaignInput.trim();
    if (!isUuid(trimmed)) {
      return;
    }
    setTrackedCampaignIds((prev) => addTrackedCampaignId(prev, trimmed));
    setCampaignInput("");
  }

  const queryErrors = diagnosticsQueries
    .map((query, index) => ({ query, campaignId: trackedCampaignIds[index] ?? "unknown" }))
    .filter((entry) => entry.query.isError)
    .map((entry) => ({ key: entry.campaignId, error: entry.query.error }));

  return (
    <div className="operator-grid">
      <PageHeader title="Approval Queue" description="Branch-local HiL decision queue from canonical campaign diagnostics." />

      <Card>
        <CardHeader>
          <CardTitle>Track Campaigns</CardTitle>
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
            Show pending/deferred only
          </label>
        </CardContent>
      </Card>

      <ApprovalGateSummary gates={approvalGates} />
      <PendingApprovalPanel gates={approvalGates} />

      <Card>
        <CardHeader>
          <CardTitle>Approval Gates</CardTitle>
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
              onAction={(gateId, status) =>
                approvalMutation.mutate({
                  gateId,
                  status,
                  decidedBy: "operator.console.approvals"
                })
              }
            />
          ) : (
            <EmptyState title="No approval gates" description="No matching approval gates were found." />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Manual Approval Decision</CardTitle>
        </CardHeader>
        <CardContent>
          <ApprovalDecisionDialog
            loading={approvalMutation.isPending}
            onSubmit={({ gateId, status, decidedBy, notes }) =>
              approvalMutation.mutate({ gateId, status, decidedBy, notes })
            }
          />
        </CardContent>
      </Card>

      {approvalMutation.isError ? <ErrorState error={approvalMutation.error} title="Approval decision failed" /> : null}

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
