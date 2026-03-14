"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getCampaignDiagnostics } from "@/lib/api/campaigns";
import { getFindingDiagnostics } from "@/lib/api/findings";
import { getHealth, getReadiness } from "@/lib/api/diagnostics";
import { useDiagnosticsSummary } from "@/hooks/useDiagnosticsSummary";
import { queryKeys } from "@/lib/query-keys";
import { isUuid } from "@/lib/utils";

import { AuditFeed } from "@/components/diagnostics/AuditFeed";
import { CampaignDiagnosticsLookup } from "@/components/diagnostics/CampaignDiagnosticsLookup";
import { DiagnosticsSummaryCards } from "@/components/diagnostics/DiagnosticsSummaryCards";
import { FindingDiagnosticsLookup } from "@/components/diagnostics/FindingDiagnosticsLookup";
import { HealthPanel } from "@/components/diagnostics/HealthPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DiagnosticsPage() {
  const [campaignId, setCampaignId] = useState("");
  const [findingId, setFindingId] = useState("");

  const summaryQuery = useDiagnosticsSummary();
  const healthQuery = useQuery({
    queryKey: queryKeys.diagnostics.health(),
    queryFn: ({ signal }) => getHealth(signal)
  });
  const readinessQuery = useQuery({
    queryKey: queryKeys.diagnostics.ready(),
    queryFn: ({ signal }) => getReadiness(signal)
  });

  const campaignDiagnosticsQuery = useQuery({
    queryKey: queryKeys.campaigns.diagnostics(campaignId),
    queryFn: ({ signal }) => getCampaignDiagnostics(campaignId, signal),
    enabled: isUuid(campaignId)
  });
  const findingDiagnosticsQuery = useQuery({
    queryKey: queryKeys.findings.detail(findingId),
    queryFn: ({ signal }) => getFindingDiagnostics(findingId, signal),
    enabled: isUuid(findingId)
  });

  return (
    <div className="operator-grid">
      <PageHeader title="Diagnostics" description="Operator-focused health, readiness, metrics, and state inspection." />

      <Card>
        <CardHeader>
          <CardTitle>Lookups</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-2">
          <CampaignDiagnosticsLookup campaignId={campaignId} onChange={setCampaignId} />
          <FindingDiagnosticsLookup findingId={findingId} onChange={setFindingId} />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {healthQuery.isLoading ? <LoadingState label="Loading /health..." /> : null}
        {healthQuery.isError ? <ErrorState error={healthQuery.error} title="Health check failed" /> : null}
        {healthQuery.data ? <HealthPanel title="Liveness" health={healthQuery.data} /> : null}

        {readinessQuery.isLoading ? <LoadingState label="Loading /readyz..." /> : null}
        {readinessQuery.isError ? <ErrorState error={readinessQuery.error} title="Readiness check failed" /> : null}
        {readinessQuery.data ? <HealthPanel title="Readiness" health={readinessQuery.data} /> : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Canonical Metrics Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {summaryQuery.isLoading ? <LoadingState label="Loading diagnostics summary..." /> : null}
          {summaryQuery.isError ? <ErrorState error={summaryQuery.error} title="Summary load failed" /> : null}
          {summaryQuery.data ? <DiagnosticsSummaryCards summary={summaryQuery.data} /> : null}
        </CardContent>
      </Card>

      {isUuid(campaignId) ? (
        <Card>
          <CardHeader>
            <CardTitle>Campaign Diagnostics</CardTitle>
          </CardHeader>
          <CardContent>
            {campaignDiagnosticsQuery.isLoading ? <LoadingState label="Loading campaign diagnostics..." /> : null}
            {campaignDiagnosticsQuery.isError ? (
              <ErrorState error={campaignDiagnosticsQuery.error} title="Campaign diagnostics failed" />
            ) : null}
            {campaignDiagnosticsQuery.data ? (
              <AuditFeed events={campaignDiagnosticsQuery.data.recent_audit_events} />
            ) : null}
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title="Campaign diagnostics lookup disabled"
          description="Enter a valid campaign UUID to load campaign diagnostics."
        />
      )}

      {isUuid(findingId) ? (
        <Card>
          <CardHeader>
            <CardTitle>Finding Diagnostics</CardTitle>
          </CardHeader>
          <CardContent>
            {findingDiagnosticsQuery.isLoading ? <LoadingState label="Loading finding diagnostics..." /> : null}
            {findingDiagnosticsQuery.isError ? (
              <ErrorState error={findingDiagnosticsQuery.error} title="Finding diagnostics failed" />
            ) : null}
            {findingDiagnosticsQuery.data ? <AuditFeed events={findingDiagnosticsQuery.data.recent_audit_events} /> : null}
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title="Finding diagnostics lookup disabled"
          description="Enter a valid finding UUID to load finding diagnostics."
        />
      )}
    </div>
  );
}
