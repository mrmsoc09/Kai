"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { correlateCampaign, decideApprovalGate, scheduleCampaign } from "@/lib/api/campaigns";
import { useCampaignDetails } from "@/hooks/useCampaignDetails";
import { inferApprovalGates } from "@/lib/approval-gates";
import { queryKeys } from "@/lib/query-keys";

import { ApprovalGateTable } from "@/components/approvals/ApprovalGateTable";
import { CampaignDiagnosticsPanel } from "@/components/campaigns/CampaignDiagnosticsPanel";
import { CampaignStatusHeader } from "@/components/campaigns/CampaignStatusHeader";
import { CampaignSummaryPanel } from "@/components/campaigns/CampaignSummaryPanel";
import { AuditEventList } from "@/components/data-display/AuditEventList";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { BranchGraphPanel } from "@/components/phases/BranchGraphPanel";
import { BranchList } from "@/components/phases/BranchList";
import { PhaseJobTable } from "@/components/phases/PhaseJobTable";
import { ToolExecutionDrawer } from "@/components/phases/ToolExecutionDrawer";
import { ToolExecutionTable } from "@/components/phases/ToolExecutionTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function CampaignDetailPage() {
  const params = useParams<{ campaignId: string }>();
  const campaignId = params.campaignId;
  const queryClient = useQueryClient();
  const [approvalActor, setApprovalActor] = useState("operator.console.approvals");

  const { campaign: campaignQuery, diagnostics: diagnosticsQuery } = useCampaignDetails(campaignId);

  const scheduleMutation = useMutation({
    mutationFn: () => scheduleCampaign(campaignId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(campaignId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(campaignId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  const correlateMutation = useMutation({
    mutationFn: () => correlateCampaign(campaignId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(campaignId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.findings.queue() });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  const approveMutation = useMutation({
    mutationFn: ({
      gateId,
      status
    }: {
      gateId: string;
      status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";
    }) =>
      decideApprovalGate(gateId, {
        status,
        decided_by: approvalActor,
        operator_notes: "Operator console decision"
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(campaignId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(campaignId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  const inferredApprovalGates = useMemo(
    () => (diagnosticsQuery.data ? inferApprovalGates(diagnosticsQuery.data) : []),
    [diagnosticsQuery.data]
  );

  if (campaignQuery.isLoading || diagnosticsQuery.isLoading) {
    return <LoadingState label="Loading campaign detail..." />;
  }
  if (campaignQuery.isError) {
    return <ErrorState error={campaignQuery.error} title="Campaign detail failed" />;
  }
  if (diagnosticsQuery.isError) {
    return <ErrorState error={diagnosticsQuery.error} title="Campaign diagnostics failed" />;
  }
  if (!campaignQuery.data || !diagnosticsQuery.data) {
    return <LoadingState label="Waiting for campaign state..." />;
  }

  return (
    <div className="operator-grid">
      <PageHeader
        title="Campaign Detail / Execution Monitor"
        description="Branch, phase, approval, and diagnostics visibility for one campaign."
        actions={
          <>
            <Button disabled={scheduleMutation.isPending} onClick={() => scheduleMutation.mutate()}>
              {scheduleMutation.isPending ? "Scheduling..." : "Re-schedule"}
            </Button>
            <Button
              variant="secondary"
              disabled={correlateMutation.isPending}
              onClick={() => correlateMutation.mutate()}
            >
              {correlateMutation.isPending ? "Correlating..." : "Correlate Observations"}
            </Button>
          </>
        }
      />

      <CampaignStatusHeader campaign={campaignQuery.data} />
      <CampaignSummaryPanel campaign={campaignQuery.data} />
      <CampaignDiagnosticsPanel diagnostics={diagnosticsQuery.data} />

      <Card>
        <CardHeader>
          <CardTitle>Branch Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <BranchGraphPanel jobs={campaignQuery.data.phase_jobs} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Branches</CardTitle>
        </CardHeader>
        <CardContent>
          <BranchList branches={campaignQuery.data.branches} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Phase Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <PhaseJobTable jobs={campaignQuery.data.phase_jobs} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Approval Gates</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={approvalActor}
            onChange={(event) => setApprovalActor(event.target.value)}
            placeholder="approval actor"
          />
          <ApprovalGateTable
            rows={inferredApprovalGates}
            onAction={(gateId, status) => approveMutation.mutate({ gateId, status })}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tool Execution Visibility</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <SectionHeader title="Execution Metrics" />
          <ToolExecutionTable diagnostics={diagnosticsQuery.data} />
          <SectionHeader title="Status Breakdown" />
          <ToolExecutionDrawer diagnostics={diagnosticsQuery.data} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Audit Events</CardTitle>
        </CardHeader>
        <CardContent>
          <AuditEventList events={diagnosticsQuery.data.recent_audit_events} />
        </CardContent>
      </Card>
    </div>
  );
}
