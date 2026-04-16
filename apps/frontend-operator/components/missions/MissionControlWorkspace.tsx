"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { correlateCampaign, decideApprovalGate, scheduleCampaign } from "@/lib/api/campaigns";
import { useCampaignDetails } from "@/hooks/useCampaignDetails";
import { useFindingsQueue } from "@/hooks/useFindingsQueue";
import { inferApprovalGates } from "@/lib/approval-gates";
import { APPROVAL_CONSOLE_ACTOR } from "@/lib/operator-identity";
import { queryKeys } from "@/lib/query-keys";
import { deriveTimelineItems } from "@/lib/utils/soc";
import type { ArtifactReference } from "@/components/cockpit/ArtifactDrawer";

import { ApprovalGateTable } from "@/components/approvals/ApprovalGateTable";
import { ArtifactDrawer } from "@/components/cockpit/ArtifactDrawer";
import { MissionLinkedSidePanel } from "@/components/cockpit/MissionLinkedSidePanel";
import { PhaseProgressRibbon } from "@/components/cockpit/PhaseProgressRibbon";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { FindingsQueueTable } from "@/components/findings/FindingsQueueTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { ToolExecutionDrawer } from "@/components/phases/ToolExecutionDrawer";
import { ToolExecutionTable } from "@/components/phases/ToolExecutionTable";
import { InvestigationTimeline } from "@/components/soc/InvestigationTimeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

function toArtifactReferences(missionId: string, events: Array<{ id: string; event_type: string; payload: Record<string, unknown> }>): ArtifactReference[] {
  const refs = new Map<string, ArtifactReference>();
  for (const event of events) {
    const payload = event.payload ?? {};
    const stringCandidates = [
      payload.artifact_uri,
      payload.artifact_path,
      payload.stdout_ref,
      payload.stderr_ref
    ].filter((value): value is string => typeof value === "string" && value.length > 0);
    const listCandidates = [
      ...(Array.isArray(payload.artifact_refs_json) ? payload.artifact_refs_json : []),
      ...(Array.isArray(payload.evidence_refs_json) ? payload.evidence_refs_json : [])
    ].filter((value): value is string => typeof value === "string" && value.length > 0);
    for (const uri of [...stringCandidates, ...listCandidates]) {
      if (!refs.has(uri)) {
        refs.set(uri, {
          id: `${event.id}:${uri}`,
          label: `${event.event_type} (${missionId.slice(0, 8)})`,
          uri,
          source: "mission_audit_event"
        });
      }
    }
  }
  return Array.from(refs.values()).slice(0, 25);
}

