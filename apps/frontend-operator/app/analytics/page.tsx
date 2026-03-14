"use client";

import { useAnalytics } from "@/hooks/useAnalytics";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";

import { AnalyticsCards } from "@/components/soc/AnalyticsCards";
import { AnalyticsCharts } from "@/components/soc/AnalyticsCharts";
import { TrackedCampaignSelector } from "@/components/soc/TrackedCampaignSelector";
import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { StatusBadge } from "@/components/status/StatusBadge";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Td, Th } from "@/components/ui/table";

export default function AnalyticsPage() {
  const tracked = useTrackedCampaignIds();
  const data = useAnalytics(tracked.trackedCampaignIds);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Campaign Performance Analytics"
        description="Operational status and volume analytics from canonical diagnostics and tracked campaign state."
      />

      <TrackedCampaignSelector
        trackedCampaignIds={tracked.trackedCampaignIds}
        onAdd={tracked.addCampaignId}
        onRemove={tracked.removeCampaignId}
      />

      {data.summaryQuery.isLoading ? <LoadingState label="Loading analytics summary..." /> : null}
      {data.summaryQuery.isError ? <ErrorState error={data.summaryQuery.error} title="Analytics summary failed" /> : null}
      {data.summaryQuery.data ? (
        <div className="space-y-4">
          <AnalyticsCards summary={data.summaryQuery.data} />
          <AnalyticsCharts summary={data.summaryQuery.data} />
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Tracked Campaign Statuses</CardTitle>
        </CardHeader>
        <CardContent>
          {data.campaignStatusRows.length > 0 ? (
            <DataTable>
              <thead>
                <tr>
                  <Th>Campaign</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {data.campaignStatusRows.map((row) => (
                  <tr key={row.id}>
                    <Td className="font-mono text-xs">{row.id}</Td>
                    <Td>
                      <StatusBadge status={row.status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          ) : (
            <EmptyState
              title="No tracked campaigns"
              description="Track campaigns to populate campaign performance analytics."
            />
          )}
        </CardContent>
      </Card>

      {data.tracked.errors.length > 0 ? (
        <div className="space-y-2">
          {data.tracked.errors.map((entry) => (
            <ErrorState
              key={`${entry.scope}:${entry.campaignId}`}
              error={entry.error}
              title={`Campaign analytics source failed (${entry.campaignId})`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
