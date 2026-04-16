import Link from "next/link";

import { StatusBadge } from "@/components/status/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function MissionLinkedSidePanel({
  missionId,
  missionStatus,
  findingsCount,
  approvalCount,
  evidenceCount
}: {
  missionId: string;
  missionStatus?: string;
  findingsCount?: number;
  approvalCount?: number;
  evidenceCount?: number;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Mission Context</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-muted">Mission ID</p>
          <p className="font-mono text-xs text-foreground">{missionId}</p>
        </div>
        {missionStatus ? (
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-wide text-muted">Status</p>
            <StatusBadge status={missionStatus} />
          </div>
        ) : null}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md border border-border bg-elevated p-2">
            <p className="text-[11px] uppercase text-muted">Findings</p>
            <p className="text-base font-semibold text-foreground">{findingsCount ?? 0}</p>
          </div>
          <div className="rounded-md border border-border bg-elevated p-2">
            <p className="text-[11px] uppercase text-muted">Approvals</p>
            <p className="text-base font-semibold text-foreground">{approvalCount ?? 0}</p>
          </div>
          <div className="rounded-md border border-border bg-elevated p-2">
            <p className="text-[11px] uppercase text-muted">Evidence</p>
            <p className="text-base font-semibold text-foreground">{evidenceCount ?? 0}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Link href={`/mission-control/${missionId}`} className="text-active hover:underline">
            Mission Control
          </Link>
          <Link href={`/findings?campaign_id=${missionId}`} className="text-active hover:underline">
            Findings
          </Link>
          <Link href={`/terminal?mission_id=${missionId}`} className="text-active hover:underline">
            Terminal
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
