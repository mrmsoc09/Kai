import Link from "next/link";

import type { CampaignDiagnosticsResponse, CampaignStatusResponse } from "@/lib/types";
import { deriveMissionCockpitModel } from "@/lib/utils/cockpit";

import { StatusBadge } from "@/components/status/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function PriorityBadge({ priority }: { priority: "HIGH" | "MEDIUM" | "LOW" }) {
  const className =
    priority === "HIGH"
      ? "border-danger/40 bg-danger/10 text-danger"
      : priority === "MEDIUM"
        ? "border-review/40 bg-review/10 text-review"
        : "border-active/30 bg-active/10 text-active";

  return <Badge className={className}>{priority}</Badge>;
}

export function HuntExecutionCockpit({
  missionId,
  campaign,
  diagnostics,
  findingsCount,
  approvalCount
}: {
  missionId: string;
  campaign: CampaignStatusResponse;
  diagnostics: CampaignDiagnosticsResponse;
  findingsCount: number;
  approvalCount: number;
}) {
  const model = deriveMissionCockpitModel({
    missionId,
    campaign,
    diagnostics,
    findingsCount,
    approvalCount
  });

  const autonomousActions = model.actions.filter((action) => action.lane === "AUTONOMOUS");
  const manualActions = model.actions.filter((action) => action.lane === "MANUAL");

  return (
    <Card className="cockpit-flightdeck">
      <CardHeader className="cockpit-flightdeck-header">
        <CardTitle>Pilot + Copilot Mission Deck</CardTitle>
        <p className="text-xs text-muted">
          AI lane drives autonomous recon and correlation while operator lane focuses on exploit confirmation and approval gates.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Autonomy Coverage</p>
            <p className="text-2xl font-semibold text-foreground">{model.autonomyCoverage}%</p>
            <StatusBadge status={model.autonomyStatus} />
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Manual Coverage</p>
            <p className="text-2xl font-semibold text-foreground">{model.manualCoverage}%</p>
            <StatusBadge status={model.manualStatus} />
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Confidence Score</p>
            <p className="text-2xl font-semibold text-foreground">{model.confidenceScore}</p>
            <StatusBadge status={model.confidenceStatus} />
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Evidence Throughput</p>
            <p className="text-2xl font-semibold text-foreground">{model.evidenceCount}</p>
            <p className="text-xs text-muted">
              Approvals: {model.pendingApprovals} | Findings: {model.findingsNeedingReview}
            </p>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <div className="cockpit-lane">
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-foreground">Autonomous Lane</p>
              <StatusBadge status={model.autonomyStatus} />
            </div>
            <div className="space-y-2">
              {autonomousActions.map((action) => (
                <div key={action.id} className="rounded-md border border-border bg-panel/60 p-2">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-foreground">{action.title}</p>
                    <PriorityBadge priority={action.priority} />
                  </div>
                  <p className="text-xs text-muted">{action.description}</p>
                  <div className="mt-2 flex items-center justify-between">
                    <StatusBadge status={action.status} />
                    <Link href={action.href} className="text-xs font-medium text-active hover:underline">
                      Open
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="cockpit-lane">
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-foreground">Manual Hunt Lane</p>
              <StatusBadge status={model.manualStatus} />
            </div>
            <div className="space-y-2">
              {manualActions.length > 0 ? (
                manualActions.map((action) => (
                  <div key={action.id} className="rounded-md border border-border bg-panel/60 p-2">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-foreground">{action.title}</p>
                      <PriorityBadge priority={action.priority} />
                    </div>
                    <p className="text-xs text-muted">{action.description}</p>
                    <div className="mt-2 flex items-center justify-between">
                      <StatusBadge status={action.status} />
                      <Link href={action.href} className="text-xs font-medium text-active hover:underline">
                        Review
                      </Link>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-muted">No manual blockers currently require intervention.</p>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
          <div className="cockpit-lane">
            <p className="mb-3 text-sm font-semibold text-foreground">Guided Manual Scan Checklist</p>
            <div className="space-y-2">
              {model.guidanceSteps.map((step) => (
                <div key={step.id} className="rounded-md border border-border bg-panel/60 p-2">
                  <p className="text-sm font-medium text-foreground">{step.title}</p>
                  <p className="mt-1 text-xs text-muted">{step.detail}</p>
                  <Link href={step.href} className="mt-2 inline-flex text-xs font-medium text-active hover:underline">
                    Open related workspace
                  </Link>
                </div>
              ))}
            </div>
          </div>

          <div className="cockpit-lane">
            <p className="mb-3 text-sm font-semibold text-foreground">AI Signal Brief</p>
            <ul className="space-y-2">
              {model.aiSignals.map((signal, index) => (
                <li key={`${signal}:${index}`} className="rounded-md border border-border bg-panel/60 p-2 text-xs text-foreground">
                  {signal}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted">
              Active tools: {model.activeToolExecutions} | Failed tools: {model.failedToolExecutions}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
