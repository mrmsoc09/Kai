"use client";

import { useState } from "react";

import { useSystemDiagnostics } from "@/hooks/useSystemDiagnostics";

import { SystemDiagnosticsPanel } from "@/components/soc/SystemDiagnosticsPanel";
import { CampaignDiagnosticsLookup } from "@/components/diagnostics/CampaignDiagnosticsLookup";
import { FindingDiagnosticsLookup } from "@/components/diagnostics/FindingDiagnosticsLookup";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SystemPage() {
  const [campaignId, setCampaignId] = useState("");
  const [findingId, setFindingId] = useState("");
  const data = useSystemDiagnostics({ campaignId, findingId });

  return (
    <div className="operator-grid">
      <PageHeader
        title="System Diagnostics"
        description="Canonical system operations view for health/readiness, metrics, and campaign/finding diagnostics lookup."
      />

      <Card>
        <CardHeader>
          <CardTitle>Diagnostics Lookups</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-2">
          <CampaignDiagnosticsLookup campaignId={campaignId} onChange={setCampaignId} />
          <FindingDiagnosticsLookup findingId={findingId} onChange={setFindingId} />
        </CardContent>
      </Card>

      {data.summaryQuery.isLoading || data.healthQuery.isLoading || data.readinessQuery.isLoading ? (
        <LoadingState label="Loading system diagnostics..." />
      ) : null}

      {data.summaryQuery.isError ? <ErrorState error={data.summaryQuery.error} title="Summary failed" /> : null}
      {data.healthQuery.isError ? <ErrorState error={data.healthQuery.error} title="Liveness failed" /> : null}
      {data.readinessQuery.isError ? <ErrorState error={data.readinessQuery.error} title="Readiness failed" /> : null}
      {data.campaignDiagnosticsQuery.isError ? (
        <ErrorState error={data.campaignDiagnosticsQuery.error} title="Campaign diagnostics failed" />
      ) : null}
      {data.findingDiagnosticsQuery.isError ? (
        <ErrorState error={data.findingDiagnosticsQuery.error} title="Finding diagnostics failed" />
      ) : null}

      <SystemDiagnosticsPanel
        summary={data.summaryQuery.data}
        health={data.healthQuery.data}
        readiness={data.readinessQuery.data}
        campaignDiagnostics={data.campaignDiagnosticsQuery.data ?? null}
        findingDiagnostics={data.findingDiagnosticsQuery.data ?? null}
      />
    </div>
  );
}
