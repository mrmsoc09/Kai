"use client";

import { useState } from "react";

import { useTimeline } from "@/hooks/useTimeline";

import { InvestigationTimeline } from "@/components/soc/InvestigationTimeline";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function TimelinePage() {
  const [campaignId, setCampaignId] = useState("");
  const [findingId, setFindingId] = useState("");
  const data = useTimeline({ campaignId, findingId });

  return (
    <div className="operator-grid">
      <PageHeader
        title="Investigation Timeline"
        description="Chronological execution -> observation -> finding -> review -> export event flow from canonical audit records."
      />

      <Card>
        <CardHeader>
          <CardTitle>Timeline Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-2">
          <Input
            value={campaignId}
            onChange={(event) => setCampaignId(event.target.value)}
            placeholder="campaign UUID (optional)"
          />
          <Input
            value={findingId}
            onChange={(event) => setFindingId(event.target.value)}
            placeholder="finding UUID (optional)"
          />
        </CardContent>
      </Card>

      {data.campaignDiagnosticsQuery.isLoading || data.findingDiagnosticsQuery.isLoading ? (
        <LoadingState label="Loading timeline..." />
      ) : null}
      {data.campaignDiagnosticsQuery.isError ? (
        <ErrorState error={data.campaignDiagnosticsQuery.error} title="Campaign timeline source failed" />
      ) : null}
      {data.findingDiagnosticsQuery.isError ? (
        <ErrorState error={data.findingDiagnosticsQuery.error} title="Finding timeline source failed" />
      ) : null}

      <InvestigationTimeline items={data.timeline} />
    </div>
  );
}
