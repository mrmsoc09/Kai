"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { useApprovalQueue } from "@/hooks/useApprovalQueue";
import { useBountyDashboard } from "@/hooks/useBountyDashboard";
import { useCampaigns } from "@/hooks/useCampaigns";
import { useFindingsQueue } from "@/hooks/useFindingsQueue";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";
import { gateIsPending } from "@/lib/approval-gates";

import { PendingApprovalPanel } from "@/components/approvals/PendingApprovalPanel";
import { ActionCard } from "@/components/cockpit/ActionCard";
import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { FindingsQueueTable } from "@/components/findings/FindingsQueueTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function OverviewPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const missionTracking = useTrackedCampaignIds();
  const missionQueries = useCampaigns(missionTracking.trackedCampaignIds);
  const approvals = useApprovalQueue(missionTracking.trackedCampaignIds);
  const findingsQuery = useFindingsQueue();
  const data = useBountyDashboard(programIdFilter.trim() || undefined);

  const trackedMissions = useMemo(
    () => missionQueries.filter((query) => query.isSuccess).map((query) => query.data.campaign),
    [missionQueries]
  );
  const activeMissions = useMemo(
    () =>
      trackedMissions.filter((mission) =>
        ["RUNNING", "WAITING_APPROVAL", "BLOCKED", "READY"].includes(mission.status)
      ),
    [trackedMissions]
  );
  const pendingApprovals = useMemo(
    () => approvals.approvalGates.filter((gate) => gateIsPending(gate.status)),
    [approvals.approvalGates]
  );
  const findings = findingsQuery.data?.items ?? [];
  const priorityFindings = useMemo(
    () =>
      [...findings]
        .sort((a, b) => {
          if (a.readiness_status === "READY_FOR_SUBMISSION" && b.readiness_status !== "READY_FOR_SUBMISSION") {
            return -1;
          }
          if (a.readiness_status !== "READY_FOR_SUBMISSION" && b.readiness_status === "READY_FOR_SUBMISSION") {
            return 1;
          }
          return b.evidence_count - a.evidence_count;
        })
        .slice(0, 12),
    [findings]
  );
  const evidenceReadyItems = findings.filter((item) =>
    item.readiness_status.toUpperCase().includes("READY")
  );

  const attackPathHighlights = useMemo(() => {
    const grouped = new Map<string, { asset: string; findings: number; evidence: number; campaigns: Set<string> }>();
    for (const finding of findings) {
      const key = finding.asset;
      const current = grouped.get(key) ?? {
        asset: finding.asset,
        findings: 0,
        evidence: 0,
        campaigns: new Set<string>()
      };
      current.findings += 1;
      current.evidence += finding.evidence_count;
      current.campaigns.add(finding.campaign_id);
      grouped.set(key, current);
    }
    return Array.from(grouped.values())
      .sort((a, b) => b.findings - a.findings)
      .slice(0, 8);
  }, [findings]);

  const toolsSummary = data.toolsHealthQuery.data?.summary;
  const pipelineFailureCount =
    (data.schedulerStatusQuery.data?.error_schedules ?? 0) +
    Math.max((toolsSummary?.total_tools ?? 0) - (toolsSummary?.healthy_tools ?? 0), 0);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Action Board"
        description="Mission-centric decision board prioritizing active risk, approvals, evidence readiness, and execution failures."
      />

      <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <ActionCard
          title="Priority Findings"
          value={priorityFindings.length}
          status={priorityFindings.length > 0 ? "NEEDS_REVIEW" : "READY"}
          detail="Top findings needing operator attention."
          href="/findings"
        />
        <ActionCard
          title="Active Missions"
          value={activeMissions.length}
          status={activeMissions.length > 0 ? "RUNNING" : "READY"}
          detail="Tracked missions currently progressing or gated."
          href="/missions"
        />
        <ActionCard
          title="Evidence-Ready"
          value={evidenceReadyItems.length}
          status={evidenceReadyItems.length > 0 ? "READY_FOR_SUBMISSION" : "READY"}
          detail="Findings ready to move toward report/export."
          href="/evidence"
        />
        <ActionCard
          title="Approval Queue"
          value={pendingApprovals.length}
          status={pendingApprovals.length > 0 ? "WAITING_APPROVAL" : "COMPLETED"}
          detail="Human approval decisions currently blocking flow."
          href="/approvals"
        />
        <ActionCard
          title="Attack-Path Hotspots"
          value={attackPathHighlights.length}
          status={attackPathHighlights.length > 0 ? "NEEDS_REVIEW" : "READY"}
          detail="Assets accumulating correlated finding pressure."
          href="/evidence"
        />
        <ActionCard
          title="Pipeline / Tool Failures"
          value={pipelineFailureCount}
          status={pipelineFailureCount > 0 ? "FAILED" : "COMPLETED"}
          detail="Scheduler + tool health failures requiring intervention."
          href="/system"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Priority Findings</CardTitle>
          </CardHeader>
          <CardContent>
            {findingsQuery.isLoading ? <LoadingState label="Loading findings..." /> : null}
            {findingsQuery.isError ? <ErrorState error={findingsQuery.error} title="Findings load failed" /> : null}
            {priorityFindings.length > 0 ? (
              <FindingsQueueTable rows={priorityFindings} />
            ) : (
              <EmptyState
                title="No priority findings"
                description="No findings are currently queued at priority levels."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Active Missions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {activeMissions.length > 0 ? (
              activeMissions.map((mission) => (
                <div key={mission.id} className="rounded-md border border-border bg-elevated p-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-mono text-xs text-foreground">{mission.id}</p>
                      <p className="text-xs text-muted">program: {mission.program_id}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={mission.status} />
                      <Link href={`/mission-control/${mission.id}`} className="text-xs text-active hover:underline">
                        Open
                      </Link>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                title="No active missions"
                description="Track missions from the Missions page to surface active execution here."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Approval Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <PendingApprovalPanel gates={pendingApprovals} showApprovalLink />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Attack-Path Highlights</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {attackPathHighlights.length > 0 ? (
              attackPathHighlights.map((row) => (
                <div key={row.asset} className="rounded-md border border-border bg-elevated p-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-mono text-xs text-foreground">{row.asset}</p>
                    <p className="text-xs text-muted">{row.campaigns.size} mission(s)</p>
                  </div>
                  <p className="text-xs text-muted">
                    findings: {row.findings} | evidence: {row.evidence}
                  </p>
                </div>
              ))
            ) : (
              <EmptyState
                title="No attack-path highlights"
                description="No asset concentration signals were derived from the findings queue."
              />
            )}
          </CardContent>
        </Card>
      </div>

      {data.toolsHealthQuery.isError ? (
        <ErrorState error={data.toolsHealthQuery.error} title="Tool health failed" />
      ) : null}
      {data.schedulerStatusQuery.isError ? (
        <ErrorState error={data.schedulerStatusQuery.error} title="Scheduler status failed" />
      ) : null}
      {approvals.diagnosticsQueries
        .map((query, index) => ({ query, missionId: missionTracking.trackedCampaignIds[index] ?? "unknown" }))
        .filter((row) => row.query.isError)
        .map((row) => (
          <ErrorState key={row.missionId} error={row.query.error} title={`Mission diagnostics failed (${row.missionId})`} />
        ))}
    </div>
  );
}
