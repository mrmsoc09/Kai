"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { flattenRecentAuditEvents, deriveOverviewAlerts } from "@/lib/utils/soc";
import { useTrackedCampaignData } from "@/hooks/useTrackedCampaignData";

export function useOverview(campaignIds: string[]) {
  const tracked = useTrackedCampaignData(campaignIds);

  const summaryQuery = useQuery({
    queryKey: queryKeys.diagnostics.summary(),
    queryFn: ({ signal }) => socApi.getDiagnosticsSummary(signal)
  });
  const healthQuery = useQuery({
    queryKey: queryKeys.diagnostics.health(),
    queryFn: ({ signal }) => socApi.getHealth(signal)
  });
  const readinessQuery = useQuery({
    queryKey: queryKeys.diagnostics.ready(),
    queryFn: ({ signal }) => socApi.getReadiness(signal)
  });
  const findingsQueueQuery = useQuery({
    queryKey: queryKeys.findings.queue(),
    queryFn: () => socApi.getFindingsReviewQueue({ limit: 300 })
  });

  const findingsQueue = findingsQueueQuery.data?.items ?? [];

  const alerts = useMemo(
    () =>
      deriveOverviewAlerts({
        diagnostics: tracked.diagnostics,
        findings: findingsQueue,
        summaryGeneratedAt: summaryQuery.data?.generated_at
      }),
    [tracked.diagnostics, findingsQueue, summaryQuery.data?.generated_at]
  );

  const recentAuditEvents = useMemo(
    () => flattenRecentAuditEvents({ campaignDiagnostics: tracked.diagnostics }).slice(0, 25),
    [tracked.diagnostics]
  );

  return {
    trackedCampaigns: tracked.campaigns,
    trackedDiagnostics: tracked.diagnostics,
    trackedErrors: tracked.errors,
    summaryQuery,
    healthQuery,
    readinessQuery,
    findingsQueueQuery,
    alerts,
    recentAuditEvents
  };
}
