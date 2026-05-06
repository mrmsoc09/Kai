import Link from "next/link";

import type { MissionCockpitModel } from "@/lib/utils/cockpit";

import { StatusBadge } from "@/components/status/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type OverviewMissionCockpitRow = {
  missionId: string;
  programId: string;
  missionStatus: string;
  model: MissionCockpitModel;
};

function summarizeBlockers(model: MissionCockpitModel): number {
  return model.pendingApprovals + model.findingsNeedingReview + model.failedToolExecutions;
}

function topAction(model: MissionCockpitModel) {
  return model.actions.find((action) => action.priority === "HIGH") ?? model.actions[0] ?? null;
}

export function OverviewMissionCockpit({ rows }: { rows: OverviewMissionCockpitRow[] }) {
  const missionCount = rows.length;
  const avgAutonomy = missionCount
    ? Math.round(rows.reduce((sum, row) => sum + row.model.autonomyCoverage, 0) / missionCount)
    : 0;
  const avgConfidence = missionCount
    ? Math.round(rows.reduce((sum, row) => sum + row.model.confidenceScore, 0) / missionCount)
    : 0;
  const manualBlockers = rows.reduce((sum, row) => sum + summarizeBlockers(row.model), 0);

  return (
    <Card className="cockpit-flightdeck">
      <CardHeader className="cockpit-flightdeck-header">
        <CardTitle>Cross-Mission Flight Deck</CardTitle>
        <p className="text-xs text-muted">
          Global AI autonomy and human validation pressure across tracked missions before mission-level drill-down.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Tracked Missions</p>
            <p className="text-2xl font-semibold text-foreground">{missionCount}</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Avg Autonomy</p>
            <p className="text-2xl font-semibold text-foreground">{avgAutonomy}%</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Avg Confidence</p>
            <p className="text-2xl font-semibold text-foreground">{avgConfidence}</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Manual Blockers</p>
            <p className="text-2xl font-semibold text-foreground">{manualBlockers}</p>
          </div>
        </div>

        {rows.length > 0 ? (
          <div className="space-y-2">
            {rows.map((row) => {
              const action = topAction(row.model);
              return (
                <div key={row.missionId} className="cockpit-lane">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-mono text-xs text-foreground">{row.missionId}</p>
                      <p className="text-xs text-muted">program: {row.programId}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={row.missionStatus} />
                      <Badge className="border-active/30 bg-active/10 text-active">Auto {row.model.autonomyCoverage}%</Badge>
                      <Badge className="border-review/30 bg-review/10 text-review">Manual {row.model.manualCoverage}%</Badge>
                      <Link href={`/mission-control/${row.missionId}`} className="text-xs text-active hover:underline">
                        Open Mission
                      </Link>
                    </div>
                  </div>
                  {action ? (
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs text-muted">Next action: {action.title}</p>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={action.status} />
                        <Link href={action.href} className="text-xs text-active hover:underline">
                          Route
                        </Link>
                      </div>
                    </div>
                  ) : null}
                  <details className="mt-2 rounded-md border border-border bg-panel/60 p-2">
                    <summary className="cursor-pointer text-xs font-medium text-foreground">
                      Manual checklist preview
                    </summary>
                    <div className="mt-2 space-y-2">
                      <div className="space-y-1">
                        <p className="text-[11px] uppercase tracking-wide text-muted">Guided Steps</p>
                        {row.model.guidanceSteps.slice(0, 3).map((step) => (
                          <div key={step.id} className="rounded-md border border-border bg-elevated/70 p-2">
                            <p className="text-xs font-medium text-foreground">{step.title}</p>
                            <p className="text-xs text-muted">{step.detail}</p>
                            <Link href={step.href} className="text-xs text-active hover:underline">
                              Open
                            </Link>
                          </div>
                        ))}
                      </div>
                      <div className="space-y-1">
                        <p className="text-[11px] uppercase tracking-wide text-muted">AI Signals</p>
                        {row.model.aiSignals.slice(0, 2).map((signal, index) => (
                          <p key={`${row.missionId}:${index}`} className="text-xs text-muted">
                            {signal}
                          </p>
                        ))}
                      </div>
                    </div>
                  </details>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-muted">
            Track missions from the Missions page to populate cross-mission autonomy and manual validation guidance.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
