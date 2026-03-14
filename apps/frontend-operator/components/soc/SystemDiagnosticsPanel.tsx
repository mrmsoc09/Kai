import type { CampaignDiagnosticsResponse, FindingDiagnosticsResponse } from "@/lib/types";

import { AuditFeed } from "@/components/diagnostics/AuditFeed";
import { DiagnosticsSummaryCards } from "@/components/diagnostics/DiagnosticsSummaryCards";
import { HealthPanel } from "@/components/diagnostics/HealthPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SystemDiagnosticsPanel({
  summary,
  health,
  readiness,
  campaignDiagnostics,
  findingDiagnostics
}: {
  summary?: Parameters<typeof DiagnosticsSummaryCards>[0]["summary"];
  health?: Parameters<typeof HealthPanel>[0]["health"];
  readiness?: Parameters<typeof HealthPanel>[0]["health"];
  campaignDiagnostics?: CampaignDiagnosticsResponse | null;
  findingDiagnostics?: FindingDiagnosticsResponse | null;
}) {
  return (
    <div className="space-y-4">
      {summary ? (
        <Card>
          <CardHeader>
            <CardTitle>Diagnostics Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <DiagnosticsSummaryCards summary={summary} />
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {health ? <HealthPanel title="Liveness" health={health} /> : null}
        {readiness ? <HealthPanel title="Readiness" health={readiness} /> : null}
      </div>

      {campaignDiagnostics ? (
        <Card>
          <CardHeader>
            <CardTitle>Campaign Audit Feed</CardTitle>
          </CardHeader>
          <CardContent>
            <AuditFeed events={campaignDiagnostics.recent_audit_events} />
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title="Campaign diagnostics not selected"
          description="Enter a campaign ID to inspect campaign audit activity."
        />
      )}

      {findingDiagnostics ? (
        <Card>
          <CardHeader>
            <CardTitle>Finding Audit Feed</CardTitle>
          </CardHeader>
          <CardContent>
            <AuditFeed events={findingDiagnostics.recent_audit_events} />
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title="Finding diagnostics not selected"
          description="Enter a finding ID to inspect finding audit activity."
        />
      )}
    </div>
  );
}