export function MissionControlWorkspace({ missionId }: { missionId: string }) {
  const queryClient = useQueryClient();
  const [approvalActor, setApprovalActor] = useState<string>(APPROVAL_CONSOLE_ACTOR);
  const { campaign: campaignQuery, diagnostics: diagnosticsQuery } = useCampaignDetails(missionId);
  const findingsQuery = useFindingsQueue(missionId);

  const scheduleMutation = useMutation({
    mutationFn: () => scheduleCampaign(missionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(missionId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(missionId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  const correlateMutation = useMutation({
    mutationFn: () => correlateCampaign(missionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(missionId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.findings.queue(missionId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  const approveMutation = useMutation({
    mutationFn: ({
      gateId,
      status,
      intention
    }: {
      gateId: string;
      status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";
      intention?: string;
    }) =>
      decideApprovalGate(gateId, {
        status,
        decided_by: approvalActor,
        operator_notes: "Mission control decision",
        decision_payload_json: intention ? { reviewer_intention: intention } : {}
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(missionId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(missionId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  if (campaignQuery.isLoading || diagnosticsQuery.isLoading) {
    return <LoadingState label="Loading mission control..." />;
  }
  if (campaignQuery.isError) {
    return <ErrorState error={campaignQuery.error} title="Mission load failed" />;
  }
  if (diagnosticsQuery.isError) {
    return <ErrorState error={diagnosticsQuery.error} title="Mission diagnostics failed" />;
  }
  if (!campaignQuery.data || !diagnosticsQuery.data) {
    return <LoadingState label="Waiting for mission state..." />;
  }

  const approvalGates = inferApprovalGates(diagnosticsQuery.data);
  const timelineItems = deriveTimelineItems({
    campaignId: missionId,
    campaignDiagnostics: diagnosticsQuery.data
  });
  const agentActions = diagnosticsQuery.data.recent_audit_events.filter((event) => {
    const actor = (event.actor ?? "").toLowerCase();
    const type = (event.event_type ?? "").toLowerCase();
    return actor.includes("agent") || type.includes("agent");
  });
  const artifacts = toArtifactReferences(
    missionId,
    diagnosticsQuery.data.recent_audit_events.map((event) => ({
      id: event.id,
      event_type: event.event_type,
      payload: event.payload
    }))
  );

  return (
    <div className="operator-grid">
      <PageHeader
        title="Mission Control"
        description="Central execution cockpit for mission progress, gated actions, evidence readiness, and operator decisions."
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
              {correlateMutation.isPending ? "Correlating..." : "Correlate"}
            </Button>
            <Link
              href={`/terminal?mission_id=${missionId}`}
              className="inline-flex h-9 items-center justify-center rounded-md border border-border px-4 text-sm text-foreground hover:bg-elevated"
            >
              Open Mission Terminal
            </Link>
          </>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Mission Summary</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">Mission ID</p>
            <p className="font-mono text-xs text-foreground">{missionId}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">Program</p>
            <p className="font-mono text-xs text-foreground">{campaignQuery.data.campaign.program_id}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">Branches</p>
            <p className="text-sm font-semibold text-foreground">{campaignQuery.data.branches.length}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">Phase Jobs</p>
            <p className="text-sm font-semibold text-foreground">{campaignQuery.data.phase_jobs.length}</p>
          </div>
        </CardContent>
      </Card>

      <PhaseProgressRibbon jobs={campaignQuery.data.phase_jobs} />

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Execution Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <InvestigationTimeline items={timelineItems} />
          </CardContent>
        </Card>
        <MissionLinkedSidePanel
          missionId={missionId}
          missionStatus={campaignQuery.data.campaign.status}
          findingsCount={findingsQuery.data?.count ?? 0}
          approvalCount={approvalGates.length}
          evidenceCount={diagnosticsQuery.data.counts.artifacts + diagnosticsQuery.data.counts.observations}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Agent Actions</CardTitle>
          </CardHeader>
          <CardContent>
            {agentActions.length > 0 ? (
              <InvestigationTimeline
                items={agentActions.map((event) => ({
                  id: event.id,
                  happenedAt: event.happened_at,
                  eventType: event.event_type,
                  actor: event.actor,
                  message: event.message,
                  campaignId: missionId,
                  payload: event.payload
                }))}
              />
            ) : (
              <EmptyState
                title="No agent action events"
                description="No agent-scoped actions were found in recent audit history."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tool Output</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ToolExecutionTable diagnostics={diagnosticsQuery.data} />
            <ToolExecutionDrawer diagnostics={diagnosticsQuery.data} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Evidence Panel</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-muted">
              Artifacts: {diagnosticsQuery.data.counts.artifacts} | Observations: {diagnosticsQuery.data.counts.observations}
            </p>
            <ArtifactDrawer title="Mission Artifacts" items={artifacts} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Approvals / Gates</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={approvalActor}
              onChange={(event) => setApprovalActor(event.target.value)}
              placeholder="approval actor"
            />
            {approvalGates.length > 0 ? (
              <ApprovalGateTable
                rows={approvalGates}
                onAction={(gateId, status) => {
                  const selected = approvalGates.find((gate) => gate.gate_id === gateId);
                  approveMutation.mutate({ gateId, status, intention: selected?.intention });
                }}
              />
            ) : (
              <EmptyState
                title="No approval gates"
                description="No active approval gate records were derived for this mission."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Findings</CardTitle>
        </CardHeader>
        <CardContent>
          {findingsQuery.isLoading ? <LoadingState label="Loading mission findings..." /> : null}
          {findingsQuery.isError ? (
            <ErrorState error={findingsQuery.error} title="Mission findings failed" />
          ) : null}
          {findingsQuery.data ? (
            findingsQuery.data.items.length > 0 ? (
              <FindingsQueueTable rows={findingsQuery.data.items} />
            ) : (
              <EmptyState
                title="No mission findings"
                description="This mission currently has no findings in the review queue."
              />
            )
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
